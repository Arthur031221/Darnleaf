"""Local web server. It binds to loopback, serves the UI and a small JSON API for one session."""

from __future__ import annotations

import ipaddress
import json
import mimetypes
import secrets
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import __version__, limits
from .imaging import InputError
from .session import Session

WEB = resources.files("darnleaf").joinpath("web")
JSON_LIMIT = 64 * 1024
BODY_LIMIT = limits.MAX_ORIGINAL_BYTES + 1024
COOKIE = "darnleaf_token"
MAX_PREVIEW = 2000


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _disposition(name: str) -> str:
    """Header values must be Latin-1, so non-ASCII names go in the RFC 5987 form with an ASCII fallback."""
    ascii_name = "".join(c if c.isascii() and (c.isalnum() or c in "._- ") else "_" for c in name)
    if ascii_name == name:
        return f'attachment; filename="{name}"'
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


def _int(value: str, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


class App:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        if not is_loopback(host):
            raise InputError(f"refusing to listen on {host}: Darnleaf only serves 127.0.0.0/8, ::1 and localhost")
        self.token = secrets.token_urlsafe(24)
        self.session = Session()
        self.lock = threading.Lock()
        server = ThreadingHTTPServer
        if ":" in host:
            server = type("ThreadingHTTPServer6", (ThreadingHTTPServer,), {"address_family": socket.AF_INET6})
        self.httpd = server((host.strip("[]"), port), self._handler())
        self.httpd.daemon_threads = True
        self.host, self.port = host.strip("[]"), self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{self._authority(self.host)}:{self.port}/"

    @staticmethod
    def _authority(host: str) -> str:
        return f"[{host}]" if ":" in host else host

    def allowed_hosts(self) -> set[str]:
        names = {self._authority(self.host), "localhost", "127.0.0.1", "[::1]"} if self.host in ("localhost", "127.0.0.1", "::1") else {self._authority(self.host)}
        return {f"{name}:{self.port}" for name in names}

    def preload(self, original: Path, rescans: list[Path], use_ocr: bool = False) -> None:
        """Load files given on the command line and start matching, so the browser opens on the review."""
        session = self.session

        def read(path: Path) -> bytes:
            try:
                return path.read_bytes()
            except OSError as exc:
                raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc

        session.set_original(original.name, read(original))
        for path in rescans:
            session.add_rescan(path.name, read(path))
        session.start(use_ocr)

    def serve(self) -> None:
        try:
            self.httpd.serve_forever()
        finally:
            self.session.close()

    def shutdown(self) -> None:
        self.httpd.shutdown()

    def _handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = f"Darnleaf/{__version__}"

            def log_message(self, *args) -> None:  # keep the terminal quiet
                pass

            # ----- plumbing ------------------------------------------------------

            def _send(self, status: int, body: bytes, kind: str, extra: dict[str, str] | None = None) -> None:
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
                )
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, payload, status: int = 200) -> None:
                self._send(status, json.dumps(payload).encode(), "application/json")

            def _fail(self, status: int, message: str) -> None:
                self._json({"error": message}, status)

            def _cookie_ok(self) -> bool:
                jar = self.headers.get("Cookie", "")
                return any(part.strip() == f"{COOKIE}={app.token}" for part in jar.split(";"))

            def _guard(self, write: bool) -> bool:
                if self.headers.get("Host", "") not in app.allowed_hosts():
                    self._fail(HTTPStatus.FORBIDDEN, "unexpected Host header")
                    return False
                if write:
                    if self.headers.get("X-Darnleaf-Token") != app.token or not self._cookie_ok():
                        self._fail(HTTPStatus.FORBIDDEN, "missing session token")
                        return False
                elif not self._cookie_ok():
                    self._fail(HTTPStatus.FORBIDDEN, "missing session cookie")
                    return False
                return True

            def _body(self, limit: int = JSON_LIMIT) -> bytes:
                try:
                    size = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    raise InputError("bad Content-Length") from None
                if size < 0:
                    raise InputError("bad Content-Length")
                if size > limit:
                    self.close_connection = True
                    raise InputError("upload is too large")
                return self.rfile.read(size)

            # ----- routes --------------------------------------------------------

            def do_GET(self) -> None:
                url = urlparse(self.path)
                if self.headers.get("Host", "") not in app.allowed_hosts():
                    return self._fail(HTTPStatus.FORBIDDEN, "unexpected Host header")
                if not url.path.startswith("/api/"):
                    return self._static(url.path)
                if not self._guard(False):
                    return
                s, q = app.session, parse_qs(url.query)
                try:
                    if url.path == "/api/state":
                        return self._json(s.state())
                    parts = url.path.split("/")[2:]
                    if parts[0] == "page":
                        return self._send(200, s.page_image(int(parts[1]), _int(q.get("size", ["700"])[0], 64, MAX_PREVIEW)), "image/png")
                    if parts[0] == "rescan":
                        return self._send(200, s.rescan_image(int(parts[1]), _int(q.get("size", ["700"])[0], 64, MAX_PREVIEW), int(q.get("turns", ["0"])[0])), "image/png")
                    if parts[0] == "evidence":
                        return self._send(200, s.evidence_image(int(parts[1]), int(parts[2]), parts[3]), "image/png")
                    if parts[0] == "download":
                        name, data, kind = s.download(parts[1])
                        return self._send(200, data, kind, {"Content-Disposition": _disposition(name)})
                    return self._fail(404, "not found")
                except (InputError, ValueError, IndexError) as exc:
                    self._fail(400, str(exc))

            def do_POST(self) -> None:
                url = urlparse(self.path)
                if not self._guard(True):
                    return
                s = app.session
                try:
                    name = unquote(self.headers.get("X-Filename", "upload"))
                    if url.path == "/api/original":
                        return self._json(s.set_original(name, self._body(BODY_LIMIT)))
                    if url.path == "/api/rescan":
                        return self._json({"added": s.add_rescan(name, self._body(limits.MAX_REPLACEMENT_BYTES + 1024))})
                    payload = json.loads(self._body() or b"{}")
                    if url.path == "/api/clear":
                        s.clear_rescans()
                    elif url.path == "/api/sample":
                        s.load_sample()
                    elif url.path == "/api/match":
                        s.start(bool(payload.get("ocr")))
                    elif url.path == "/api/cancel":
                        s.cancel_match()
                    elif url.path == "/api/choose":
                        page = payload.get("page")
                        s.set_choice(int(payload["rescan"]), None if page is None else int(page) - 1, bool(payload.get("confirmed")))
                    elif url.path == "/api/export":
                        return self._json(s.export(payload.get("mode", "align"), bool(payload.get("drop_annotations"))))
                    else:
                        return self._fail(404, "not found")
                    self._json(s.state())
                except (InputError, KeyError, ValueError, TypeError) as exc:
                    self._fail(400, str(exc))
                except json.JSONDecodeError:
                    self._fail(400, "invalid JSON")

            def _static(self, path: str) -> None:
                rel = "index.html" if path in ("", "/") else path.lstrip("/")
                if ".." in rel.split("/") or rel.startswith("."):
                    return self._fail(404, "not found")
                node = WEB.joinpath(rel)
                if not node.is_file():
                    return self._fail(404, "not found")
                data = node.read_bytes()
                extra = {}
                if rel == "index.html":
                    data = data.replace(b"__TOKEN__", app.token.encode())
                    extra["Set-Cookie"] = f"{COOKIE}={app.token}; Path=/; HttpOnly; SameSite=Strict"
                kind = mimetypes.guess_type(rel)[0] or "application/octet-stream"
                self._send(200, data, kind + ("; charset=utf-8" if kind.startswith("text/") or kind.endswith("json") else ""), extra)

        return Handler
