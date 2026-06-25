from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .api_catalog import build_api_catalog, build_openapi_document, render_api_docs
from .home_page import render_home_page
from .index_api import get_index_payload


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "MyInvestPositionAPI/0.2"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_html(render_home_page(get_index_payload(), build_api_catalog(self._base_url())))
            return
        if path == "/health":
            self._send_json({"ok": True})
            return
        if path == "/api":
            self._send_json(build_api_catalog(self._base_url()))
            return
        if path == "/api/index":
            self._send_json(get_index_payload())
            return
        if path == "/openapi.json":
            self._send_json(build_openapi_document(self._base_url()))
            return
        if path in {"/docs", "/redoc"}:
            title = "MyInvestPosition ReDoc" if path == "/redoc" else "MyInvestPosition API Docs"
            self._send_html(render_api_docs(build_api_catalog(self._base_url()), title=title))
            return
        self._send_json({"detail": "Not Found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _base_url(self) -> str:
        host = self.headers.get("Host")
        if host:
            return f"http://{host}"
        server_host, server_port = self.server.server_address[:2]
        return f"http://{server_host}:{server_port}"

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = html.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve MyInvestPosition read-only API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8018)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ApiHandler)
    print(f"Serving http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
