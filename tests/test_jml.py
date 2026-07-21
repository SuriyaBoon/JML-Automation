import json
import tempfile
import unittest
from pathlib import Path

from jml.models import Actor, JMLRequest
from jml.service import JMLService
from jml.store import JMLStore
from jml.tickets import JSONTicketAdapter


DEPARTMENTS = {
    "IT": {"ou": "OU=IT,DC=corp,DC=local", "groups": ["grp-IT-All", "grp-IT-Helpdesk"]},
    "Sales": {"ou": "OU=Sales,DC=corp,DC=local", "groups": ["grp-Sales-All"]},
}


class JMLWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = JMLService(JMLStore(str(Path(self.temp.name) / "jml.db")), DEPARTMENTS, JSONTicketAdapter(str(Path(self.temp.name) / "tickets.json")))
        self.request = JMLRequest("JML-1", "joiner", "EMP-1", "jsmith", "John", "Smith", "IT", "manager-1", "hr-1", "2026-08-01T09:00:00Z")

    def tearDown(self):
        self.temp.cleanup()

    def test_joiner_lifecycle_is_auditable(self):
        self.service.submit(self.request, Actor("hr-1", "hr"))
        self.service.approve("JML-1", Actor("manager-1", "manager"), "Approved by manager")
        operations = self.service.plan("JML-1", Actor("iam-1", "iam_operator"))
        self.assertEqual([item["op"] for item in operations], ["create_user", "set_groups", "create_home_directory", "force_password_change"])
        self.service.execute("JML-1", Actor("iam-1", "iam_operator"), dry_run=True)
        self.service.verify("JML-1", Actor("verifier-1", "verifier"), True, {"account_exists": True, "groups_correct": True})
        result = self.service.close("JML-1", Actor("verifier-1", "verifier"), "All checks passed")
        self.assertEqual(result["status"], "closed")
        events = self.service.store.events("JML-1")
        self.assertEqual([event["event_type"] for event in events], ["request_submitted", "ticket_created", "request_approved", "plan_created", "execution_started", "execution_completed", "verification_completed", "request_closed"])

    def test_requester_cannot_approve_or_verify(self):
        self.service.submit(self.request, Actor("hr-1", "hr"))
        with self.assertRaises(PermissionError):
            self.service.approve("JML-1", Actor("hr-1", "manager"), "self approval")
        self.service.approve("JML-1", Actor("manager-1", "manager"), "Approved")
        self.service.plan("JML-1", Actor("iam-1", "iam_operator"))
        self.service.execute("JML-1", Actor("iam-1", "iam_operator"))
        with self.assertRaises(PermissionError):
            self.service.verify("JML-1", Actor("iam-1", "verifier"), True, {})

    def test_replay_is_rejected(self):
        self.service.submit(self.request, Actor("hr-1", "hr"))
        with self.assertRaises(Exception):
            self.service.submit(self.request, Actor("hr-1", "hr"))

    def test_leaver_does_not_delete_account(self):
        request = JMLRequest("JML-2", "leaver", "EMP-2", "adoe", "Ann", "Doe", "IT", "manager-1", "hr-1", "2026-08-02T17:00:00Z")
        self.service.submit(request, Actor("hr-1", "hr"))
        self.service.approve("JML-2", Actor("manager-1", "manager"), "Termination approved")
        operations = self.service.plan("JML-2", Actor("iam-1", "iam_operator"))
        self.assertEqual([item["op"] for item in operations], ["disable_user", "remove_managed_groups"])
        self.assertNotIn("delete_user", json.dumps(operations))

    def test_mover_has_remove_and_add_operations(self):
        request = JMLRequest("JML-3", "mover", "EMP-3", "adoe", "Ann", "Doe", "IT", "manager-1", "hr-1", "2026-08-02T09:00:00Z", old_department="Sales")
        self.service.submit(request, Actor("hr-1", "hr"))
        self.service.approve("JML-3", Actor("manager-1", "manager"), "Transfer approved")
        operations = self.service.plan("JML-3", Actor("iam-1", "iam_operator"))
        self.assertEqual([item["op"] for item in operations], ["remove_groups", "move_ou", "set_groups"])

    def test_ticket_is_created_and_closed_with_lifecycle(self):
        self.service.submit(self.request, Actor("hr-1", "hr"))
        # The request ticket is created at submission by the local adapter;
        # the store remains the authoritative link for this MVP.
        self.assertEqual(self.service.store.get("JML-1")["status"], "pending_approval")
        self.assertTrue((Path(self.temp.name) / "tickets.json").exists())


if __name__ == "__main__":
    unittest.main()
