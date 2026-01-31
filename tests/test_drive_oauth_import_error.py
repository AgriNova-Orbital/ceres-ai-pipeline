from __future__ import annotations


def test_drive_oauth_import_error_is_friendly():
    from modules.drive_oauth import _import_google

    try:
        _import_google()
    except ImportError as e:
        # In CI/dev env without google client deps, this should be a clear message.
        msg = str(e).lower()
        assert "google drive" in msg or "drive" in msg
