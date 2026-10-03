"""Pytest configuration shared across all test modules.

Auto-applies a longer timeout (600s) to slow-marked tests so they don't fail
when running the full suite locally with --timeout=120. CI excludes slow tests
via `-m "not slow"`, so this hook has no CI impact.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_default_runtime(tmp_path, monkeypatch):
    """Keep default-path tests inside a per-test runtime directory."""
    runtime = tmp_path / "carrymem-runtime"
    config_dir = runtime / "config"
    monkeypatch.setenv("CARRYMEM_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CARRYMEM_DB_PATH", str(config_dir / "memories.db"))
    monkeypatch.setenv("CARRYMEM_CONFIG_FILE", str(config_dir / "config.yaml"))
    monkeypatch.setenv("CARRYMEM_DATA_PATH", str(runtime / "data"))
    monkeypatch.setenv("CARRYMEM_BACKUP_DIR", str(runtime / "backups"))
    monkeypatch.setenv("CARRYMEM_CACHE_DIR", str(runtime / "cache"))
    monkeypatch.setenv("CARRYMEM_LOG_DIR", str(runtime / "logs"))
    monkeypatch.setenv("CARRYMEM_LOCK_FILE", str(runtime / "carrymem.lock"))


def pytest_collection_modifyitems(items):
    for item in items:
        slow_marker = item.get_closest_marker("slow")
        if slow_marker:
            item.add_marker(pytest.mark.timeout(600))
