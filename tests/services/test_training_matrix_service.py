from pathlib import Path


def test_training_matrix_service_has_run_matrix_function():
    from modules.services.training_matrix_service import run_matrix

    assert callable(run_matrix)
