# tests/test_oauth_deps_importable.py
def test_authlib_is_importable():
    import authlib

    assert authlib is not None
