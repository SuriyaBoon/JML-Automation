from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

RequestType = Literal["joiner", "mover", "leaver"]
Status = Literal[
    "submitted", "pending_approval", "approved", "planned", "executing",
    "pending_verification", "pending_closure", "verification_failed", "closed", "rejected", "failed",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Actor:
    actor_id: str
    role: str

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if self.role not in {"requester", "hr", "manager", "iam_operator", "verifier", "admin"}:
            raise ValueError(f"unsupported role: {self.role}")


@dataclass(frozen=True)
class JMLRequest:
    request_id: str
    request_type: RequestType
    employee_id: str
    username: str
    first_name: str
    last_name: str
    department: str
    manager_id: str
    requested_by: str
    effective_at: str
    old_department: str | None = None
    job_title: str | None = None
    reason: str | None = None

    def validate(self, departments: dict[str, Any]) -> None:
        for field in ("request_id", "employee_id", "username", "first_name", "last_name", "department", "manager_id", "requested_by", "effective_at"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"{field} is required")
        if self.request_type not in {"joiner", "mover", "leaver"}:
            raise ValueError("request_type must be joiner, mover, or leaver")
        if self.department not in departments:
            raise ValueError(f"unknown department: {self.department}")
        if self.request_type == "mover" and not (self.old_department or "").strip():
            raise ValueError("old_department is required for mover requests")
        if self.request_type != "mover" and self.old_department:
            raise ValueError("old_department is only valid for mover requests")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
