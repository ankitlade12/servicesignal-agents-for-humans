"""Run and supervise one API/worker pair, preserving deployment environment settings."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

os.chdir(Path(__file__).resolve().parent.parent)
load_dotenv()
port = os.environ.setdefault("SERVICESIGNAL_PORT", "8017")
os.environ.setdefault("PUBLISHER_ORIGIN", f"http://127.0.0.1:{port}")
os.environ.setdefault("PUBLIC_ORIGIN", f"http://localhost:{port}")
children = []


def stop(signum=None, frame=None):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
exit_code = 0
try:
    children.append(subprocess.Popen([sys.executable, "-m", "app.worker"]))
    children.append(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                os.getenv("SERVICESIGNAL_HOST", "127.0.0.1"),
                "--port",
                port,
            ]
        )
    )
    while all(p.poll() is None for p in children):
        time.sleep(0.5)
    exit_code = next((p.returncode for p in children if p.returncode is not None), 1)
except KeyboardInterrupt:
    pass
finally:
    for p in children:
        if p.poll() is None:
            p.terminate()
    for p in children:
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
raise SystemExit(exit_code)
