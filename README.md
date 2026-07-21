# Sentinel JML Automation

Approval-driven Joiner–Mover–Leaver automation for Active Directory.

## 1. คืออะไร

JML ย่อมาจาก Joiner (พนักงานเข้าใหม่), Mover (ย้ายแผนก/role) และ Leaver (สิ้นสุดการจ้างงาน) โปรเจกต์นี้เป็น workflow สำหรับควบคุมการเปลี่ยนแปลง Active Directory ให้มี requester, approval, execution plan, verification, ticket และ audit trail ครบในเส้นทางเดียว

โปรเจกต์ต่อยอดจาก bulk AD provisioning ใน `home-lab-v2` และมีจุดเชื่อมต่อในอนาคตกับ SentinelGRC เพื่อส่ง access-review evidence และ governance finding

ปัญหาที่ MVP ตั้งใจแก้คือ account provisioning ที่ช้า, OU/group ผิด, สิทธิ์ค้างหลังย้ายแผนก, enabled account หลังพนักงานลาออก, orphan/stale account และการเปลี่ยนแปลงที่ไม่มีหลักฐานตรวจสอบย้อนหลัง

MVP รองรับ Joiner, Mover และ Leaver โดย Leaver จะ disable account และถอด managed groups แต่ไม่ลบบัญชีหรือข้อมูล

## 2. ทำงานยังไง

ระบบทำงานตาม lifecycle นี้:

```text
Request → Validate → Approve → Plan → Execute → Verify → Close
```

ข้อมูล request และ state เก็บใน SQLite การ execute จะเกิดหลัง approval เท่านั้น และค่าเริ่มต้นเป็น dry-run

กฎสำคัญ:

```text
ผู้ร้องขอ ≠ ผู้อนุมัติ
ผู้ execute ≠ ผู้ verify
ต้อง approved ก่อนสร้าง execution plan
ต้อง verification ผ่านก่อน close
```

Joiner จะสร้างแผนสำหรับ account, OU, department groups, home directory และ force password change

Mover จะถอด groups ของ department เดิม ย้าย OU และเพิ่ม groups ของ department ใหม่

Leaver จะ disable account และถอด managed group access โดยเก็บ account/data ไว้สำหรับ retention decision

สถาปัตยกรรมเต็มและ state machine อยู่ที่ [`docs/blueprint.md`](docs/blueprint.md)

This MVP demonstrates one safe identity-lifecycle workflow:

```text
Request → Validate → Approve → Plan → Execute → Verify → Close
```

The default executor is a dry-run adapter. It never changes Active Directory. A PowerShell adapter contract is included for a lab deployment with delegated permissions.

## 3. คำสั่งที่ใช้

- Joiner: create an account, place it in the department OU, assign mapped groups, and plan a home directory.
- Mover: remove old department groups and assign the new department groups.
- Leaver: disable the account and remove managed group memberships without deleting data.
- Manager/HR approval with requester/approver separation.
- Idempotent request identity and execution planning.
- SQLite persistence, tamper-evident audit events, verification, and JSON ticket export.
- Dry-run execution and post-change verification contract.

HRIS, Microsoft 365, real ticketing, SSO/MFA, and destructive account deletion are deliberately outside this MVP.

### Joiner workflow

```powershell
python -m jml.cli init --db runtime/jml.db
python -m jml.cli submit --db runtime/jml.db --request sample_data/joiner.json
python -m jml.cli approve --db runtime/jml.db --request JML-000001 --actor manager-01
python -m jml.cli plan --db runtime/jml.db --request JML-000001 --actor iam-01
python -m jml.cli execute --db runtime/jml.db --request JML-000001 --actor iam-01 --dry-run
python -m jml.cli verify --db runtime/jml.db --request JML-000001 --actor verifier-01 --passed
python -m jml.cli close --db runtime/jml.db --request JML-000001 --actor verifier-01 --reason "All post-change checks passed"
```

Mover and leaver ใช้ `sample_data/mover.json` และ `sample_data/leaver.json` ตามลำดับ

ส่งออก execution plan เพื่อรีวิวก่อน execute:

```powershell
python -m jml.cli --db runtime/jml.db plan --request JML-000001 --actor iam-01 --output runtime/plan.json
```

ดู state และ audit timeline:

```powershell
python -m jml.cli --db runtime/jml.db show --request JML-000001
```

รัน PowerShell adapter แบบปลอดภัย:

```powershell
.\powershell\Invoke-JMLPlan.ps1 -PlanPath runtime/plan.json -DryRun
```

Tickets ถูกเขียนเป็น `runtime/tickets.json` โดย local adapter เพื่อให้ตรวจสอบได้ง่าย

Run all tests:

```powershell
python -m unittest discover -v
```

## 4. หลักฐานการทำงานพิสูจน์ว่าใช้ได้

ผลการตรวจล่าสุด:

```text
6 tests — OK
Python compile check — OK
CLI end-to-end smoke test — OK
```

Test ครอบคลุม Joiner lifecycle, Mover group transition, Leaver no-delete policy, approval/verification separation, replay rejection, audit events และ ticket creation ที่ [`tests/test_jml.py`](tests/test_jml.py)

เมื่อ Joiner สำเร็จ สถานะสุดท้ายต้องเป็น `closed` และ audit timeline ต้องมี:

```text
request_submitted
ticket_created
request_approved
plan_created
execution_started
execution_completed
verification_completed
request_closed
```

หลักฐานนี้พิสูจน์ workflow และ policy ของ MVP ได้ แต่ยังไม่ใช่ live AD evidence เพราะใช้ dry-run adapter และ SQLite lab database การทดสอบถัดไปต้องทำใน isolated AD lab ด้วย delegated service account

## 5. แก้ปัญหาอะไร

โปรเจกต์นี้ลดความเสี่ยงและงาน manual ใน identity lifecycle โดยเปลี่ยนจากการแก้ AD แบบไม่มีมาตรฐานเป็น:

```text
Manual account changes
→ Approved and repeatable identity lifecycle
```

ผลกระทบที่วัดได้เมื่อเชื่อม AD จริง:

- ลดเวลาสร้าง account ใหม่
- ลด provisioning error
- ลด orphan/stale account
- ลดสิทธิ์ค้างหลังย้ายแผนก
- ลดเวลา offboarding
- เพิ่ม request ที่มี approval และ verification
- ตรวจสอบย้อนหลังได้ว่าใครทำอะไร เมื่อไหร่ และกับบัญชีใด

ความสัมพันธ์กับ SentinelGRC:

```text
JML Automation
→ ทำ approved identity change
→ สร้าง access-review evidence
→ SentinelGRC ตรวจ control
→ สร้าง governance finding เมื่อพบ orphan/stale access
```

JML เป็น operational automation layer ส่วน SentinelGRC เป็น governance and assurance layer

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
