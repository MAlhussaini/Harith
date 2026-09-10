import unittest

from harith_server import app


class CorsPolicyTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_proxy_allows_the_production_dashboard_origin_only(self):
        response = self.client.options(
            "/os/proxy",
            headers={"Origin": "https://harith.onrender.com"},
        )
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://harith.onrender.com",
        )
        self.assertIn("Origin", response.headers.get("Vary", ""))

    def test_proxy_does_not_use_wildcard_for_unknown_origins(self):
        response = self.client.options(
            "/os/proxy",
            headers={"Origin": "https://untrusted.example"},
        )
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_legacy_endpoints_keep_the_existing_cors_policy(self):
        response = self.client.get("/api/test")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main()
