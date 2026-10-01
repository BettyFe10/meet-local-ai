"""Verifica del plist generato per l'avvio automatico (eseguibile anche fuori da macOS)."""

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "installer" / "launchagent.sh"


@pytest.fixture
def fake_repo(tmp_path):
    """Copia minima del repo con un 'venv' che punta al Python dei test."""
    repo = tmp_path / "repo con spazi"
    shutil.copytree(REPO / "backend" / "meetlocalai", repo / "backend" / "meetlocalai")
    shutil.copytree(REPO / "config", repo / "config")
    (repo / "installer").mkdir()
    shutil.copy(SCRIPT, repo / "installer" / "launchagent.sh")
    shutil.copy(REPO / "stop_backend.sh", repo / "stop_backend.sh")
    vbin = repo / "backend" / ".venv" / "bin"
    vbin.mkdir(parents=True)
    (vbin / "python").symlink_to(sys.executable)
    return repo


def test_plist_is_valid_and_points_to_repo(fake_repo, cfg_path):
    out = subprocess.run(["bash", str(fake_repo / "installer" / "launchagent.sh"), "print-plist"],
                         capture_output=True, text=True, env={**os.environ})
    assert out.returncode == 0, out.stderr
    pl = plistlib.loads(out.stdout.encode())
    assert pl["Label"] == "local.meetlocalai.backend"
    assert pl["ProgramArguments"] == [str(fake_repo / "backend" / ".venv" / "bin" / "python"), "-m", "meetlocalai"]
    assert pl["WorkingDirectory"] == str(fake_repo / "backend")
    assert pl["RunAtLoad"] is True
    assert pl["KeepAlive"] == {"SuccessfulExit": False}
    assert pl["ProcessType"] != "Background"
    assert pl["StandardOutPath"].endswith("backend.stdout.log")


def test_unknown_command_shows_usage():
    out = subprocess.run(["bash", str(SCRIPT), "boh"], capture_output=True, text=True)
    assert out.returncode == 2 and "install | uninstall" in out.stdout


def test_backend_writes_and_removes_pidfile(cfg_path):
    from meetlocalai import __main__ as m, config as config_mod
    pidfile = config_mod.data_dirs(config_mod.load())["temp_dir"] / "backend.pid"
    m._write_pidfile(pidfile)
    assert pidfile.read_text() == str(os.getpid())
