from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JSONTicketAdapter:
    """Reviewable local ticket adapter; replace with Jira/ServiceNow later."""

    def __init__(self, path: str = "runtime/tickets.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, tickets: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(tickets, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        tickets = self._read()
        for ticket in tickets:
            if ticket["request_id"] == request["request_id"]:
                return ticket
        ticket = {
            "ticket_id": "JML-T-" + request["request_id"].split("-")[-1],
            "request_id": request["request_id"],
            "status": "open",
            "summary": f"{request['request_type'].title()} identity request for {request['username']}",
        }
        tickets.append(ticket)
        self._write(tickets)
        return ticket

    def update(self, request_id: str, status: str, resolution: str | None = None) -> dict[str, Any]:
        tickets = self._read()
        for ticket in tickets:
            if ticket["request_id"] == request_id:
                ticket["status"] = status
                if resolution:
                    ticket["resolution"] = resolution
                self._write(tickets)
                return ticket
        raise KeyError(f"ticket not found for request: {request_id}")

