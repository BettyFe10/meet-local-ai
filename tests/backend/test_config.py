import json

import pytest

from meetlocalai import config as config_mod, paths

from .conftest import write_cfg


def test_example_config_is_valid():
    cfg = json.loads(paths.EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    config_mod.validate(cfg)


def test_missing_config_is_created_from_example(tmp_path):
    p = tmp_path / "sub" / "config.json"
    cfg = config_mod.load(p)
    assert p.exists()
    assert cfg["backend"]["port"] == 8765


def test_user_values_override_defaults_and_missing_keys_are_filled(tmp_path):
    p = write_cfg(tmp_path, {"backend": {"port": 9999}})
    cfg = config_mod.load(p)
    assert cfg["backend"]["port"] == 9999
    assert cfg["backend"]["host"] == "127.0.0.1"          # dal default
    assert cfg["summary"]["not_determinable_text"]        # sezione non presente nel file utente


@pytest.mark.parametrize("override", [
    {"backend": {"host": "0.0.0.0"}},
    {"backend": {"port": 80}},
    {"backend": {"port": "8765"}},
    {"llm": {"base_url": "https://api.example.com"}},
    {"llm": {"base_url": "http://192.168.1.10:11434"}},
    {"backend": {"allowed_extension_ids": "abc"}},
])
def test_invalid_configs_are_rejected(tmp_path, override):
    with pytest.raises(config_mod.ConfigError):
        config_mod.load(write_cfg(tmp_path, override))


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"])
def test_loopback_llm_urls_are_accepted(tmp_path, url):
    config_mod.load(write_cfg(tmp_path, {"llm": {"base_url": url}}))


def test_invalid_json_gives_readable_error(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{ non json", encoding="utf-8")
    with pytest.raises(config_mod.ConfigError, match="JSON"):
        config_mod.load(p)


def test_no_absolute_user_paths_in_example():
    txt = paths.EXAMPLE_CONFIG.read_text(encoding="utf-8")
    assert "/Users/" not in txt and "/home/" not in txt
