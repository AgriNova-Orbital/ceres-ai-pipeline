from __future__ import annotations


def test_get_redis_conn_uses_shared_fakeredis_when_enabled(monkeypatch):
    from apps import wheat_risk_webui

    monkeypatch.setenv("USE_FAKEREDIS", "1")
    conn1 = wheat_risk_webui.get_redis_conn()
    conn2 = wheat_risk_webui.get_redis_conn()

    conn1.set("hello", "world")
    assert conn2.get("hello") == "world"
