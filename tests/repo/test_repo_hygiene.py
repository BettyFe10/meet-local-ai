"""Controlli sul repository: niente dati personali, niente file di dati/segreti tracciati, script validi."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEXT_EXT = {".py", ".js", ".mjs", ".json", ".md", ".sh", ".html", ".css", ".txt", ".ini", ""}
FORBIDDEN_EXT = {".wav", ".webm", ".ogg", ".mp3", ".m4a", ".pem", ".key", ".bin", ".gguf", ".safetensors", ".log", ".crx"}
ALLOWED_EMAILS: set[str] = set()
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")
USER_PATH_RE = re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)")
ALLOWED_USERS = {"utente", "<nome>", "alex"}


def tracked():
    if not shutil.which("git") or not (REPO / ".git").exists():
        pytest.skip("git non disponibile")
    out = subprocess.run(["git", "-C", str(REPO), "ls-files", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout
    return [REPO / p for p in out.splitlines() if (REPO / p).is_file()]


def texts():
    for p in tracked():
        if p.suffix in TEXT_EXT:
            yield p, p.read_text(encoding="utf-8", errors="replace")


def test_no_data_or_secret_files_tracked():
    bad = [str(p.relative_to(REPO)) for p in tracked()
           if p.suffix.lower() in FORBIDDEN_EXT or p.name == "config.json" or p.name.startswith(("env_report", "diagnose_report"))]
    assert not bad, bad


def test_no_personal_data_in_tracked_files():
    me = os.environ.get("USER") or ""
    found = []
    for p, txt in texts():
        rel = str(p.relative_to(REPO))
        for m in EMAIL_RE.finditer(txt):
            if m.group(0).lower() not in ALLOWED_EMAILS and not m.group(0).lower().endswith(("@example.com", "@2x.png")):
                found.append((rel, m.group(0)))
        for m in USER_PATH_RE.finditer(txt):
            if m.group(1) not in ALLOWED_USERS and not rel.startswith("tests/"):
                found.append((rel, m.group(0)))
        if "PRIVATE KEY" in txt and not rel.startswith("tests/"):
            found.append((rel, "PRIVATE KEY"))
        if len(me) >= 4 and me not in ("root", "runner") and re.search(rf"\b{re.escape(me)}\b", txt, re.I):
            found.append((rel, "nome utente del sistema"))
    assert not found, found


def test_no_remote_urls_in_extension_code():
    """L'estensione parla solo con 127.0.0.1 (Meet compare solo come pattern di host)."""
    bad = []
    for p, txt in texts():
        if "extension" in p.parts and p.suffix in {".js", ".html", ".css"}:
            for m in re.finditer(r"https?://[^\s\"'`)<]+", txt):
                u = m.group(0)
                if not u.startswith(("http://127.0.0.1", "https://meet.google.com", "http://www.w3.org")):
                    bad.append((p.name, u))
    assert not bad, bad


def test_shell_scripts_are_executable_and_parse():
    scripts = [p for p in tracked() if p.suffix in (".sh", ".command")]
    assert {"diagnose.sh", "start_backend.sh", "stop_backend.sh", "install_mac.sh", "uninstall_mac.sh",
            "Installa Meet Local AI.command"} <= {p.name for p in scripts}
    for p in scripts:
        assert os.access(p, os.X_OK), f"{p.name} non eseguibile"
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, f"{p.name}: {r.stderr}"
        assert p.read_text().startswith("#!/bin/bash"), p.name


def test_checkpoint_files_exist():
    for f in ("PROJECT_STATUS.md", "TODO.md", "DECISIONS.md", "TEST_RESULTS.md", "ARCHITECTURE.md", "THIRD_PARTY.md", "README.md"):
        assert (REPO / f).is_file(), f


def test_python_requirements_are_pinned():
    for f in ("requirements.txt", "requirements-dev.txt"):
        for line in (REPO / "backend" / f).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "-r")):
                assert "==" in line, f"{f}: {line}"


def test_installer_help_and_safety():
    for name in ("install_mac.sh", "uninstall_mac.sh"):
        r = subprocess.run(["bash", str(REPO / name), "--help"], capture_output=True, text=True)
        assert r.returncode == 0 and "Uso:" in r.stdout, name
        assert subprocess.run(["bash", str(REPO / name), "--boh"], capture_output=True).returncode == 2
    un = (REPO / "uninstall_mac.sh").read_text()
    assert "Meetings" not in "".join(l for l in un.splitlines() if "rm -rf" in l)      # mai cancellare le riunioni
    assert un.count("rm -rf") == 2
    assert (REPO / "SETUP-NEW-COMPUTER.md").is_file()


def test_install_ram_tiers_match_backend():
    """Le fasce di RAM dell'installer devono coincidere con quelle del backend."""
    from meetlocalai import llm
    sh = (REPO / "install_mac.sh").read_text()
    for gb, model in ((32, llm.recommended_model(32)), (16, llm.recommended_model(16)), (8, llm.recommended_model(8))):
        assert model in sh, (gb, model)
    assert sorted(t[0] for t in llm.RAM_TIERS if t[0] > 0) == [12, 24]


def test_documentation_is_complete_and_links_resolve():
    docs = ["README.md", "SETUP-NEW-COMPUTER.md", "docs/GUIDA-UTENTE.md", "docs/PRIVACY.md", "docs/LIMITI-NOTI.md",
            "docs/BACKUP.md", "docs/GITHUB.md", "installer/README.md"]
    for d in docs:
        p = REPO / d
        assert p.is_file(), d
        for m in re.finditer(r"\]\(([^)#]+?\.(?:md|json|sh))\)", p.read_text(encoding="utf-8")):
            target = (p.parent / m.group(1)).resolve()
            assert target.is_file(), f"{d}: collegamento rotto → {m.group(1)}"
    guide = (REPO / "docs/GUIDA-UTENTE.md").read_text(encoding="utf-8")
    for msg in ("Backend offline.", "Whisper locale non disponibile.", "Modello locale non disponibile."):
        assert msg in guide
    limits = (REPO / "docs/LIMITI-NOTI.md").read_text(encoding="utf-8")
    assert "NON TESTATO" in limits
