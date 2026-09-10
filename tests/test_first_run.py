"""Exercise a clean source copy without private config, media or real API calls."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="roxy-first-run-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("backend", "frontend", "scripts"):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "assets" / "defaults", self.root / "assets" / "defaults")
        shutil.copyfile(ROOT / "config.example.yaml", self.root / "config.example.yaml")
        shutil.copyfile(ROOT / "config.example.yaml", self.root / "config.yaml")
        spec = importlib.util.spec_from_file_location("first_run_backend", self.root / "backend" / "main.py")
        self.backend = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"ROXY_LLM_API_KEY": ""}):
            spec.loader.exec_module(self.backend)
        self.client = TestClient(self.backend.app)
        self.addCleanup(self.client.close)

    def configure_test_llm(self):
        self.backend.LLM_CFG.update(api_key="test-only", base_url="http://127.0.0.1:9/v1", model="test-model")

    def test_clean_copy_serves_page_and_default_assets(self):
        self.assertFalse((self.root / "voice-engine").exists())
        self.assertFalse((self.root / "assets" / "images").exists())
        for path in ("/", "/style.css", "/app.js", "/assets/images/portrait_roxy.jpg", "/assets/images/favicon.png"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertIn("image/svg+xml", self.client.get("/assets/images/portrait_roxy.jpg").headers["content-type"])
        self.assertEqual(self.client.get("/api/backgrounds").json(), {"backgrounds": []})

    def test_missing_config_returns_actionable_error_without_calling_provider(self):
        health = self.client.get("/api/health").json()
        self.assertFalse(health["llm_configured"])
        self.assertFalse(health["voice_enabled"])
        self.assertFalse(health["voice_online"])
        with patch.object(self.backend, "_call_llm", new_callable=AsyncMock) as provider:
            for path in ("/api/chat", "/api/chat/stream"):
                response = self.client.post(path, json={"message": "Hello"})
                self.assertEqual(response.status_code, 503)
                self.assertIn("ROXY_LLM_API_KEY", response.json()["error"])
            provider.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_text_chat_without_voice_has_no_translation_request(self):
        self.configure_test_llm()
        with patch.object(self.backend, "_call_llm", new_callable=AsyncMock, return_value="Hello!") as reply:
            with patch.object(self.backend, "_call_messages", new_callable=AsyncMock) as translation:
                response = self.client.post("/api/chat", json={"message": "Hello", "session_id": "smoke"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["reply"], "Hello!")
                self.assertEqual(response.json()["voice_text"], "Hello!")
                reply.assert_awaited_once()
                translation.assert_not_called()
        self.assertEqual(len(self.client.get("/api/history?session_id=smoke").json()["messages"]), 2)

    def test_stream_chat_without_voice(self):
        self.configure_test_llm()
        async def fake_stream(*args, **kwargs):
            yield "Hello "
            yield "from a clean install!"
        with patch.object(self.backend, "_call_llm_stream", fake_stream):
            response = self.client.post("/api/chat/stream", json={"message": "Hello"})
        self.assertEqual(response.status_code, 200)
        self.assertIn('"reply": "Hello from a clean install!"', response.text)
        self.assertIn("data: [DONE]", response.text)

    def test_local_portrait_overrides_placeholder_and_stays_protected(self):
        custom = self.root / "assets" / "images" / "portrait_roxy.jpg"
        custom.parent.mkdir()
        custom.write_bytes(b"test-image-content")
        self.assertEqual(self.client.get("/assets/images/portrait_roxy.jpg").content, b"test-image-content")
        self.backend.ACCESS_ENABLED = True
        self.assertEqual(self.client.get("/assets/images/portrait_roxy.jpg").status_code, 401)
        self.assertEqual(self.client.get("/assets/images/favicon.png").status_code, 200)

    def test_bootstrap_creates_config_before_installing_anything(self):
        (self.root / "config.yaml").unlink()
        result = subprocess.run([sys.executable, str(self.root / "scripts" / "launch.py"), "--check"],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual((self.root / "config.yaml").read_bytes(), (self.root / "config.example.yaml").read_bytes())
        self.assertFalse((self.root / ".venv-web").exists())


if __name__ == "__main__":
    unittest.main()
