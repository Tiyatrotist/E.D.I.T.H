"""
tests/test_dashboard_features.py — Mobil Web PWA Dashboard Genişletmesi Testleri

FastAPI TestClient ile Mobil Dashboard'un tüm uç noktalarını test eder:
  - PWA Manifest ve 5 Sekmeli Arayüz
  - Canlı Ekran Yakalama (/api/screen/snapshot) ve Vizyon Analizi (/api/screen/analyze)
  - Kamera Görüntüsü (/api/camera/snapshot)
  - Uzak Dosya Yöneticisi: Listeleme (/api/files/list), İndirme (/api/files/download), Yükleme (/api/files/upload)
  - Canlı Refakatçi & Yaşam Senkronizasyonu: /api/activity/status, /api/activity/dnd, /api/activity/snooze, /api/activity/report
  - Genişletilmiş Bilgisayar Kontrolleri: /api/command (ses, parlaklık, ekran kilidi, uygulama başlatma)
"""

import io
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from dashboard.server import app


@pytest.fixture(scope="module")
def client():
    """TestClient tekil istemcisi."""
    return TestClient(app)


class TestDashboardPWA:
    """PWA ve HTML arayüz testleri."""

    def test_pwa_manifest(self, client):
        res = client.get("/manifest.json")
        assert res.status_code == 200
        data = res.json()
        assert data.get("short_name") == "EDITH"
        assert data.get("display") == "standalone"

    def test_dashboard_html_tabs(self, client):
        res = client.get("/")
        assert res.status_code == 200
        html = res.text
        # 5 ana sekmenin HTML içinde tanımlı olduğunu doğrula
        assert 'id="tab-voice"' in html
        assert 'id="tab-screen"' in html
        assert 'id="tab-files"' in html
        assert 'id="tab-pc"' in html
        assert 'id="tab-calls"' in html
        assert "E.D.I.T.H" in html


class TestDashboardScreenVision:
    """Ekran ve kamera canlı görüntüleme testleri."""

    def test_screen_snapshot_endpoint(self, client):
        res = client.get("/api/screen/snapshot")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "image/jpeg"
        assert len(res.content) > 100

    def test_camera_snapshot_endpoint(self, client):
        res = client.get("/api/camera/snapshot")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "image/jpeg"
        assert len(res.content) > 100

    def test_screen_analyze_endpoint(self, client, monkeypatch):
        # Vision çağrısını mockla
        monkeypatch.setattr("actions.screen_vision.analyze_screen", lambda query="": "Ekranda VS Code ve Terminal açık.")
        res = client.post("/api/screen/analyze", json={"query": "Ekranda ne var?"})
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "VS Code" in data.get("analysis", "")


class TestDashboardFileManager:
    """Uzak dosya listeleme, indirme ve telefondan yükleme testleri."""

    def test_files_list_default(self, client):
        res = client.get("/api/files/list")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "current_path" in data
        assert isinstance(data.get("items"), list)

    def test_files_list_quick_jump(self, client):
        res = client.get("/api/files/list?path=Desktop")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "Desktop" in data.get("current_path", "")

    def test_file_download_and_upload(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. PC'de geçici dosya oluştur ve indir
            test_file = Path(tmpdir) / "test_download.txt"
            test_file.write_text("EDITH Mobil Dosya Transfer Testi", encoding="utf-8")

            down_res = client.get(f"/api/files/download?path={str(test_file)}")
            assert down_res.status_code == 200
            assert "EDITH Mobil Dosya Transfer Testi" in down_res.text

            # 2. Telefondan PC'ye dosya yükle
            upload_content = b"Telefondan gonderilen ornek dosya icerigi"
            files = {"file": ("uploaded_from_mobile.txt", io.BytesIO(upload_content), "text/plain")}
            data = {"target_dir": tmpdir}

            up_res = client.post("/api/files/upload", files=files, data=data)
            assert up_res.status_code == 200
            up_data = up_res.json()
            assert up_data.get("status") == "ok"

            saved_file = Path(tmpdir) / "uploaded_from_mobile.txt"
            assert saved_file.exists()
            assert saved_file.read_bytes() == upload_content


class TestDashboardActivitySupervisorSync:
    """Canlı refakatçi ve etkinlik gözetmeni senkronizasyonu."""

    def test_activity_status(self, client):
        res = client.get("/api/activity/status")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "badge" in data
        assert "activity" in data
        assert "dnd_enabled" in data

    def test_activity_dnd_toggle(self, client):
        # DND'yi aç
        res_on = client.post("/api/activity/dnd", json={"enabled": True})
        assert res_on.status_code == 200
        assert res_on.json().get("dnd_enabled") is True

        # DND'yi kapat
        res_off = client.post("/api/activity/dnd", json={"enabled": False})
        assert res_off.status_code == 200
        assert res_off.json().get("dnd_enabled") is False

    def test_activity_snooze(self, client):
        res = client.post("/api/activity/snooze", json={"minutes": 45})
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "45 dakika" in data.get("message", "")

    def test_activity_report(self, client):
        res = client.get("/api/activity/report")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "Bugünkü Etkinlik & Yaşam Raporunuz" in data.get("report", "")


class TestDashboardRemoteCommands:
    """Genişletilmiş uzaktan PC komutları testleri."""

    def test_volume_commands(self, client):
        res_vol = client.post("/api/command", json={"action": "volume_up"})
        assert res_vol.status_code == 200
        assert res_vol.json().get("status") == "ok"

    def test_desktop_and_media_commands(self, client):
        res_desk = client.post("/api/command", json={"action": "show_desktop"})
        assert res_desk.status_code == 200
        assert res_desk.json().get("status") == "ok"

        res_media = client.post("/api/command", json={"action": "media_play_pause"})
        assert res_media.status_code == 200
        assert res_media.json().get("status") == "ok"

    def test_launch_app_command(self, client, monkeypatch):
        monkeypatch.setattr("actions.open_app.open_app", lambda name="": f"{name} başlatıldı.")
        res_app = client.post("/api/command", json={"action": "launch_app", "app_name": "chrome"})
        assert res_app.status_code == 200
        data = res_app.json()
        assert "chrome" in data.get("result", "")
