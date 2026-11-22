"""Own the local service process trees so stopping also releases workers/ports."""
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
from app.config import get_settings


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    node = shutil.which("node")
    if not node and os.name == "nt":
        # Also support the portable Node installation beside the project.
        node = next((str(p) for p in sorted(root.parent.glob("node-v*-win-x64/node.exe")) if p.is_file()), None)
    vite = root / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if not node:
        raise SystemExit("找不到 Node.js，请安装或将 node.exe 所在目录加入 PATH。")
    if not vite.is_file():
        raise SystemExit("前端依赖尚未安装，请先运行 scripts/setup.sh。")
    frontend = [node, str(vite), "--host", "127.0.0.1"]
    commands = [
        ([sys.executable, "-m", "uvicorn", "mock_api.main:app", "--host", "127.0.0.1", "--port", "8001"], root / "backend"),
        ([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], root / "backend"),
        ([sys.executable, "-m", "app.knowledge.worker"], root / "backend"),
        (frontend, root / "frontend"),
    ]
    settings = get_settings()
    if settings.dingtalk_client_id and settings.dingtalk_client_secret.get_secret_value():
        commands.extend([
            ([sys.executable, "-m", "app.im.worker"], root / "backend"),
            ([sys.executable, "im_local.py"], root / "backend"),
        ])
        print("钉钉接入已启用，将与后台一起启动。", flush=True)
    else:
        print("未填写完整钉钉凭据，仅启动 Web；IM 尚未接入。", flush=True)
    processes: list[subprocess.Popen] = []
    try:
        for command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, start_new_session=os.name != "nt"))
        print("Xiaosu: http://localhost:5173 | API: http://127.0.0.1:8000/docs | Ctrl+C to stop", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        raise SystemExit(next(process.returncode for process in processes if process.poll() is not None))
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)


if __name__ == "__main__":
    main()
