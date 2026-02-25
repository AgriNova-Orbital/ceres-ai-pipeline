def test_evaluation_service_has_run_evaluation_function():
    from modules.services.evaluation_service import run_evaluation

    assert callable(run_evaluation)
