import http.client
import json
import re
import threading
import time

import pytest

from darnleaf.imaging import InputError
from darnleaf.server import App


@pytest.fixture(scope="module")
def app():
    app = App(port=0)
    threading.Thread(target=app.serve, daemon=True).start()
    yield app
    app.shutdown()


class Client:
    def __init__(self, app, host=None):
        self.app, self.host, self.cookie = app, host, None

    def call(self, method, path, body=None, token=True, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=60)
        h = {"Host": self.host or f"127.0.0.1:{self.app.port}", **(headers or {})}
        if self.cookie:
            h["Cookie"] = self.cookie
        if token:
            h["X-Darnleaf-Token"] = self.app.token
        conn.request(method, path, body=body, headers=h)
        res = conn.getresponse()
        data = res.read()
        for k, v in res.getheaders():
            if k.lower() == "set-cookie":
                self.cookie = v.split(";")[0]
        return res.status, data, dict(res.getheaders())

    def json(self, method, path, body=None, **kw):
        status, data, _ = self.call(method, path, None if body is None else json.dumps(body).encode(), **kw)
        return status, json.loads(data or b"{}")


@pytest.fixture()
def client(app):
    c = Client(app)
    status, html, headers = c.call("GET", "/")
    assert status == 200 and re.search(rb'darnleaf-token" content="[\w-]{20,}"', html)
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    return c


def test_api_needs_the_cookie(app):
    status, _, _ = Client(app).call("GET", "/api/state")
    assert status == 403


def test_wrong_host_is_refused_even_with_cookie(app, client):
    client.host = "evil.example"
    assert client.call("GET", "/")[0] == 403
    assert client.call("GET", "/api/state")[0] == 403


def test_writes_need_the_token_header(client):
    assert client.call("POST", "/api/clear", b"{}", token=False)[0] == 403


def test_path_traversal_is_not_served(client):
    for path in ("/../server.py", "/%2e%2e/server.py", "/locales/../../server.py", "/.hidden"):
        assert client.call("GET", path)[0] in (403, 404)


def test_static_files_and_all_locales_are_served(client):
    for code in ["en", "zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de", "pt-BR"]:
        status, data, _ = client.call("GET", f"/locales/{code}.json")
        assert status == 200 and json.loads(data)["load.go"]


def test_rejects_non_pdf_and_oversized_input(client):
    status, body = client.json("POST", "/api/original", None, headers={"X-Filename": "x.pdf"})
    assert status == 400 and body["error"]
    status, data, _ = client.call("POST", "/api/rescan", b"garbage", headers={"X-Filename": "x.png"})
    assert status == 400


def test_upload_match_review_and_export_flow(client, case):
    state = client.json("POST", "/api/clear", {})[1]
    assert state["stage"] == "idle"
    status, data, _ = client.call("POST", "/api/original", case["pdf"].read_bytes(), headers={"X-Filename": "booklet.pdf"})
    assert status == 200 and json.loads(data)["pages"] == 40
    for f in case["rescans"]:
        assert client.call("POST", "/api/rescan", f.read_bytes(), headers={"X-Filename": f.name})[0] == 200
    assert client.json("POST", "/api/match", {})[0] == 200
    for _ in range(300):
        state = client.json("GET", "/api/state")[1]
        if state["stage"] != "matching":
            break
        time.sleep(0.3)
    assert state["stage"] == "review"
    # Export is refused until the unsure ones are confirmed.
    status, body = client.json("POST", "/api/export", {})
    assert status == 400 and "confirm" in body["error"]
    for p in state["proposals"]:
        if p["page"]:
            client.json("POST", "/api/choose", {"rescan": p["rescan"], "page": p["page"], "confirmed": True})
    status, receipt = client.json("POST", "/api/export", {})
    assert status == 200 and receipt["original"]["file"] == "booklet.pdf"
    status, pdf, headers = client.call("GET", "/api/download/pdf")
    assert status == 200 and pdf.startswith(b"%PDF-") and "attachment" in headers["Content-Disposition"]
    # Images behind the review screen.
    assert client.call("GET", "/api/page/0?size=200")[2]["Content-Type"] == "image/png"
    assert client.call("GET", "/api/rescan/0?size=200&turns=1")[0] == 200
    top = state["proposals"][0]
    status, png, _ = client.call("GET", f"/api/evidence/0/{top['page'] - 1}/overlay")
    assert status == 200 and png.startswith(b"\x89PNG")
    assert client.call("GET", "/api/page/999")[0] == 400


def test_negative_and_garbage_content_length_are_refused(client):
    for value in ("-5", "abc"):
        status, _, _ = client.call("POST", "/api/rescan", b"", headers={"X-Filename": "x.png", "Content-Length": value})
        assert status == 400


def test_oversized_bodies_are_refused_per_route(client):
    # A JSON route takes a few kilobytes. The declared size alone is enough to refuse, nothing is read.
    conn = http.client.HTTPConnection("127.0.0.1", client.app.port, timeout=10)
    conn.putrequest("POST", "/api/choose", skip_host=True)
    for k, v in {"Host": f"127.0.0.1:{client.app.port}", "Cookie": client.cookie, "X-Darnleaf-Token": client.app.token, "Content-Length": str(10 * 1024 * 1024)}.items():
        conn.putheader(k, v)
    conn.endheaders()
    res = conn.getresponse()
    assert res.status == 400 and b"too large" in res.read()
    conn.close()


def test_preview_size_is_clamped(client, case):
    client.json("POST", "/api/clear", {})
    client.call("POST", "/api/original", case["pdf"].read_bytes(), headers={"X-Filename": "b.pdf"})
    status, png, _ = client.call("GET", "/api/page/0?size=99999999")
    assert status == 200 and len(png) < 20_000_000
    from io import BytesIO

    from PIL import Image

    assert max(Image.open(BytesIO(png)).size) <= 2000
    assert client.call("GET", "/api/page/0?size=abc")[0] == 400


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "example.com", "::"])
def test_refuses_to_listen_beyond_loopback(host):
    with pytest.raises(InputError):
        App(host=host, port=0)


def test_ipv6_loopback_works_and_brackets_the_url():
    try:
        app = App(host="::1", port=0)
    except OSError:
        pytest.skip("no IPv6 loopback here")
    try:
        assert app.url.startswith("http://[::1]:")
        assert f"[::1]:{app.port}" in app.allowed_hosts()
        threading.Thread(target=app.serve, daemon=True).start()
        conn = http.client.HTTPConnection("::1", app.port, timeout=10)
        conn.request("GET", "/", headers={"Host": f"[::1]:{app.port}"})
        assert conn.getresponse().status == 200
    finally:
        app.shutdown()
