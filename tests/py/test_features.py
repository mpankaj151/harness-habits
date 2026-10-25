import json

import pytest

from harness_habits import features

ENV_KEYS = ["HH_FEATURE_OUTPUT_GUARD", "CLAUDE_PLUGIN_OPTION_OUTPUT_GUARD", "HH_FEATURE_IDLE_COMPACTION"]


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def write_features(tmp_path, data):
    d = tmp_path / "harness-habits"
    d.mkdir()
    (d / "features.json").write_text(json.dumps(data))


def test_defaults():
    assert features.enabled("output-guard") is True
    assert features.enabled("idle-compaction") is False
    assert features.enabled("tool-budget") is False


def test_unknown_key_is_false():
    assert features.enabled("nope") is False


def test_file_overrides_default(clean):
    write_features(clean, {"output-guard": False, "idle-compaction": True})
    assert features.enabled("output-guard") is False
    assert features.enabled("idle-compaction") is True


def test_invalid_file_falls_back(clean):
    d = clean / "harness-habits"
    d.mkdir()
    (d / "features.json").write_text("{not json")
    assert features.enabled("output-guard") is True


def test_hh_env_overrides_file(clean, monkeypatch):
    write_features(clean, {"output-guard": False})
    monkeypatch.setenv("HH_FEATURE_OUTPUT_GUARD", "1")
    assert features.enabled("output-guard") is True


@pytest.mark.parametrize("val", ["0", "false", "off", "OFF", "False"])
def test_off_values(monkeypatch, val):
    monkeypatch.setenv("HH_FEATURE_OUTPUT_GUARD", val)
    assert features.enabled("output-guard") is False


def test_other_values_are_on(monkeypatch):
    monkeypatch.setenv("HH_FEATURE_IDLE_COMPACTION", "yes")
    assert features.enabled("idle-compaction") is True


def test_plugin_option_wins_over_hh(monkeypatch):
    monkeypatch.setenv("HH_FEATURE_OUTPUT_GUARD", "1")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_OUTPUT_GUARD", "false")
    assert features.enabled("output-guard") is False
