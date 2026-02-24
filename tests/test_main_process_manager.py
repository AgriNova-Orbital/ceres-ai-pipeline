# tests/test_main_process_manager.py
from unittest.mock import MagicMock, patch
import multiprocessing


def test_main_starts_gunicorn_and_worker_processes(monkeypatch):
    mock_process = MagicMock()
    monkeypatch.setattr(multiprocessing, "Process", mock_process)

    # We need a way to stop the main loop
    # We can patch the join methods
    with patch("multiprocessing.Process.join") as mock_join:
        from scripts.main import main

        # We need to run main in a way that doesn't block forever
        # A simple way is to make it not loop, but the plan doesn't specify how
        # We will assume it's a function we can call.
        try:
            main([])
        except TypeError:
            # The main function in the plan has no args, but our test runner might pass some.
            main()

    assert mock_process.call_count == 2
    # assert targets are correct for gunicorn and rq worker
    gunicorn_call = mock_process.call_args_list[0]
    worker_call = mock_process.call_args_list[1]

    assert "run_gunicorn" in str(gunicorn_call)
    assert "run_worker" in str(worker_call)
