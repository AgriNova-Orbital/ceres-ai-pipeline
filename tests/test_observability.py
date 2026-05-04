from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock


def test_init_sentry_noops_without_dsn(monkeypatch):
    from modules.observability import init_sentry

    monkeypatch.delenv("SENTRY_DSN", raising=False)

    assert init_sentry("web") is False


def test_init_sentry_configures_sdk_when_dsn_is_present(monkeypatch):
    from modules.observability import init_sentry

    init_mock = Mock()
    fake_sdk = SimpleNamespace(init=init_mock)
    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", fake_sdk)
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.invalid/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "test")
    monkeypatch.setenv("SENTRY_RELEASE", "ceres@123")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")

    assert init_sentry("worker") is True

    init_mock.assert_called_once()
    kwargs = init_mock.call_args.kwargs
    assert kwargs["dsn"] == "https://example@sentry.invalid/1"
    assert kwargs["environment"] == "test"
    assert kwargs["release"] == "ceres@123"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["server_name"] == "ceres-worker"


def test_build_new_relic_command_is_noop_without_required_env(monkeypatch):
    from modules.observability import build_new_relic_command

    monkeypatch.delenv("NEW_RELIC_LICENSE_KEY", raising=False)
    monkeypatch.setenv("NEW_RELIC_APP_NAME", "ceres-web")

    assert build_new_relic_command(["gunicorn", "app:wsgi"]) == [
        "gunicorn",
        "app:wsgi",
    ]


def test_build_new_relic_command_wraps_when_configured(monkeypatch):
    from modules.observability import build_new_relic_command

    monkeypatch.setenv("NEW_RELIC_LICENSE_KEY", "nr-license")
    monkeypatch.setenv("NEW_RELIC_APP_NAME", "ceres-web")

    assert build_new_relic_command(["gunicorn", "app:wsgi"]) == [
        "newrelic-admin",
        "run-program",
        "gunicorn",
        "app:wsgi",
    ]


def test_create_app_initializes_sentry(monkeypatch, tmp_path):
    import apps.wheat_risk_webui as webui

    calls: list[str] = []
    monkeypatch.setattr(webui, "init_sentry", lambda service_name: calls.append(service_name))

    webui.create_app(repo_root=tmp_path)

    assert calls == ["web"]


def test_worker_main_initializes_sentry(monkeypatch):
    import modules.jobs.worker as worker

    calls: list[str] = []

    class FakeWorker:
        def __init__(self, queues, connection):
            self.queues = queues
            self.connection = connection

        def work(self):
            return None

    monkeypatch.setattr(worker, "init_sentry", lambda service_name: calls.append(service_name))
    monkeypatch.setattr(
        worker, "Redis", SimpleNamespace(from_url=lambda redis_url: object())
    )
    monkeypatch.setattr(worker, "Queue", lambda name, connection: object())
    monkeypatch.setattr(worker, "Worker", FakeWorker)
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")

    worker.main()

    assert calls == ["worker"]
