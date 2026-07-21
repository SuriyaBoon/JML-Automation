from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import Actor, JMLRequest
from .service import JMLService
from .store import JMLStore


ROOT = Path(__file__).resolve().parents[1]


def service(db: str) -> JMLService:
    departments = json.loads((ROOT / "config" / "departments.json").read_text(encoding="utf-8"))
    return JMLService(JMLStore(db), departments)


def request_from_file(path: str) -> JMLRequest:
    return JMLRequest(**json.loads(Path(path).read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel JML Automation MVP")
    parser.add_argument("--db", default="runtime/jml.db")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    submit = commands.add_parser("submit"); submit.add_argument("--request", required=True); submit.add_argument("--actor", default=None); submit.add_argument("--role", default="hr")
    for name in ("approve", "reject"):
        command = commands.add_parser(name); command.add_argument("--request", required=True); command.add_argument("--actor", required=True); command.add_argument("--reason", default="MVP review completed"); command.add_argument("--role", default="manager")
    plan = commands.add_parser("plan"); plan.add_argument("--request", required=True); plan.add_argument("--actor", required=True); plan.add_argument("--role", default="iam_operator"); plan.add_argument("--output")
    execute = commands.add_parser("execute"); execute.add_argument("--request", required=True); execute.add_argument("--actor", required=True); execute.add_argument("--role", default="iam_operator"); execute.add_argument("--dry-run", action="store_true")
    verify = commands.add_parser("verify"); verify.add_argument("--request", required=True); verify.add_argument("--actor", required=True); verify.add_argument("--role", default="verifier"); verify.add_argument("--passed", action="store_true")
    close = commands.add_parser("close"); close.add_argument("--request", required=True); close.add_argument("--actor", required=True); close.add_argument("--role", default="verifier"); close.add_argument("--reason", default="Verification passed")
    show = commands.add_parser("show"); show.add_argument("--request", required=True)
    args = parser.parse_args()
    svc = service(args.db)
    if args.command == "init":
        print(json.dumps({"status": "ready", "database": args.db}, indent=2)); return 0
    if args.command == "submit":
        request = request_from_file(args.request); actor = Actor(args.actor or request.requested_by, args.role); result = svc.submit(request, actor)
    elif args.command in {"approve", "reject"}:
        actor = Actor(args.actor, args.role); result = getattr(svc, args.command)(args.request, actor, args.reason)
    elif args.command == "plan":
        result = svc.plan(args.request, Actor(args.actor, args.role))
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif args.command == "execute":
        result = svc.execute(args.request, Actor(args.actor, args.role), args.dry_run)
    elif args.command == "verify":
        result = svc.verify(args.request, Actor(args.actor, args.role), args.passed, {"mvp_mode": True})
    elif args.command == "close":
        result = svc.close(args.request, Actor(args.actor, args.role), args.reason)
    else:
        result = {"request": svc.store.get(args.request), "events": svc.store.events(args.request)}
    print(json.dumps(result, indent=2, default=str)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
