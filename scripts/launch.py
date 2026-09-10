"""Windows-friendly bootstrap; requires only the Python standard library."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / ".venv-web"
ENV_PYTHON = ENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def load_user_key():
    # Double-clicked launchers may inherit an older Explorer environment.
    if os.name == "nt" and not os.environ.get("ROXY_LLM_API_KEY"):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, "ROXY_LLM_API_KEY")
                os.environ["ROXY_LLM_API_KEY"] = str(value)
        except OSError:
            pass


def prepare_environment():
    if not ENV_DIR.exists():
        print("Creating .venv-web (website dependencies only)...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(ENV_DIR)], check=True)
    probe = subprocess.run([str(ENV_PYTHON), "-c", "import fastapi, uvicorn, httpx, yaml, pydantic"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    requirements = ROOT / "requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = ENV_DIR / ".requirements.sha256"
    if probe.returncode or not stamp.exists() or stamp.read_text().strip() != fingerprint:
        print("Installing website dependencies; an Internet connection is required...", flush=True)
        subprocess.run([str(ENV_PYTHON), "-m", "pip", "install", "-r", str(requirements)], check=True)
        stamp.write_text(fingerprint, encoding="ascii")


def open_when_ready(process, url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        if process.poll() is not None:
            return
        try:
            with opener.open(url + "/api/auth_status", timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            pass
        time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    parser.add_argument("--check", action="store_true", help="Prepare and validate without starting the server")
    args = parser.parse_args()
    os.chdir(ROOT)
    if sys.version_info < (3, 9):
        print("Python 3.9 or newer is required; Python 3.12 is recommended.")
        return 1
    config = ROOT / "config.yaml"
    if not config.exists():
        shutil.copyfile(ROOT / "config.example.yaml", config)
        print("Created config.yaml. Set llm.base_url and llm.model, then set ROXY_LLM_API_KEY.")
        print("See README.md and run start.bat again. No voice engine is required.")
        return 2
    bundled_python = ROOT / "voice-engine" / "GPT-SoVITS" / "runtime" / "python.exe"
    if Path(sys.executable).resolve() == bundled_python.resolve():
        # Embedded distributions often omit venv/ensurepip. Reuse their installed
        # dependencies without changing the user's voice environment.
        try:
            import fastapi, uvicorn, httpx, yaml, pydantic
        except ImportError as error:
            raise ValueError("Bundled dependencies are incomplete. Install Python 3.12 and retry.") from error
        web_python = Path(sys.executable)
    else:
        prepare_environment()
        # Re-enter with the project's environment so PyYAML is available.
        if Path(sys.executable).resolve() != ENV_PYTHON.resolve():
            return subprocess.call([str(ENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
        web_python = ENV_PYTHON
    import yaml
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    for section in ("llm", "voice", "server"):
        if not isinstance(cfg, dict) or not isinstance(cfg.get(section), dict):
            raise ValueError(f"config.yaml needs a '{section}' section. See config.example.yaml.")
    for field in ("base_url", "model"):
        if not str(cfg["llm"].get(field, "")).strip():
            raise ValueError(f"Set llm.{field} in config.yaml.")
    port = int(cfg["server"].get("port", 8321))
    if not 1 <= port <= 65535:
        raise ValueError("server.port must be between 1 and 65535.")
    load_user_key()
    if args.check:
        print("Setup OK. Website dependencies and config.yaml are ready.")
        return 0
    if cfg["voice"].get("enabled", False):
        print("Voice is enabled: start run_voice.bat separately if you want speech.")
    host = str(cfg["server"].get("host", "127.0.0.1"))
    browser_host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    if ":" in browser_host:
        browser_host = f"[{browser_host}]"
    url = f"http://{browser_host}:{port}"
    print(f"Starting {url}. Keep this window open; Ctrl+C stops the website.", flush=True)
    process = subprocess.Popen([str(web_python), "backend/main.py"], cwd=ROOT)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(process, url), daemon=True).start()
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        print("Check your Python installation, config.yaml and network, then retry.", file=sys.stderr)
        raise SystemExit(1)
