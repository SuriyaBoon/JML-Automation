[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)] [string]$PlanPath,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $PlanPath)) { throw "Plan not found: $PlanPath" }
$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json

foreach ($operation in $plan) {
    $description = "$($operation.op) for $($operation.username)"
    if ($DryRun -or -not $PSCmdlet.ShouldProcess($description, 'Apply JML operation')) {
        [pscustomobject]@{ operation = $operation.op; status = 'planned'; target = $operation.username }
        continue
    }

    # Production/lab adapter boundary: use a delegated service identity and
    # explicit cmdlets here. Never run this workflow as Domain Admin.
    switch ($operation.op) {
        'create_user' { New-ADUser -SamAccountName $operation.username -GivenName $operation.first_name -Surname $operation.last_name -Title $operation.job_title -Path $operation.ou -Enabled $true }
        'disable_user' { Disable-ADAccount -Identity $operation.username }
        'move_ou' { Move-ADObject -Identity (Get-ADUser $operation.username).DistinguishedName -TargetPath $operation.ou }
        'set_groups' { foreach ($group in $operation.groups) { Add-ADGroupMember -Identity $group -Members $operation.username } }
        'remove_groups' { foreach ($group in $operation.groups) { Remove-ADGroupMember -Identity $group -Members $operation.username -Confirm:$false } }
        'remove_managed_groups' { Write-Warning 'Managed group removal requires an approved group allowlist.' }
        'force_password_change' { Set-ADUser -Identity $operation.username -ChangePasswordAtLogon $true }
        'create_home_directory' { Write-Warning 'Home directory creation requires an approved filesystem adapter.' }
        default { throw "Unsupported JML operation: $($operation.op)" }
    }
    [pscustomobject]@{ operation = $operation.op; status = 'executed'; target = $operation.username }
}
