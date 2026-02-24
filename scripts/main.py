# scripts/main.py
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from apps.wheat_risk_webui import create_app


def run_gunicorn():
    subprocess.run(
        [
            "gunicorn",
            "--bind",
            "0.0.0.0:5055",
            "--workers",
            "4",
            "apps.wheat_risk_webui:create_app()",
        ]
    )


def run_worker():
    subprocess.run([sys.executable, "-m", "modules.jobs.worker"])


def main(argv=None):
    p1 = multiprocessing.Process(target=run_gunicorn)
    p2 = multiprocessing.Process(target=run_worker)

    p1.start()
    p2.start()

    p1.join()
    p2.join()


if __name__ == "__main__":
    main()
