# JML Automation MVP Blueprint

## Workflow

```text
Request -> Validate -> Approval -> Plan -> Execute -> Verify -> Close
```

## Enterprise boundary

```mermaid
flowchart TB
    HR["HR / Manager"] --> API["JML Request API"]
    API --> POLICY["Validation and Approval Policy"]
    POLICY --> PLAN["Execution Plan"]
    PLAN --> WORKER["IAM Worker"]
    WORKER --> AD["Active Directory"]
    WORKER --> FILE["Home Directory"]
    WORKER --> VERIFY["Post-change Verification"]
    VERIFY --> TICKET["Ticket Adapter"]
    API --> AUDIT["Hash-chained Audit"]
    POLICY --> AUDIT
    WORKER --> AUDIT
    VERIFY --> AUDIT
    AD -. "Access-review evidence" .-> SENTINEL["SentinelGRC"]
```

## Lifecycle sequence

```mermaid
sequenceDiagram
    actor Requester
    participant JML as JML Automation
    actor Approver
    actor Operator as IAM Operator
    participant Directory as Active Directory
    actor Verifier

    Requester->>JML: Submit lifecycle request
    JML->>JML: Validate and create ticket
    Approver->>JML: Approve request
    Operator->>JML: Generate execution plan
    Operator->>Directory: Apply approved change or dry-run
    Verifier->>JML: Verify final state
    JML->>JML: Close request and preserve evidence
```

## Roles

`requester`, `hr`, `manager`, `iam_operator`, `verifier`, and `admin`

The requester cannot approve. The executor cannot verify the same request. Leaver workflows disable access and remove managed group membership; they do not delete accounts or data.

## MVP acceptance criteria

- Joiner creates a deterministic plan for account, OU, groups, home directory, and forced password change.
- Mover removes old department groups and adds new department groups.
- Leaver disables the account and removes managed access without a delete operation.
- No plan executes before approval.
- Replaying a request is rejected.
- Every lifecycle event is persisted and hash-linked.
- Dry-run is safe and is the default operational mode.
