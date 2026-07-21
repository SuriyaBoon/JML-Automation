# JML MVP Runbook

## Safe local demo

```powershell
$db = "runtime/jml.db"
$plan = "runtime/joiner-plan.json"

python -m jml.cli --db $db submit --request sample_data/joiner.json
python -m jml.cli --db $db approve --request JML-000001 --actor manager-01
python -m jml.cli --db $db plan --request JML-000001 --actor iam-01 --output $plan
python -m jml.cli --db $db execute --request JML-000001 --actor iam-01 --dry-run
python -m jml.cli --db $db verify --request JML-000001 --actor verifier-01 --passed
python -m jml.cli --db $db close --request JML-000001 --actor verifier-01
python -m jml.cli --db $db show --request JML-000001
```

## Applying a lab plan

Only after reviewing the JSON plan and confirming the delegated service identity:

```powershell
.\powershell\Invoke-JMLPlan.ps1 -PlanPath runtime/joiner-plan.json -DryRun
```

Remove `-DryRun` only inside a controlled AD lab. The adapter must never run as Domain Admin, and the plan must be approved before execution.

## Failure handling

- Stop on the first unexpected PowerShell error.
- Keep the request open or mark it failed; never close it automatically.
- Preserve the plan, command output, and audit event.
- Correct the source request or directory state, then create a new controlled execution attempt.
- Verify the final AD state independently.

## Leaver policy

The MVP disables the account and removes managed access. It does not delete the account, mailbox, home directory, or employee data. Retention and ownership decisions are separate approved policies.

