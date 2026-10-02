import json
import sys

from meetlocalai import config as config_mod, files

from .conftest import HDR
from .test_summarize import GOOD


def dirs():
    return config_mod.data_dirs(config_mod.load())


def stopped_meeting(client, title="File", with_docs=False):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": title}).json()
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    folder = dirs()["meetings_dir"] / md["id"]
    if with_docs:
        (folder / "summary.md").write_text(f"# RIUNIONE — {title}\n\n- Data: x\n\n{GOOD}\n", encoding="utf-8")
        (folder / "transcript.md").write_text("# Trascrizione — File\n\n**[00:00:01] Microfono locale:**  \nCiao.\n", encoding="utf-8")
        (folder / "transcript.txt").write_text("[00:00:01] Microfono locale:\nCiao.\n\n", encoding="utf-8")
    return md["id"], folder


def test_delete_moves_to_internal_trash_when_system_trash_unavailable(client):
    mid, folder = stopped_meeting(client)
    r = client.delete(f"/api/v1/meetings/{mid}", headers=HDR)
    assert r.status_code == 200 and r.json()["deleted"] is True and r.json()["where"] == "fallback"
    assert not folder.exists()
    kept = dirs()["data_root"] / "Cestino" / mid
    assert (kept / "metadata.json").exists()                      # recuperabile: nessuna cancellazione definitiva
    assert client.get(f"/api/v1/meetings/{mid}", headers=HDR).status_code == 404
    assert client.get("/api/v1/meetings", headers=HDR).json()["meetings"] == []
    assert client.delete(f"/api/v1/meetings/{mid}", headers=HDR).status_code == 404


def test_delete_uses_macos_trash_api(client, monkeypatch):
    import subprocess
    mid, folder = stopped_meeting(client)
    calls = []

    def fake_run(cmd, **k):
        calls.append(cmd)
        import shutil
        shutil.rmtree(cmd[-1])                                     # simula lo spostamento nel Cestino
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.delenv("MEETLOCALAI_NO_SYSTEM_TRASH")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", fake_run)
    r = client.delete(f"/api/v1/meetings/{mid}", headers=HDR).json()
    assert r["where"] == "trash" and r["user_message"] == "Riunione spostata nel Cestino."
    assert calls[0][:3] == ["/usr/bin/osascript", "-l", "JavaScript"] and calls[0][-1] == str(folder)
    assert "trashItemAtURL" in calls[0][4]


def test_cannot_delete_while_recording(client):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "Viva"}).json()
    r = client.delete(f"/api/v1/meetings/{md['id']}", headers=HDR)
    assert r.status_code == 409 and r.json()["error_code"] == "still_recording"


def test_same_name_twice_in_internal_trash_does_not_overwrite(tmp_path):
    fb = tmp_path / "Cestino"
    for _ in range(2):
        f = tmp_path / "2026-10-01_10-00_X"
        f.mkdir()
        (f / "a.txt").write_text("x")
        assert files.trash(f, fb) == "fallback"
    assert sorted(p.name for p in fb.iterdir()) == ["2026-10-01_10-00_X", "2026-10-01_10-00_X_2"]


def test_export_md_and_txt(client):
    mid, folder = stopped_meeting(client, with_docs=True)
    r = client.get(f"/api/v1/meetings/{mid}/export?format=md", headers=HDR)
    assert r.status_code == 200 and "## TL;DR" in r.text and "# Trascrizione" in r.text
    assert (dirs()["exports_dir"] / f"{mid}.md").read_text() == r.text
    t = client.get(f"/api/v1/meetings/{mid}/export?format=txt", headers=HDR).text
    assert "=== VERBALE ===" in t and "=== TRASCRIZIONE ===" in t and "##" not in t and "Ciao." in t
    assert client.get(f"/api/v1/meetings/{mid}/export?format=pdf", headers=HDR).status_code == 422


def test_export_without_documents(client):
    mid, _ = stopped_meeting(client)
    assert "Sintesi non disponibile" in client.get(f"/api/v1/meetings/{mid}/export?format=md", headers=HDR).text
    assert "Nessun contenuto disponibile" in client.get(f"/api/v1/meetings/{mid}/export?format=txt", headers=HDR).text


def test_storage(client):
    stopped_meeting(client, with_docs=True)
    s = client.get("/api/v1/storage", headers=HDR).json()
    assert s["meetings_count"] == 1 and s["meetings_bytes"] > 0 and s["free_bytes"] > 0
    assert isinstance(s["low_space"], bool)


def test_cleanup_temp_only_touches_meeting_work_dirs(tmp_path):
    (tmp_path / "2026-10-01_10-00_X").mkdir()
    (tmp_path / "llm_bench").mkdir()
    (tmp_path / "backend.pid").write_text("1")
    assert files.cleanup_temp(tmp_path) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["backend.pid", "llm_bench"]


def test_delete_allowed_from_extension_origin(client):
    ext = "chrome-extension://" + config_mod.load()["backend"]["allowed_extension_ids"][0]
    pre = client.options("/api/v1/meetings/x", headers={"Origin": ext, "Access-Control-Request-Method": "DELETE"})
    assert "DELETE" in pre.headers["access-control-allow-methods"]
