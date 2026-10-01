import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from meetlocalai import audio, bench, config as config_mod, health, transcribe

from .conftest import HDR

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg non installato")


def make_webm(path: Path, seconds: float, freq: int = 440, silent: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    src = "anullsrc=r=48000:cl=mono" if silent else f"sine=frequency={freq}:sample_rate=48000"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-t", str(seconds),
                    "-c:a", "libopus", "-b:a", "64k", str(path)], check=True)


FAKE_WHISPER_CLI = """#!/bin/bash
# finto whisper-cli: scrive un JSON nel formato di whisper.cpp
while [ $# -gt 0 ]; do case "$1" in -of) OF="$2"; shift;; -m) M="$2"; shift;; esac; shift; done
[ -f "$M" ] || { echo "model missing" >&2; exit 1; }
cat > "$OF.json" <<JSON
{"transcription":[{"offsets":{"from":0,"to":3140},"text":" Buongiorno a tutti."},
                  {"offsets":{"from":3140,"to":5000},"text":"  "},
                  {"offsets":{"from":5000,"to":7270},"text":" Iniziamo la riunione."}]}
JSON
"""


@pytest.fixture
def fake_whispercpp(tmp_path, monkeypatch, cfg_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    cli = bindir / "whisper-cli"
    cli.write_text(FAKE_WHISPER_CLI)
    cli.chmod(0o755)
    real_which = health.which
    monkeypatch.setattr(health, "which", lambda c: str(cli) if c == "whisper-cli" else real_which(c))
    models = config_mod.data_dirs(config_mod.load())["models_dir"]
    (models / "whispercpp").mkdir(parents=True, exist_ok=True)
    (models / "whispercpp" / "ggml-large-v3-turbo.bin").write_bytes(b"fake")
    return cli


# ---------- audio ----------
@needs_ffmpeg
def test_to_wav_16k_mono(tmp_path):
    src = tmp_path / "t.webm"
    make_webm(src, 2.0)
    dst = tmp_path / "t.wav"
    d = audio.to_wav(src, dst)
    assert 1.9 < d < 2.2
    with wave.open(str(dst)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)


@needs_ffmpeg
def test_mix_uses_longest_track(tmp_path):
    a, b = tmp_path / "a.webm", tmp_path / "b.webm"
    make_webm(a, 2.0, 440)
    make_webm(b, 3.0, 880)
    wa, wb = tmp_path / "a.wav", tmp_path / "b.wav"
    audio.to_wav(a, wa)
    audio.to_wav(b, wb)
    assert 2.9 < audio.mix([wa, wb], tmp_path / "m.wav") < 3.2


@needs_ffmpeg
def test_prepare_skips_missing_and_empty_tracks(tmp_path):
    meeting = tmp_path / "2026-10-01_10-00_X"
    make_webm(meeting / "raw" / "tab.webm", 1.5)
    (meeting / "raw" / "mic.webm").write_bytes(b"")
    r = audio.prepare(meeting, ["tab", "mic"], tmp_path / "work")
    assert list(r["tracks"]) == ["tab"]
    assert (meeting / "audio.wav").exists()


def test_prepare_without_audio_raises(tmp_path):
    (tmp_path / "m" / "raw").mkdir(parents=True)
    with pytest.raises(audio.AudioError, match="Nessun audio"):
        audio.prepare(tmp_path / "m", ["tab"], tmp_path / "w")


def test_missing_ffmpeg_gives_user_message(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "which", lambda c: None)
    with pytest.raises(audio.AudioError, match="FFmpeg non installato"):
        audio.to_wav(tmp_path / "x.webm", tmp_path / "x.wav")


# ---------- whisper ----------
def test_parse_whispercpp_json_skips_empty():
    segs = transcribe.parse_whispercpp_json(json.loads(
        '{"transcription":[{"offsets":{"from":0,"to":1500},"text":" Ciao"},{"offsets":{"from":1500,"to":2000},"text":" "}]}'))
    assert segs == [transcribe.Segment(0.0, 1.5, "Ciao")]


def test_mlx_not_available_outside_apple_silicon_or_without_model(tmp_path):
    ok, why = transcribe.MlxEngine("auto", tmp_path).available()
    assert ok is False and why


def test_no_engine_available_health_says_whisper_unavailable(client):
    body = client.get("/api/v1/health", headers=HDR).json()
    assert body["whisper"]["available"] is False
    assert body["whisper"]["user_message"] == "Whisper locale non disponibile."


def test_whispercpp_engine_with_fake_binary(fake_whispercpp, tmp_path):
    cfg = config_mod.load()
    eng = transcribe.select_engine(cfg, config_mod.data_dirs(cfg)["models_dir"])
    assert eng is not None and eng.name == "whispercpp"
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"")
    segs = eng.transcribe(wav, "it")
    assert [s.text for s in segs] == ["Buongiorno a tutti.", "Iniziamo la riunione."]
    assert segs[1].start == 5.0


def test_health_reports_whisper_available_with_engine(fake_whispercpp, client):
    w = client.get("/api/v1/health", headers=HDR).json()["whisper"]
    assert w == {"available": True, "engine": "whispercpp", "model": "large-v3-turbo", "user_message": None}


def test_whispercpp_missing_model_not_available(fake_whispercpp):
    cfg = config_mod.load()
    models = config_mod.data_dirs(cfg)["models_dir"]
    (models / "whispercpp" / "ggml-large-v3-turbo.bin").unlink()
    assert transcribe.select_engine(cfg, models) is None


def test_offline_env_blocks_hub_network(tmp_path):
    env = transcribe._offline_env(tmp_path)
    assert env["HF_HUB_OFFLINE"] == "1" and env["HF_HOME"].endswith("hf")


# ---------- benchmark ----------
def test_parse_max_rss():
    assert bench.parse_max_rss("  123456789  maximum resident set size\n") == 123456789
    assert bench.parse_max_rss("nulla") is None


@needs_ffmpeg
def test_bench_end_to_end_with_fake_engine(fake_whispercpp, tmp_path, capsys, monkeypatch):
    cfg = config_mod.load()
    dirs = config_mod.data_dirs(cfg)
    meeting = dirs["meetings_dir"] / "2026-10-01_10-00_Bench"
    make_webm(meeting / "raw" / "tab.webm", 30.0)
    # il benchmark lancia un processo figlio: il finto whisper-cli deve essere nel PATH
    monkeypatch.setenv("PATH", f"{fake_whispercpp.parent}:{__import__('os').environ['PATH']}")
    assert bench.main(["--engines", "whispercpp,mlx"]) == 0
    summary = json.loads(sorted(dirs["logs_dir"].glob("whisper_benchmark_*.json"))[-1].read_text())
    r = summary["engines"]["whispercpp"]["tracks"]["tab"]
    assert r["ok"] and r["segments"] == 2 and r["realtime_factor"] is not None
    assert summary["engines"]["mlx"]["available"] is False
    assert "Buongiorno" not in json.dumps(summary)          # nessun testo nei log
    assert "Buongiorno" in (dirs["temp_dir"] / "bench" / meeting.name / "whispercpp_tab.txt").read_text()
