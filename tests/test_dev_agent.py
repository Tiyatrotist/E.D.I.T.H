"""
tests/test_dev_agent.py — Otonom Geliştirici ve Kod Ajanı (Dev Agent) Testleri

Test edilen bileşenler:
  - AST sözdizimi linting (geçerli/geçersiz Python ve JSON)
  - Güvenli dosya yazımı ve dizin yönetimi
  - İzole alt süreç çalıştırma ve zaman aşımı koruması
  - AutonomousDevAgent planlama ve tam döngü yürütme
  - Hata durumunda Kendi Kendini Düzeltme Döngüsü (Self-Healing Loop)
  - Maksimum iterasyon sınırı (sonsuz döngü koruması)
  - CodeHelper 'lint' niyet entegrasyonu
  - FastAPI Dashboard /api/dev/status ve /api/dev/run uç noktaları (Rule 8)
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from actions.code_helper import code_helper
from actions.dev_agent import (
    AutonomousDevAgent,
    DevAgentResult,
    get_dev_agent_status,
    run_dev_agent,
)
from dashboard.server import app


@pytest.fixture(scope="module")
def client():
    """Dashboard TestClient tekil istemcisi."""
    return TestClient(app)


class TestDevAgentCore:
    """Otonom Dev Ajanı temel yetenek testleri."""

    def test_lint_code_python(self):
        """Python kodunun AST linting doğrulaması test edilir."""
        agent = AutonomousDevAgent()

        # Geçerli Python kodu
        valid_py = "def topla(a, b):\n    return a + b\n\nprint(topla(2, 3))\n"
        ok, msg = agent.lint_code(valid_py, "python")
        assert ok is True
        assert "hatasız" in msg.lower()

        # Geçersiz sözdizimi
        invalid_py = "def bozuk_fonksiyon(:\n    pass"
        ok2, msg2 = agent.lint_code(invalid_py, "python")
        assert ok2 is False
        assert "sözdizimi hatası" in msg2.lower()

    def test_lint_code_json(self):
        """JSON formatının linting doğrulaması test edilir."""
        agent = AutonomousDevAgent()

        valid_json = '{"name": "EDITH", "active": true, "version": 2.0}'
        ok, msg = agent.lint_code(valid_json, "json")
        assert ok is True

        invalid_json = '{"name": "EDITH", unquoted_key: 123}'
        ok2, msg2 = agent.lint_code(invalid_json, "json")
        assert ok2 is False

    def test_safe_file_write(self):
        """Çalışma dizininde güvenli dosya ve alt klasör oluşturma test edilir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousDevAgent(project_dir=tmpdir)
            target = agent.write_file("src/utils/calc.py", "x = 42\n")

            assert target.exists()
            assert target.read_text(encoding="utf-8") == "x = 42\n"
            assert "src\\utils\\calc.py" in agent.files_created or "src/utils/calc.py" in agent.files_created

    def test_run_process_success_and_timeout(self):
        """Alt süreç çalıştırma ve timeout denetimi test edilir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousDevAgent(project_dir=tmpdir)
            script = agent.write_file("hello.py", "print('EDITH_DEV_SUCCESS')")

            code, out = agent.run_process([sys.executable, str(script)], timeout=5)
            assert code == 0
            assert "EDITH_DEV_SUCCESS" in out

            # Timeout testi
            sleep_script = agent.write_file("sleep.py", "import time; time.sleep(10)")
            code2, out2 = agent.run_process([sys.executable, str(sleep_script)], timeout=1)
            assert code2 == -1
            assert "zaman aşımına uğradı" in out2


class TestDevAgentExecutionLoop:
    """Otonom görev yürütme ve Self-Healing döngü testleri."""

    def test_plan_and_execute_clean_run(self):
        """İlk denemede hatasız çalışan görev döngüsü test edilir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousDevAgent(project_dir=tmpdir)

            plan_json = '{"summary": "Toplama", "files": [{"path": "calc.py", "description": "hesaplayıcı", "language": "python"}], "entry_point": "calc.py"}'
            clean_code = "print('TOPLAM_SONUC:', 10 + 25)"

            # LLM plan ve kod yanıtlarını taklit et
            with patch.object(agent, "_call_llm_sync", side_effect=[plan_json, f"```python\n{clean_code}\n```"]):
                res = agent.plan_and_execute("Basit bir toplama scripti yaz")

                assert res.success is True
                assert res.iterations == 1
                assert "TOPLAM_SONUC: 35" in res.final_output
                assert any("calc.py" in f for f in res.files_created)
                md = res.to_markdown()
                assert "Otonom Dev Ajanı: Görev Başarıyla Tamamlandı" in md

    def test_self_healing_correction_loop(self):
        """İlk çalıştırmada runtime hatası alan ve ikinci iterasyonda düzelten döngü test edilir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousDevAgent(project_dir=tmpdir, max_iterations=3)

            plan_json = '{"files": [{"path": "math_ops.py", "description": "bolme islemi"}], "entry_point": "math_ops.py"}'
            broken_code = "print('SONUC:', 10 / 0)  # ZeroDivisionError"
            healed_code = "print('SONUC:', 10 / 2)  # Duzeltildi"

            responses = [
                plan_json,
                f"```python\n{broken_code}\n```",  # İlk kod üretimi
                f"```python\n{healed_code}\n```",  # Self-healing düzeltmesi
            ]

            with patch.object(agent, "_call_llm_sync", side_effect=responses):
                res = agent.plan_and_execute("Bölme işlemi yapan script yaz")

                assert res.success is True
                assert res.iterations == 2
                assert "SONUC: 5.0" in res.final_output

    def test_max_iterations_exhausted_guard(self):
        """Maksimum iterasyon dolduğunda güvenli şekilde durma test edilir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousDevAgent(project_dir=tmpdir, max_iterations=2)

            plan_json = '{"files": [{"path": "always_fail.py"}], "entry_point": "always_fail.py"}'
            broken_code = "raise RuntimeError('Kalıcı Hata')"

            responses = [
                plan_json,
                f"```python\n{broken_code}\n```",
                f"```python\n{broken_code}\n```",
            ]

            with patch.object(agent, "_call_llm_sync", side_effect=responses):
                res = agent.plan_and_execute("Sonsuz hata görevi")

                assert res.success is False
                assert res.iterations == 2
                assert res.error is not None
                assert "tamamlanamadı" in res.error or "giderilemedi" in res.error


