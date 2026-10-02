import json

from meetlocalai import config as config_mod, diagnose

from .conftest import HDR

SECRET_TITLE = "Licenziamento Mario"


def test_redact_hides_meeting_ids_and_home():
    from pathlib import Path
    s = diagnose.redact(f"Elaborazione 2026-10-01_19-27_Licenziamento-Mario fallita in {Path.home()}/MeetLocalAI")
    assert "Licenziamento" not in s and "<riunione>" in s and str(Path.home()) not in s


def test_diagnose_reports_without_meeting_content(client, capsys, monkeypatch):
    # sul Mac il backend vero è acceso sulla stessa porta: qui si simula spento
    monkeypatch.setattr(diagnose, "backend_state", lambda port, timeout=1.5: {"running": False, "reason": "test"})
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": SECRET_TITLE, "tracks": ["tab"]}).json()
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    cfg = config_mod.load()
    folder = config_mod.data_dirs(cfg)["meetings_dir"] / md["id"]
    m = json.loads((folder / "metadata.json").read_text())
    m["performance"].update({"realtime_factor": 0.2, "summary_seconds": 40})
    (folder / "metadata.json").write_text(json.dumps(m))
    (folder / "transcript.txt").write_text("parole segretissime")
    import logging
    logging.getLogger("meetlocalai.test").error("Elaborazione %s fallita", md["id"])

    d = diagnose.collect(cfg)
    assert d["meetings"]["total"] == 1 and d["meetings"]["by_status"] == {"stopped": 1}
    assert d["meetings"]["performance"]["transcription_realtime_factor_avg"] == 0.2
    assert d["backend"]["running"] is False                 # nessun server vero nei test
    assert d["log"]["levels"].get("ERROR", 0) >= 1 and "<riunione>" in d["log"]["last_errors"][-1]
    out = diagnose.render(d) + json.dumps(d, ensure_ascii=False)
    for secret in (SECRET_TITLE, "Licenziamento", "segretissime", md["id"]):
        assert secret not in out, secret
    pr = diagnose.problems(d)
    assert any(p.startswith("Backend offline.") for p in pr)
    assert any(p.startswith("Whisper locale non disponibile.") for p in pr)
    assert any(p.startswith("Modello locale non disponibile.") for p in pr)

    assert diagnose.main([]) == 1
    printed = capsys.readouterr().out
    assert "[Componenti]" in printed and "Licenziamento" not in printed


def test_meetings_stats_tolerates_broken_metadata(tmp_path):
    (tmp_path / "2026-01-01_10-00_X").mkdir()
    (tmp_path / "2026-01-01_10-00_X" / "metadata.json").write_text("{rotto")
    (tmp_path / "vuota").mkdir()
    s = diagnose.meetings_stats(tmp_path)
    assert s["total"] == 0 and s["unreadable_metadata"] == 1
    assert diagnose.meetings_stats(tmp_path / "manca")["total"] == 0


def test_backend_state_offline_on_closed_port():
    assert diagnose.backend_state(9, timeout=0.5)["running"] is False
