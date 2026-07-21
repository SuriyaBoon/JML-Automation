# Sentinel JML Automation

Approval-driven Joiner–Mover–Leaver automation for Active Directory.

This MVP demonstrates one safe identity-lifecycle workflow:

```text
Request → Validate → Approve → Plan → Execute → Verify → Close
```

The default executor is a dry-run adapter. It never changes Active Directory. A PowerShell adapter contract is included for a lab deployment with delegated permissions.

## MVP scope

- Joiner: create an account, place it in the department OU, assign mapped groups, and plan a home directory.
- Mover: remove old department groups and assign the new department groups.
- Leaver: disable the account and remove managed group memberships without deleting data.
- Manager/HR approval with requester/approver separation.
- Idempotent request identity and execution planning.
- SQLite persistence, tamper-evident audit events, verification, and JSON ticket export.
- Dry-run execution and post-change verification contract.

HRIS, Microsoft 365, real ticketing, SSO/MFA, and destructive account deletion are deliberately outside this MVP.

## Quick start

```powershell
python -m jml.cli init --db runtime/jml.db
python -m jml.cli submit --db runtime/jml.db --request sample_data/joiner.json
python -m jml.cli approve --db runtime/jml.db --request JML-000001 --actor manager-01
python -m jml.cli plan --db runtime/jml.db --request JML-000001 --actor iam-01
python -m jml.cli execute --db runtime/jml.db --request JML-000001 --actor iam-01 --dry-run
python -m jml.cli verify --db runtime/jml.db --request JML-000001 --actor verifier-01
python -m jml.cli close --db runtime/jml.db --request JML-000001 --actor verifier-01
```

Mover and leaver examples are in `sample_data/mover.json` and `sample_data/leaver.json`. The plan can be exported for review with `plan --output runtime/plan.json`; tickets are written to `runtime/tickets.json` by the local adapter.

Run all tests:

```powershell
python -m unittest discover -v
```

## Safety model

- No execution before approval.
- Dry-run is the default for the CLI executor.
- Requester cannot approve their own request.
- Executor cannot verify the same request.
- Leaver operations disable access; they do not delete accounts.
- Secrets are not stored in this repository.
- Every lifecycle action is written to an append-only hash chain.
- Ticket creation and closure are recorded in the local reviewable ticket adapter.

## Planned integration

```text
JML Automation → AD access review evidence → SentinelGRC governance finding
```

## Production boundary

Before production use, replace SQLite with PostgreSQL, add OIDC/SSO and MFA, use a managed secret store, run PowerShell through a delegated service identity, add TLS/WAF and durable jobs, and test backup/restore and incident recovery.
