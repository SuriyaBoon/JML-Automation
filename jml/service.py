from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Actor, JMLRequest
from .store import JMLStore
from .tickets import JSONTicketAdapter


class JMLService:
    def __init__(self, store: JMLStore, departments: dict[str, Any], tickets: JSONTicketAdapter | None = None) -> None:
        self.store = store
        self.departments = departments
        self.tickets = tickets or JSONTicketAdapter()

    def submit(self, request: JMLRequest, actor: Actor) -> dict[str, Any]:
        if actor.actor_id != request.requested_by and actor.role not in {"admin", "hr"}:
            raise PermissionError("actor cannot submit for this requester")
        request.validate(self.departments)
        self.store.add_request(request)
        self.store.audit(request.request_id, actor.actor_id, actor.role, "request_submitted", request.to_dict())
        self.store.set_status(request.request_id, "pending_approval")
        ticket = self.tickets.create(request.to_dict())
        self.store.upsert_ticket(ticket["ticket_id"], request.request_id, ticket["status"], ticket["summary"])
        self.store.audit(request.request_id, actor.actor_id, actor.role, "ticket_created", ticket)
        return self.store.get(request.request_id)

    def approve(self, request_id: str, actor: Actor, reason: str) -> dict[str, Any]:
        request = self.store.get(request_id)
        if actor.role not in {"manager", "hr", "admin"}:
            raise PermissionError("only manager, HR, or admin can approve")
        if actor.actor_id == request["requested_by"]:
            raise PermissionError("requester cannot approve the same request")
        if request["status"] != "pending_approval":
            raise ValueError(f"request cannot be approved from {request['status']}")
        if not reason.strip():
            raise ValueError("approval reason is required")
        self.store.add_approval(request_id, actor.actor_id, "approved", reason)
        self.store.set_status(request_id, "approved")
        self.store.audit(request_id, actor.actor_id, actor.role, "request_approved", {"reason": reason})
        return self.store.get(request_id)

    def reject(self, request_id: str, actor: Actor, reason: str) -> dict[str, Any]:
        request = self.store.get(request_id)
        if actor.role not in {"manager", "hr", "admin"}:
            raise PermissionError("only manager, HR, or admin can reject")
        if not reason.strip():
            raise ValueError("rejection reason is required")
        if request["status"] != "pending_approval":
            raise ValueError(f"request cannot be rejected from {request['status']}")
        self.store.add_approval(request_id, actor.actor_id, "rejected", reason)
        self.store.set_status(request_id, "rejected")
        self.tickets.update(request_id, "rejected", reason)
        self.store.upsert_ticket("JML-T-" + request_id.split("-")[-1], request_id, "rejected", reason)
        self.store.audit(request_id, actor.actor_id, actor.role, "request_rejected", {"reason": reason})
        return self.store.get(request_id)

    def plan(self, request_id: str, actor: Actor) -> list[dict[str, Any]]:
        request = self.store.get(request_id)
        if actor.role not in {"iam_operator", "admin"}:
            raise PermissionError("only IAM operator or admin can create a plan")
        if request["status"] != "approved":
            raise ValueError(f"request cannot be planned from {request['status']}")
        current = self.departments[request["department"]]
        operations: list[dict[str, Any]] = []
        kind = request["request_type"]
        if kind == "joiner":
            operations = [{"op": "create_user", "username": request["username"], "first_name": request["first_name"], "last_name": request["last_name"], "job_title": request["job_title"], "ou": current["ou"]}, {"op": "set_groups", "username": request["username"], "groups": current["groups"]}, {"op": "create_home_directory", "username": request["username"]}, {"op": "force_password_change", "username": request["username"]}]
        elif kind == "mover":
            old = self.departments[request["old_department"]]
            operations = [{"op": "remove_groups", "username": request["username"], "groups": old["groups"]}, {"op": "move_ou", "username": request["username"], "ou": current["ou"]}, {"op": "set_groups", "username": request["username"], "groups": current["groups"]}]
        elif kind == "leaver":
            operations = [{"op": "disable_user", "username": request["username"]}, {"op": "remove_managed_groups", "username": request["username"]}]
        self.store.add_plan(request_id, operations)
        self.store.set_status(request_id, "planned")
        self.store.audit(request_id, actor.actor_id, actor.role, "plan_created", {"operations": operations})
        return operations

    def execute(self, request_id: str, actor: Actor, dry_run: bool = True) -> list[dict[str, Any]]:
        request = self.store.get(request_id)
        if actor.role not in {"iam_operator", "admin"}:
            raise PermissionError("only IAM operator or admin can execute")
        if request["status"] != "planned":
            raise ValueError(f"request cannot execute from {request['status']}")
        operations = self.store.get_plan(request_id)
        self.store.set_status(request_id, "executing")
        self.store.audit(request_id, actor.actor_id, actor.role, "execution_started", {"dry_run": dry_run, "operations": operations})
        results = [{**operation, "status": "planned" if dry_run else "requires_powershell_adapter"} for operation in operations]
        self.store.add_execution(request_id, actor.actor_id, dry_run, results)
        self.store.set_status(request_id, "pending_verification")
        self.store.audit(request_id, actor.actor_id, actor.role, "execution_completed", {"dry_run": dry_run, "results": results})
        return results

    def verify(self, request_id: str, actor: Actor, passed: bool, checks: dict[str, Any]) -> dict[str, Any]:
        request = self.store.get(request_id)
        if actor.role not in {"verifier", "admin"}:
            raise PermissionError("only verifier or admin can verify")
        if actor.actor_id in {request.get("requested_by"), self.store.last_execution_actor(request_id)}:
            raise PermissionError("requester or executor cannot verify the same request")
        if request["status"] != "pending_verification":
            raise ValueError(f"request cannot verify from {request['status']}")
        result = "passed" if passed else "failed"
        self.store.add_verification(request_id, actor.actor_id, result, checks)
        self.store.set_status(request_id, "pending_closure" if passed else "verification_failed")
        self.tickets.update(request_id, "verification_pending" if passed else "blocked", result)
        self.store.upsert_ticket("JML-T-" + request_id.split("-")[-1], request_id, "verification_pending" if passed else "blocked", result)
        self.store.audit(request_id, actor.actor_id, actor.role, "verification_completed", {"result": result, "checks": checks})
        return self.store.get(request_id)

    def close(self, request_id: str, actor: Actor, reason: str) -> dict[str, Any]:
        request = self.store.get(request_id)
        if actor.role not in {"verifier", "admin"}:
            raise PermissionError("only verifier or admin can close")
        if request["status"] != "pending_closure":
            raise ValueError(f"request cannot close from {request['status']}")
        if not reason.strip():
            raise ValueError("closure reason is required")
        self.store.set_status(request_id, "closed")
        self.tickets.update(request_id, "closed", reason)
        self.store.upsert_ticket("JML-T-" + request_id.split("-")[-1], request_id, "closed", reason)
        self.store.audit(request_id, actor.actor_id, actor.role, "request_closed", {"reason": reason})
        return self.store.get(request_id)
