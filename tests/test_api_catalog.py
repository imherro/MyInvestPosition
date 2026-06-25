from __future__ import annotations

import unittest

from app.api_catalog import build_api_catalog, build_openapi_document, render_api_docs


class ApiCatalogTests(unittest.TestCase):
    def test_build_api_catalog_contains_required_sections(self) -> None:
        catalog = build_api_catalog("http://127.0.0.1:8018/")

        self.assertEqual(catalog["system"]["name"], "MyInvestPosition")
        self.assertEqual(catalog["base_url"], "http://127.0.0.1:8018")
        self.assertEqual(catalog["docs"]["docs"], "/docs")
        self.assertEqual(catalog["docs"]["redoc"], "/redoc")
        self.assertEqual(catalog["docs"]["openapi"], "/openapi.json")
        self.assertEqual(catalog["total_endpoints"], 8)
        self.assertTrue(catalog["safety"]["read_only"])
        self.assertTrue(catalog["safety"]["no_recompute"])
        self.assertTrue(catalog["safety"]["no_writes"])
        self.assertTrue(catalog["safety"]["no_trading"])
        self.assertIn("/api/index", {item["path"] for group in catalog["groups"] for item in group["endpoints"]})

    def test_every_public_endpoint_has_required_metadata(self) -> None:
        catalog = build_api_catalog()

        for group in catalog["groups"]:
            for endpoint in group["endpoints"]:
                self.assertIn(endpoint["method"], {"GET"})
                self.assertTrue(endpoint["path"].startswith("/"))
                self.assertIsInstance(endpoint["purpose"], str)
                self.assertIsInstance(endpoint["parameters"], list)
                self.assertIsInstance(endpoint["response"], str)
                self.assertTrue(endpoint["read_only"])

    def test_openapi_document_lists_catalog_endpoint(self) -> None:
        spec = build_openapi_document("http://127.0.0.1:8018")

        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertEqual(spec["info"]["title"], "MyInvestPosition")
        self.assertIn("/api", spec["paths"])
        self.assertIn("get", spec["paths"]["/api"])
        self.assertTrue(spec["paths"]["/api"]["get"]["x-read-only"])

    def test_render_api_docs_returns_html(self) -> None:
        html = render_api_docs(build_api_catalog(), title="Docs")

        self.assertIn("<!doctype html>", html)
        self.assertIn("安全边界", html)
        self.assertIn("/api/index", html)


if __name__ == "__main__":
    unittest.main()
