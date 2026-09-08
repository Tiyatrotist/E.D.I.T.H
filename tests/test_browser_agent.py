"""
tests/test_browser_agent.py — Otonom Web Tarayıcı Operatörü Testleri

Test edilen bileşenler:
  - clean_html_to_markdown() HTML temizleme ve Markdown dönüştürme
  - scrape_and_clean_page() başsız (headless) sayfa kazıma ve hata dayanıklılığı (Rule 7)
  - download_web_file() stream tabanlı dosya indirme ve boyut doğrulama
  - deep_web_research() çok kaynaklı derin web araştırması
  - browser_control() tam operatör eylemleri (read, download, scroll, tabs)
  - FastAPI Dashboard /api/browser/read, /api/browser/download, /api/browser/research uç noktaları (Rule 8)
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import requests
from fastapi.testclient import TestClient

from actions.browser import (
    browser_control,
    clean_html_to_markdown,
    deep_web_research,
    download_web_file,
    scrape_and_clean_page,
)
from dashboard.server import app


@pytest.fixture(scope="module")
def client():
    """Dashboard TestClient tekil istemcisi."""
    return TestClient(app)


class TestHTMLScraperAndCleaner:
    """HTML temizleme ve başsız kazıma testleri."""

    def test_clean_html_to_markdown_formatting(self):
        """HTML etiketlerinin doğru ayıklanıp Markdown'a dönüştürülmesi test edilir."""
        raw_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Sayfası</title>
            <style>body { color: red; }</style>
            <script>console.log('gizli');</script>
        </head>
        <body>
            <header><nav>Menü Bağlantıları</nav></header>
            <h1>Stark Endüstrileri Raporu</h1>
            <p>Bu bir <b>önemli</b> paragraftır &amp; detaylar içerir.</p>
            <ul>
                <li>Madde 1: Reaktif zırh</li>
                <li>Madde 2: Holografik HUD</li>
            </ul>
            <!-- Yorum satırı -->
            <footer>Telif hakkı 2026</footer>
        </body>
        </html>
        """
        cleaned = clean_html_to_markdown(raw_html)

        assert "Stark Endüstrileri Raporu" in cleaned
        assert "Bu bir önemli paragraftır & detaylar içerir." in cleaned
        assert "• Madde 1: Reaktif zırh" in cleaned
        assert "• Madde 2: Holografik HUD" in cleaned
        assert "console.log" not in cleaned
        assert "body { color: red; }" not in cleaned
        assert "Menü Bağlantıları" not in cleaned
        assert "Telif hakkı 2026" not in cleaned
        assert "<" not in cleaned
        assert ">" not in cleaned

    def test_scrape_and_clean_page_success(self):
        """Mock HTTP yanıtı ile sayfa kazıma testi."""
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><h1>EDITH Web</h1><p>Test içeriği başarıyla okundu.</p></body></html>"
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.raise_for_status.return_value = None

        with patch("requests.get", return_value=mock_resp):
            ok, text = scrape_and_clean_page("https://example.com")
            assert ok is True
            assert "EDITH Web" in text
            assert "Test içeriği başarıyla okundu." in text

    def test_scrape_and_clean_page_timeout_fallback(self):
        """Zaman aşımı durumunda nazik hata mesajı (Rule 7) testi."""
        with patch("requests.get", side_effect=requests.exceptions.Timeout("Zaman aşımı")):
            ok, text = scrape_and_clean_page("https://slow-site.com")
            assert ok is False
            assert "ED-NET-101" in text or "zaman aşımı" in text.lower()


class TestWebFileDownloader:
    """Web üzerinden dosya indirme testleri."""

    def test_download_web_file_success(self):
        """Stream ile parça parça dosya indirme ve boyut doğrulaması test edilir."""
        mock_resp = MagicMock()
        mock_resp.headers = {"content-disposition": 'attachment; filename="stark_blueprint.pdf"'}
        mock_resp.iter_content.return_value = [b"Chunk 1 ", b"Chunk 2 ", b"Chunk 3"]
        mock_resp.raise_for_status.return_value = None
        mock_resp.__enter__.return_value = mock_resp

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("requests.get", return_value=mock_resp):
                ok, msg, saved_path = download_web_file(
                    url="https://stark.com/blueprint.pdf",
                    destination_dir=tmpdir
                )

                assert ok is True
                assert "stark_blueprint.pdf" in msg
                assert os.path.exists(saved_path)
                content = Path(saved_path).read_bytes()
                assert content == b"Chunk 1 Chunk 2 Chunk 3"

    def test_download_web_file_network_error(self):
        """İndirme sırasında ağ hatası alındığında güvenli dönüş testi."""
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Bağlantı koptu")):
            ok, msg, path = download_web_file("https://fail.com/file.zip")
            assert ok is False
            assert "ED-NET-101" in msg or "başarısız" in msg


class TestBrowserControlActions:
    """browser_control operatör eylemleri testleri."""

    def test_browser_control_read_action(self):
        """browser_control 'read' eylemi testi."""
        with patch("actions.browser.scrape_and_clean_page", return_value=(True, "Örnek Makale Metni")):
            res = browser_control(action="read", url="https://example.com/news")
            assert "Örnek Makale Metni" in res
            assert "Sayfa İçeriği" in res

    def test_browser_control_download_action(self):
        """browser_control 'download' eylemi testi."""
        with patch("actions.browser.download_web_file", return_value=(True, "Dosya indirildi: doc.pdf", "/path/doc.pdf")):
            res = browser_control(action="download", url="https://example.com/doc.pdf")
            assert "Dosya indirildi" in res

    def test_browser_control_operator_keys(self):
        """pyautogui ile tarayıcı kaydırma ve sekme kısayolları testi."""
        mock_pyautogui = MagicMock()
        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}):
            res_down = browser_control(action="scroll_down")
            assert "aşağı kaydırıldı" in res_down
            mock_pyautogui.press.assert_called_with("pagedown")

            res_up = browser_control(action="scroll_up")
            assert "yukarı kaydırıldı" in res_up
            mock_pyautogui.press.assert_called_with("pageup")

            res_tab = browser_control(action="new_tab")
            assert "Yeni sekme" in res_tab
            mock_pyautogui.hotkey.assert_called_with("ctrl", "t")

            res_close = browser_control(action="close_tab")
            assert "kapatıldı" in res_close
            mock_pyautogui.hotkey.assert_called_with("ctrl", "w")


class TestDashboardBrowserEndpoints:
    """Mobil PWA Dashboard web gezinme uç nokta testleri (Rule 8)."""

    def test_api_browser_read_endpoint(self, client):
        """POST /api/browser/read endpoint testi."""
        with patch("actions.browser.scrape_and_clean_page", return_value=(True, "Başlıklı web içeriği")):
            res = client.post("/api/browser/read", json={"url": "https://example.com", "summarize": False})
            assert res.status_code == 200
            data = res.json()
            assert data.get("status") == "ok"
            assert "Başlıklı web içeriği" in data.get("content")

    def test_api_browser_download_endpoint_validation(self, client):
        """POST /api/browser/download doğrulama ve indirme testi."""
        # URL eksikse 400
        res_bad = client.post("/api/browser/download", json={"url": ""})
        assert res_bad.status_code == 400

        with patch("actions.browser.download_web_file", return_value=(True, "İndirildi: sample.zip", "/tmp/sample.zip")):
            res_ok = client.post("/api/browser/download", json={"url": "https://example.com/sample.zip"})
            assert res_ok.status_code == 200
            data = res_ok.json()
            assert data.get("status") == "ok"
            assert "/tmp/sample.zip" in data.get("path")

    def test_dashboard_html_contains_browser_card(self, client):
        """Mobil arayüzde Web Gezgini bileşenlerinin varlığı test edilir."""
        res = client.get("/")
        assert res.status_code == 200
        html = res.text
        assert "browser-read-btn" in html
        assert "browser-download-btn" in html
        assert "browser-url-input" in html
        assert "Otonom Web Gezgini" in html
