def test_run_script_task_executes_subprocess() -> None:
    from modules.jobs.tasks import run_script

    result = run_script(["echo", "hello"], cwd=".")
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]
