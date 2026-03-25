from __future__ import annotations


def test_resolve_chrome_binaries_prefers_env(monkeypatch):
    from modules.testing.browser_env import resolve_chrome_binaries

    monkeypatch.setenv("CHROME_BIN", "/usr/bin/google-chrome")
    monkeypatch.setenv("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")

    result = resolve_chrome_binaries()
    assert result == {
        "chrome": "/usr/bin/google-chrome",
        "chromedriver": "/usr/bin/chromedriver",
    }