class TestCodeHelperAndEndpoints:
    """CodeHelper lint entegrasyonu ve FastAPI Dev Agent uç nokta testleri."""

    def test_code_helper_lint_valid(self):
        """code_helper lint geçerli kod testi."""
        res = code_helper(intent="lint", code="a = 1\nb = 2\nprint(a + b)", language="python")
        assert "✅" in res
        assert "Hatasız" in res

    def test_code_helper_lint_syntax_error(self):
        """code_helper lint sözdizimi hata yakalama testi."""
        res = code_helper(intent="lint", code="def invalid_func(\n    pass", language="python")
        assert "❌" in res
        assert "Sözdizimi Hatası" in res

    def test_api_dev_status_endpoint(self, client):
        """GET /api/dev/status testi."""
        res = client.get("/api/dev/status")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "logs" in data

    def test_api_dev_run_endpoint_validation(self, client):
        """POST /api/dev/run görev doğrulama testi."""
        # Boş görev 400 döner
        res = client.post("/api/dev/run", json={"task": ""})
        assert res.status_code == 400

        # Geçerli görev başlatılır
        res2 = client.post("/api/dev/run", json={"task": "Fibonacci hesaplayıcı yaz"})
        assert res2.status_code == 200
        assert res2.json().get("status") == "started"

    def test_dashboard_html_contains_dev_agent_card(self, client):
        """Mobil Dashboard HTML arayüzünde Dev Agent kartının varlığı test edilir."""
        res = client.get("/")
        assert res.status_code == 200
        html = res.text
        assert "dev-agent-run-btn" in html
        assert "dev-task-input" in html
        assert "Otonom Geliştirici" in html
