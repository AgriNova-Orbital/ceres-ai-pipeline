from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from pathlib import Path


def test_job_locking_prevents_duplicate_tasks(monkeypatch, tmp_path: Path):
    from apps.wheat_risk_webui import create_app

    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "dummy-id-1"

    # We will simulate redis behavior using a dict
    fake_redis_store = {}

    class FakeRedis:
        def get(self, key):
            return fake_redis_store.get(key)

        def set(self, key, value, ex=None):
            fake_redis_store[key] = value

        def keys(self, pattern):
            # very basic pattern matching for testing
            if pattern == "lock:*":
                return [k for k in fake_redis_store.keys() if k.startswith("lock:")]
            return []

    mock_redis = FakeRedis()

    monkeypatch.setattr("apps.wheat_risk_webui.get_redis_conn", lambda: mock_redis)
    monkeypatch.setattr("apps.wheat_risk_webui.get_queue_conn", lambda: mock_queue)

    app = create_app(repo_root=tmp_path)
    # Ensure TESTING is true so flash messages are recorded without requiring a full session environment in pytest
    app.config["TESTING"] = True
    client = app.test_client()

    # First call: Should succeed and set the lock
    fake_redis_store.clear()
    mock_queue.enqueue.return_value = mock_job

    with client:
        resp1 = client.post(
            "/run/build",
            data={"action": "build_level", "level": "1"},
            follow_redirects=True,
        )
        assert resp1.status_code == 200
        mock_queue.enqueue.assert_called_once()
        assert "lock:build:build_level:1" in fake_redis_store
        assert fake_redis_store["lock:build:build_level:1"] == "dummy-id-1"

    # Second call: Should be blocked by the lock
    mock_queue.reset_mock()
    with client:
        resp2 = client.post(
            "/run/build",
            data={"action": "build_level", "level": "1"},
            follow_redirects=True,
        )
        assert resp2.status_code == 200
        mock_queue.enqueue.assert_not_called()
        assert b"is already running" in resp2.data
