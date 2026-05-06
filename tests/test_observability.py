from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import Mock


def test_init_sentry_noops_without_dsn(monkeypatch):
    from modules.observability import init_sentry

    monkeypatch.delenv("SENTRY_DSN", raising=False)

    assert init_sentry("web") is False


def test_init_sentry_configures_sdk_when_dsn_is_present(monkeypatch):
    import sentry_sdk

    from modules.observability import init_sentry

    init_mock = Mock()
    monkeypatch.setattr(sentry_sdk, "init", init_mock)
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
    integration_names = {type(x).__name__ for x in kwargs["integrations"]}
    assert integration_names == {"FlaskIntegration", "RqIntegration", "LoggingIntegration"}
    assert kwargs["enable_logs"] is True


def test_init_sentry_configures_python_logging_levels(monkeypatch):
    import sentry_sdk

    from modules.observability import init_sentry

    basic_config = Mock()
    monkeypatch.setattr(logging, "basicConfig", basic_config)
    monkeypatch.setattr(sentry_sdk, "init", Mock())
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.invalid/1")
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SENTRY_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SENTRY_BREADCRUMB_LEVEL", "DEBUG")
    monkeypatch.setenv("SENTRY_EVENT_LEVEL", "WARNING")

    assert init_sentry("web") is True

    basic_config.assert_called_once()
    assert basic_config.call_args.kwargs["level"] == logging.DEBUG
    assert basic_config.call_args.kwargs["force"] is False
    kwargs = sentry_sdk.init.call_args.kwargs
    logging_integration = next(
        item for item in kwargs["integrations"] if type(item).__name__ == "LoggingIntegration"
    )
    assert logging_integration._sentry_logs_handler.level == logging.DEBUG
    assert logging_integration._breadcrumb_handler.level == logging.DEBUG
    assert logging_integration._handler.level == logging.WARNING


def test_sentry_payload_scrubber_redacts_sensitive_fields():
    from modules.observability import scrub_sentry_payload

    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer token-123",
                "Cookie": "session=secret",
                "X-Request-ID": "req-1",
            }
        },
        "extra": {
            "refresh_token": "refresh-123",
            "nested": [{"client_secret": "google-secret"}],
        },
    }

    scrubbed = scrub_sentry_payload(event)

    assert scrubbed["request"]["headers"]["Authorization"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["Cookie"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["X-Request-ID"] == "req-1"
    assert scrubbed["extra"]["refresh_token"] == "[Filtered]"
    assert scrubbed["extra"]["nested"][0]["client_secret"] == "[Filtered]"


def test_sentry_payload_scrubber_redacts_sensitive_strings():
    from modules.observability import scrub_sentry_payload

    assert (
        scrub_sentry_payload("Authorization: Bearer token-123")
        == "Authorization: Bearer [Filtered]"
    )
    assert scrub_sentry_payload("refresh_token=refresh-123") == "refresh_token=[Filtered]"
    assert scrub_sentry_payload("client_secret: google-secret") == "client_secret: [Filtered]"
    assert scrub_sentry_payload("SENTRY_DSN=https://abc@sentry.invalid/1") == "SENTRY_DSN=[Filtered]"


def test_init_sentry_registers_event_and_log_scrubbers(monkeypatch):
    import sentry_sdk

    from modules.observability import init_sentry, scrub_sentry_log, scrub_sentry_payload

    monkeypatch.setattr(sentry_sdk, "init", Mock())
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.invalid/1")

    assert init_sentry("web") is True

    kwargs = sentry_sdk.init.call_args.kwargs
    assert kwargs["before_send"] is scrub_sentry_payload
    assert kwargs["before_send_log"] is scrub_sentry_log


def test_init_sentry_ignores_out_of_range_sample_rates(monkeypatch):
    import sentry_sdk

    from modules.observability import init_sentry

    init_mock = Mock()
    monkeypatch.setattr(sentry_sdk, "init", init_mock)
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.invalid/1")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "2")
    monkeypatch.setenv("SENTRY_PROFILES_SAMPLE_RATE", "-0.5")

    assert init_sentry("web") is True

    kwargs = init_mock.call_args.kwargs
    assert kwargs["traces_sample_rate"] == 0.0
    assert kwargs["profiles_sample_rate"] == 0.0


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
