"""Tests for ``backend.paths`` — deterministic resolution and env-var overrides."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def _reload_paths():
    """Re-import backend.paths fresh so env vars take effect."""
    for mod in ("backend.paths", "backend.config"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
        else:
            importlib.import_module(mod)
    return sys.modules["backend.paths"]


class TestDefaults:
    def test_db_path_is_absolute(self):
        """DB_PATH must be an absolute path rooted in the project."""
        paths = _reload_paths()
        assert os.path.isabs(paths.DB_PATH)

    def test_db_path_ends_with_council_db(self):
        paths = _reload_paths()
        assert Path(paths.DB_PATH).name == "council.db"

    def test_defaults_share_data_home(self, monkeypatch):
        """Without overrides, DB, config, and agent-cwd all share the data dir."""
        # Clear any existing overrides
        for key in (
            "COUNCIL_HOME",
            "COUNCIL_DB_PATH",
            "COUNCIL_DATA_DIR",
            "COUNCIL_CONFIG_PATH",
            "COUNCIL_AGENT_CWD",
        ):
            monkeypatch.delenv(key, raising=False)

        paths = _reload_paths()
        db_parent = Path(paths.DB_PATH).parent
        assert Path(paths.COUNCIL_CONFIG_PATH).parent == db_parent
        assert Path(paths.AGENT_CWD).parent == db_parent
        assert Path(paths.DATA_DIR).parent == db_parent


class TestCouncilHomeOverride:
    def test_council_home_redirects_all(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COUNCIL_HOME", str(tmp_path))
        # Clear individual overrides so COUNCIL_HOME takes full effect
        for key in ("COUNCIL_DB_PATH", "COUNCIL_DATA_DIR",
                    "COUNCIL_CONFIG_PATH", "COUNCIL_AGENT_CWD"):
            monkeypatch.delenv(key, raising=False)

        paths = _reload_paths()

        assert Path(paths.DB_PATH).parent == tmp_path
        assert Path(paths.COUNCIL_CONFIG_PATH).parent == tmp_path
        assert Path(paths.AGENT_CWD).parent == tmp_path
        assert Path(paths.DATA_DIR).parent == tmp_path


class TestIndividualOverrides:
    def test_db_path_override(self, monkeypatch, tmp_path):
        custom = tmp_path / "custom" / "my.db"
        monkeypatch.setenv("COUNCIL_DB_PATH", str(custom))
        paths = _reload_paths()
        assert paths.DB_PATH == str(custom)

    def test_config_path_override(self, monkeypatch, tmp_path):
        custom = tmp_path / "my_config.json"
        monkeypatch.setenv("COUNCIL_CONFIG_PATH", str(custom))
        paths = _reload_paths()
        assert paths.COUNCIL_CONFIG_PATH == str(custom)

    def test_agent_cwd_override(self, monkeypatch, tmp_path):
        custom = tmp_path / "agent-sandbox"
        monkeypatch.setenv("COUNCIL_AGENT_CWD", str(custom))
        paths = _reload_paths()
        assert paths.AGENT_CWD == str(custom)

    def test_data_dir_override(self, monkeypatch, tmp_path):
        custom = tmp_path / "legacy-convs"
        monkeypatch.setenv("COUNCIL_DATA_DIR", str(custom))
        paths = _reload_paths()
        assert paths.DATA_DIR == str(custom)

    def test_individual_overrides_trump_council_home(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        custom_db = tmp_path / "elsewhere" / "council.db"
        monkeypatch.setenv("COUNCIL_HOME", str(home))
        monkeypatch.setenv("COUNCIL_DB_PATH", str(custom_db))

        paths = _reload_paths()
        # DB goes to the explicit override, not the home
        assert paths.DB_PATH == str(custom_db)
        # Other paths still use the home
        assert Path(paths.AGENT_CWD).parent == home


class TestResolutionToAbsolute:
    """Every path produced by paths.py must be absolute — no relative or
    ``~``-prefixed values survive to callers."""

    def test_relative_db_path_is_resolved(self, monkeypatch, tmp_path):
        rel = "relative/path/to/custom.db"
        monkeypatch.setenv("COUNCIL_DB_PATH", rel)
        paths = _reload_paths()
        assert os.path.isabs(paths.DB_PATH)
        assert paths.DB_PATH.endswith(rel.replace("/", os.sep))

    def test_tilde_db_path_is_expanded(self, monkeypatch):
        monkeypatch.setenv("COUNCIL_DB_PATH", "~/my-council.db")
        paths = _reload_paths()
        assert os.path.isabs(paths.DB_PATH)
        assert paths.DB_PATH.startswith(str(Path.home()))
        assert paths.DB_PATH.endswith("my-council.db")

    def test_memory_path_is_preserved(self, monkeypatch):
        """The special SQLite :memory: name must be kept verbatim, not
        resolved to an absolute filesystem path."""
        monkeypatch.setenv("COUNCIL_DB_PATH", ":memory:")
        paths = _reload_paths()
        assert paths.DB_PATH == ":memory:"

    def test_relative_council_home_is_resolved(self, monkeypatch, tmp_path):
        home = tmp_path / "relative-home"
        monkeypatch.setenv("COUNCIL_HOME", "relative-home")
        monkeypatch.delenv("COUNCIL_DB_PATH", raising=False)

        paths = _reload_paths()
        assert os.path.isabs(paths.DB_PATH)
        assert "relative-home" in paths.DB_PATH

    def test_tilde_council_home_is_expanded(self, monkeypatch):
        monkeypatch.setenv("COUNCIL_HOME", "~/council-data")
        monkeypatch.delenv("COUNCIL_DB_PATH", raising=False)

        paths = _reload_paths()
        assert os.path.isabs(paths.DB_PATH)
        assert str(Path.home()) in paths.DB_PATH
        assert "council-data" in paths.DB_PATH

    def test_relative_config_path_is_resolved(self, monkeypatch):
        monkeypatch.setenv("COUNCIL_CONFIG_PATH", "configs/my.json")
        paths = _reload_paths()
        assert os.path.isabs(paths.COUNCIL_CONFIG_PATH)

    def test_relative_agent_cwd_is_resolved(self, monkeypatch):
        monkeypatch.setenv("COUNCIL_AGENT_CWD", "sandbox")
        paths = _reload_paths()
        assert os.path.isabs(paths.AGENT_CWD)

    def test_relative_data_dir_is_resolved(self, monkeypatch):
        monkeypatch.setenv("COUNCIL_DATA_DIR", "legacy")
        paths = _reload_paths()
        assert os.path.isabs(paths.DATA_DIR)
