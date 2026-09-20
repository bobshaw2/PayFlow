import unittest
from io import BytesIO
from pathlib import Path

from app import create_app
from reconciliation import ReconciliationError, reconcile


def row(transaction_id, amount="10.00", currency="USD", date="2026-09-20"):
    return {"transaction_id": transaction_id, "amount": amount, "currency": currency, "date": date}


class ReconciliationTests(unittest.TestCase):
    def test_finds_expected_statuses(self):
        result = reconcile([row("a"), row("b", "12"), row("c"), row("c")], [row("a"), row("b", "13"), row("d")])
        statuses = {item["transaction_id"]: item["status"] for item in result["transactions"]}
        self.assertEqual(statuses, {"a": "Matched", "b": "Amount mismatch", "c": "Duplicate", "d": "Missing merchant"})
        self.assertEqual(result["summary"]["issues"], 3)

    def test_rejects_invalid_amount(self):
        with self.assertRaises(ReconciliationError):
            reconcile([row("a", "not-money")], [row("a")])

    def test_rejects_blank_transaction_id(self):
        with self.assertRaises(ReconciliationError):
            reconcile([row("")], [row("a")])


class FlaskRouteTests(unittest.TestCase):
    def setUp(self):
        self.test_db = Path("work") / "payflow-test.db"
        if self.test_db.exists():
            self.test_db.unlink()
        self.client = create_app({"TESTING": True, "DATABASE": str(self.test_db)}).test_client()

    def tearDown(self):
        if self.test_db.exists():
            self.test_db.unlink()

    def signup(self):
        return self.client.post("/signup", data={"username": "demo_user", "email": "demo@example.com", "password": "safe-password"}, follow_redirects=True)

    def test_signup_unlocks_dashboard(self):
        response = self.signup()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PayFlow", response.data)
        self.assertIn(b"Amount mismatch", response.data)

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_upload_requires_csv_extension(self):
        self.signup()
        response = self.client.post("/reconcile", data={
            "merchant_file": (BytesIO(b"hello"), "merchant.txt"),
            "provider_file": (BytesIO(b"hello"), "provider.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"must be a .csv file", response.data)

    def test_saved_report_can_be_exported(self):
        self.signup()
        csv_data = b"transaction_id,amount,currency,date\nTXN-1,10.00,USD,2026-09-20\n"
        response = self.client.post("/reconcile", data={
            "merchant_file": (BytesIO(csv_data), "merchant.csv"),
            "provider_file": (BytesIO(csv_data), "provider.csv"),
        }, content_type="multipart/form-data")
        self.assertIn(b"saved to your backend history", response.data)
        self.assertIn(b"Export this saved CSV report", response.data)
        export = self.client.get("/export/1")
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"TXN-1", export.data)


if __name__ == "__main__":
    unittest.main()
