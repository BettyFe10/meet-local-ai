"""Controlli statici dell'estensione Chrome (senza browser)."""

import base64
import hashlib
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EXT = REPO / "extension"
MANIFEST = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
PAGES = ["popup.html", "dashboard.html", "meeting.html", "settings.html"]


def ext_id_from_key(key_b64: str) -> str:
    h = hashlib.sha256(base64.b64decode(key_b64)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in h)


def test_manifest_v3_basics():
    assert MANIFEST["manifest_version"] == 3
    assert MANIFEST["background"]["service_worker"] == "service_worker.js"
    assert MANIFEST["action"]["default_popup"] == "popup.html"


def test_permissions_are_minimal():
    assert set(MANIFEST["permissions"]) <= {"storage", "tabCapture", "offscreen"}
    assert set(MANIFEST["host_permissions"]) == {"https://meet.google.com/*", "http://127.0.0.1/*"}


def test_stable_id_matches_backend_allowlist():
    cfg = json.loads((REPO / "config" / "config.example.json").read_text(encoding="utf-8"))
    assert ext_id_from_key(MANIFEST["key"]) in cfg["backend"]["allowed_extension_ids"]


def test_no_private_key_in_repo():
    for f in REPO.rglob("*"):
        if ".git" in f.parts or ".venv" in f.parts or not f.is_file() or f.stat().st_size > 2_000_000:
            continue
        try:
            txt = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert "PRIVATE KEY-----" not in txt or f.name.startswith("test_"), f


def test_referenced_files_exist():
    refs = [MANIFEST["background"]["service_worker"], MANIFEST["action"]["default_popup"], MANIFEST["options_page"]]
    refs += list(MANIFEST["icons"].values()) + list(MANIFEST["action"]["default_icon"].values())
    for r in refs:
        assert (EXT / r).is_file(), r


class _Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.inline, self.styles = [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            else:
                self.inline += 1
        if tag == "link" and a.get("rel") == "stylesheet":
            self.styles.append(a["href"])


@pytest.mark.parametrize("page", PAGES)
def test_pages_exist_without_inline_scripts(page):
    s = _Scan()
    s.feed((EXT / page).read_text(encoding="utf-8"))
    assert s.inline == 0, "MV3 CSP vieta gli script inline"
    for ref in s.scripts + s.styles:
        assert not ref.startswith("http"), ref
        assert (EXT / ref).is_file(), ref


def test_no_remote_endpoints_in_js():
    allowed = ("http://127.0.0.1", "https://meet.google.com")
    for js in EXT.rglob("*.js"):
        for url in re.findall(r"https?://[^\s\"'`)]+", js.read_text(encoding="utf-8")):
            assert url.startswith(allowed), f"{js.name}: {url}"


def test_api_client_always_sends_client_header():
    assert '"X-MeetLocalAI": "1"' in (EXT / "lib" / "api.js").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_js_syntax(tmp_path):
    for js in EXT.rglob("*.js"):
        copy = tmp_path / (js.stem + ".mjs")
        copy.write_text(js.read_text(encoding="utf-8"), encoding="utf-8")
        r = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
        assert r.returncode == 0, f"{js.name}: {r.stderr}"
