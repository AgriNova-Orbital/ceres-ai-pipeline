import subprocess


def run_script(cmd: list[str], cwd: str) -> dict:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
