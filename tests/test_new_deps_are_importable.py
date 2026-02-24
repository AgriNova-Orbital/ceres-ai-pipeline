# tests/test_new_deps_are_importable.py
def test_gunicorn_and_rq_are_importable():
    import gunicorn
    import redis
    import rq

    assert gunicorn is not None
    assert redis is not None
    assert rq is not None
