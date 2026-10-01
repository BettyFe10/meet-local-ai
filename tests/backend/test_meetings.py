import json

from meetlocalai import config as config_mod, paths

from .conftest import HDR

EXAMPLE = json.loads((paths.REPO_ROOT / "docs" / "metadata.example.json").read_text(encoding="utf-8"))


def make(meetings_dir, mid, created_at, **extra):
    d = meetings_dir / mid
    d.mkdir(parents=True)
    md = {**EXAMPLE, "id": mid, "created_at": created_at, **extra}
    (d / "metadata.json").write_text(json.dumps(md), encoding="utf-8")
    return d


def mdir():
    return config_mod.data_dirs(config_mod.load())["meetings_dir"]


def test_empty_list(client):
    assert client.get("/api/v1/meetings", headers=HDR).json() == {"meetings": []}


def test_list_sorted_newest_first_with_summary_fields(client):
    make(mdir(), "2026-09-01_09-00_Vecchia", "2026-09-01T09:00:00+02:00", title="Vecchia")
    make(mdir(), "2026-09-27_10-30_Nuova", "2026-09-27T10:30:00+02:00", title="Nuova")
    ms = client.get("/api/v1/meetings", headers=HDR).json()["meetings"]
    assert [m["title"] for m in ms] == ["Nuova", "Vecchia"]
    assert set(ms[0]) == {"id", "title", "created_at", "date", "start_time", "duration_seconds", "status"}


def test_corrupt_or_inconsistent_metadata_is_skipped(client):
    d = mdir() / "2026-09-02_09-00_Rotta"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text("{ rotto", encoding="utf-8")
    make(mdir(), "2026-09-03_09-00_Incoerente", "2026-09-03T09:00:00+02:00")
    (mdir() / "2026-09-03_09-00_Incoerente" / "metadata.json").write_text(
        json.dumps({**EXAMPLE, "id": "altro"}), encoding="utf-8")
    (mdir() / "cartella-a-caso").mkdir()
    assert client.get("/api/v1/meetings", headers=HDR).json()["meetings"] == []


def test_get_meeting(client):
    make(mdir(), "2026-09-27_10-30_Riunione", "2026-09-27T10:30:00+02:00", title="Riunione")
    r = client.get("/api/v1/meetings/2026-09-27_10-30_Riunione", headers=HDR)
    assert r.status_code == 200 and r.json()["title"] == "Riunione"


def test_get_missing_or_invalid_id_is_404(client):
    for bad in ("2026-09-27_10-30_Nessuna", "..", "..%2F..%2Fetc", "nome non valido"):
        r = client.get(f"/api/v1/meetings/{bad}", headers=HDR)
        assert r.status_code == 404, bad
        assert r.json()["user_message"]
