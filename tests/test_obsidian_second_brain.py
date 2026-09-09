"""
tests/test_obsidian_second_brain.py — E.D.I.T.H Obsidian İkinci Beyin & Bilgi Grafiği Test Paketi

Bu test paketi, Aşama 14 kapsamında geliştirilen Obsidian Second Brain entegrasyonunu doğrular:
1. Vault Yapılandırması ve Karşılama İndeksi
2. YAML Frontmatter, Sanitizasyon ve Wikilink Analizi
3. Atomik Konsept Notu Oluşturma ve Okuma
4. Günlük Asistan Günlüğü (Daily Note Journaling)
5. Vault İçi Semantik & Anahtar Kelime Arama
6. Web Kaynağı Arşivleme (Resources)
7. Bilgi Grafiği (Knowledge Graph) Düğüm ve Kenar Analizi
8. Sabah Brifingi Entegrasyonu
9. Telefon Köprüsü Çağrı Kaydı Entegrasyonu
10. Dashboard REST API Uç Noktaları (/api/obsidian/*)
11. Main.py Tool Execution Dispatcher
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from actions.obsidian_bridge import (
    ObsidianBridge,
    build_frontmatter,
    extract_tags,
    extract_wikilinks,
    get_obsidian_bridge,
    parse_frontmatter,
    sanitize_filename,
)
from dashboard.server import app


@pytest.fixture
def temp_vault():
    """İzole geçici test vault klasörü sağlar."""
    temp_dir = tempfile.mkdtemp(prefix="edith_test_vault_")
    vault_path = Path(temp_dir)
    bridge = ObsidianBridge(custom_vault_path=vault_path)
    # Global bridge referansını da güncelle
    with patch("actions.obsidian_bridge._global_obsidian_bridge", bridge):
        yield bridge, vault_path
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestObsidianBridgeCore:
    """ObsidianBridge çekirdek fonksiyonlarını test eder."""

    def test_vault_initialization_and_welcome_note(self, temp_vault):
        bridge, vault_path = temp_vault
        assert vault_path.exists()

        # Standart klasörlerin oluştuğunu doğrula
        for folder in ["Daily", "Concepts", "Projects", "Resources"]:
            assert (vault_path / folder).is_dir()

        welcome_file = vault_path / "000_EDITH_Second_Brain.md"
        assert welcome_file.exists()
        content = welcome_file.read_text(encoding="utf-8")
        assert "E.D.I.T.H — İkinci Beyin" in content
        assert "[[Daily]]" in content
        assert "created_by: \"EDITH\"" in content

    def test_filename_sanitization_and_helpers(self):
        assert sanitize_filename("Proje: Stark/Yapay Zeka *2026*?") == "Proje_StarkYapay_Zeka_2026"
        assert sanitize_filename("   ") == "Adsiz_Not"
        assert len(sanitize_filename("a" * 150, max_length=50)) == 50

        # Wikilink ayıklama
        md = "Bu konu [[Yapay Zeka]] ve [[Makine Öğrenmesi|ML]] ile ilgilidir."
        links = extract_wikilinks(md)
        assert links == ["Yapay Zeka", "Makine Öğrenmesi"]

        # Tag ayıklama
        tags_md = "Bugün #yapayzeka ve #edith_asistan üzerine çalıştık #python."
        tags = extract_tags(tags_md)
        assert "yapayzeka" in tags
        assert "edith_asistan" in tags
        assert "python" in tags

    def test_frontmatter_builder_and_parser(self):
        fm_text = build_frontmatter(
            title="Kuantum Hesaplama",
            tags=["kuantum", "fizik"],
            note_type="concept",
            extra={"status": "active"},
        )
        assert fm_text.startswith("---")
        assert 'title: "Kuantum Hesaplama"' in fm_text
        assert "tags: [kuantum, fizik]" in fm_text
        assert 'status: "active"' in fm_text

        parsed_fm, remaining = parse_frontmatter(fm_text + "# Başlık\nİçerik satırı")
        assert parsed_fm.get("title") == "Kuantum Hesaplama"
        assert parsed_fm.get("type") == "concept"
        assert "kuantum" in parsed_fm.get("tags", [])
        assert "# Başlık" in remaining

    def test_create_and_read_concept_note(self, temp_vault):
        bridge, vault_path = temp_vault

        res = bridge.create_note(
            title="Stark Mark 85 Zırhı",
            content="Nanoteknolojik partiküllerle üretilen son nesil savunma zırhı.",
            folder="Concepts",
            tags=["stark", "armor", "nano"],
            links=["Stark Industries", "Ark Reaktörü"],
            note_type="concept",
        )
        assert res["status"] == "ok"
        note_file = vault_path / "Concepts" / res["filename"]
        assert note_file.exists()

        # Okuma testi
        note = bridge.read_note("Stark Mark 85 Zırhı")
        assert note is not None
        assert note["title"] == "Stark Mark 85 Zırhı"
        assert note["folder"] == "Concepts"
        assert "Nanoteknolojik" in note["content"]
        assert "Stark Industries" in note["wikilinks"]
        assert "Ark Reaktörü" in note["wikilinks"]
        assert "stark" in note["tags"]

    def test_daily_note_journaling(self, temp_vault):
        bridge, vault_path = temp_vault

        # İlk ekleme: Şablon oluşur ve başlık altına eklenir
        res1 = bridge.append_daily_note(
            entry_text="İkinci beyin mimarisi tasarlandı.",
            section="Düşünceler & Hızlı Notlar",
            tags=["mimari"],
        )
        assert res1["status"] == "ok"

        # İkinci ekleme: Aynı günlüğe farklı başlık altına ekleme
        res2 = bridge.append_daily_note(
            entry_text="Sabah koşusu ve Stark donanım telemetrisi incelendi.",
            section="Sabah Brifingi & Durum",
        )
        assert res2["status"] == "ok"

        daily_content = bridge.get_today_daily_content()
        assert "## 💡 Düşünceler & Hızlı Notlar" in daily_content
        assert "İkinci beyin mimarisi tasarlandı." in daily_content
        assert "#mimari" in daily_content
        assert "## ☕ Sabah Brifingi & Durum" in daily_content
        assert "Sabah koşusu" in daily_content

    def test_search_vault(self, temp_vault):
        bridge, vault_path = temp_vault

        bridge.create_note(
            title="Python Asenkron Programlama",
            content="asyncio, loop ve event-driven mimariler modern asistanlarda kritik rol oynar.",
            folder="Concepts",
            tags=["python", "async"],
        )
        bridge.create_note(
            title="Stark Güvenlik Protokolleri",
            content="Savunma kalkanları ve Jarvis/EDITH yetkilendirme katmanları.",
            folder="Projects",
            tags=["stark", "security"],
        )

        results = bridge.search_vault("asenkron asyncio")
        assert len(results) > 0
        assert results[0]["title"] == "Python Asenkron Programlama"
        assert results[0]["folder"] == "Concepts"

        # Olmayan arama
        empty_res = bridge.search_vault("uzay gemisi hiper motoru")
        assert len(empty_res) == 0

    def test_web_resource_archiving(self, temp_vault):
        bridge, vault_path = temp_vault

        res = bridge.save_web_resource(
            url="https://arxiv.org/abs/2301.00001",
            title="Yapay Zeka ve Otonom Ajanlar Makalesi",
            summary="Ajan tabanlı LLM mimarilerinin masaüstü otomasyonundaki performansı incelenmektedir.",
            key_points=["Multimodal karar alma", "Hızlı geri bildirim döngüsü", "Yerel model desteği"],
            tags=["arxiv", "paper"],
        )
        assert res["status"] == "ok"
        note = bridge.read_note("Yapay Zeka ve Otonom Ajanlar Makalesi")
        assert note is not None
        assert note["folder"] == "Resources"
        assert "https://arxiv.org/abs/2301.00001" in note["content"]
        assert "Multimodal karar alma" in note["content"]

    def test_knowledge_graph_and_stats(self, temp_vault):
        bridge, vault_path = temp_vault

        bridge.create_note(
            title="Düğüm A",
            content="Bu not [[Düğüm B]] ve [[Düğüm C]] ile bağlantılıdır.",
            folder="Concepts",
        )
        bridge.create_note(
            title="Düğüm B",
            content="Bu not [[Düğüm C]] ile bağlantılıdır.",
            folder="Concepts",
        )
        bridge.create_note(
            title="Düğüm C",
            content="Merkezi düğüm.",
            folder="Concepts",
        )

        graph = bridge.get_graph_data()
        assert graph["node_count"] >= 3
        # Edges kontrolü
        edge_pairs = [(e["source"], e["target"]) for e in graph["edges"]]
        assert ("Düğüm_A", "Düğüm_B") in edge_pairs or ("Düğüm A", "Düğüm B") in edge_pairs or any(e["source"].startswith("Düğüm") for e in graph["edges"])

        stats = bridge.get_vault_stats()
        assert stats["total_notes"] >= 4  # 3 not + 000_EDITH_Second_Brain
        assert "Concepts" in stats["folders"]


class TestObsidianIntegrations:
    """Morning briefing ve Phone bridge günlük not entegrasyonlarını test eder."""

    def test_morning_briefing_daily_note_integration(self, temp_vault):
        bridge, vault_path = temp_vault

        with patch("actions.obsidian_bridge.get_obsidian_bridge", return_value=bridge), \
             patch("app_config.load_app_config", return_value={"obsidian": {"enabled": True, "auto_daily_briefing": True}}):
            from actions.morning_briefing import generate_morning_briefing
            md, spoken = generate_morning_briefing(force=True)

            daily_text = bridge.get_today_daily_content()
            assert "## ☕ Sabah Brifingi & Durum" in daily_text
            assert "Günaydın" in daily_text or "Tünaydın" in daily_text or "İyi akşamlar" in daily_text

    def test_phone_bridge_call_log_daily_note_integration(self, temp_vault):
        bridge, vault_path = temp_vault

        with patch("actions.obsidian_bridge.get_obsidian_bridge", return_value=bridge), \
             patch("app_config.load_app_config", return_value={"obsidian": {"enabled": True, "auto_call_log": True}}):
            from core.phone_bridge import _append_call_log
            _append_call_log(
                caller_name="Pepper Potts",
                caller_number="+905551234567",
                summary="Yönetim kurulu toplantısı saat 15:00'e alındı.",
            )

            daily_text = bridge.get_today_daily_content()
            assert "## 📞 İletişim & Çağrı Kayıtları" in daily_text
            assert "Pepper Potts" in daily_text
            assert "Yönetim kurulu toplantısı" in daily_text


class TestObsidianDashboardAPI:
    """Dashboard REST API uç noktalarını (/api/obsidian/*) test eder."""

    def test_api_obsidian_endpoints(self, temp_vault):
        bridge, vault_path = temp_vault
        client = TestClient(app)

        with patch("actions.obsidian_bridge.get_obsidian_bridge", return_value=bridge):
            # 1. Stats
            r_stats = client.get("/api/obsidian/stats")
            assert r_stats.status_code == 200
            d_stats = r_stats.json()
            assert d_stats["status"] == "ok"
            assert "total_notes" in d_stats

            # 2. Daily Get
            r_daily = client.get("/api/obsidian/daily")
            assert r_daily.status_code == 200
            assert "content" in r_daily.json()

            # 3. Post Daily Entry
            r_post_daily = client.post("/api/obsidian/daily", json={
                "entry": "REST API üzerinden günlük not eklendi.",
                "section": "Düşünceler & Hızlı Notlar",
                "tags": ["api", "test"]
            })
            assert r_post_daily.status_code == 200
            assert r_post_daily.json()["status"] == "ok"

            # 4. Post New Note
            r_post_note = client.post("/api/obsidian/note", json={
                "title": "API Test Notu",
                "content": "FastAPI ile oluşturulmuş test zettelkasten notu.",
                "folder": "Concepts",
                "tags": ["api", "fastapi"]
            })
            assert r_post_note.status_code == 200
            assert r_post_note.json()["status"] == "ok"

            # 5. Search
            r_search = client.get("/api/obsidian/search?q=FastAPI")
            assert r_search.status_code == 200
            d_search = r_search.json()
            assert d_search["status"] == "ok"
            assert d_search["count"] > 0
            assert d_search["results"][0]["title"] == "API Test Notu"

            # 6. Read
            r_read = client.get("/api/obsidian/read?title=API Test Notu")
            assert r_read.status_code == 200
            d_read = r_read.json()
            assert d_read["status"] == "ok"
            assert d_read["note"]["title"] == "API Test Notu"

            # 7. Graph
            r_graph = client.get("/api/obsidian/graph")
            assert r_graph.status_code == 200
            d_graph = r_graph.json()
            assert d_graph["status"] == "ok"
            assert "nodes" in d_graph
            assert "edges" in d_graph


class TestMainToolDispatcher:
    """main.py _execute_tool içindeki obsidian_note yönlendirmesini test eder."""

    def test_main_obsidian_tool_dispatch(self, temp_vault):
        import asyncio
        bridge, vault_path = temp_vault

        async def _test():
            with patch("actions.obsidian_bridge.get_obsidian_bridge", return_value=bridge):
                from main import EdithLive

                mock_ui = MagicMock()
                edith = EdithLive(mock_ui)

                # 1. Quick note create
                res_create = await edith._execute_tool("obsidian_note", {
                    "action": "quick_note",
                    "title": "Reaktör Mimarisi",
                    "content": "Ark reaktörü enerji çekirdeği optimizasyonu.",
                    "folder": "Projects",
                    "tags": "ark, enerji, stark",
                })
                assert "kaydedildi" in res_create.lower()
                expected_fn = sanitize_filename("Reaktör Mimarisi") + ".md"
                assert (vault_path / "Projects" / expected_fn).exists()

                # 2. Daily log
                res_daily = await edith._execute_tool("obsidian_daily_log", {
                    "content": "Masaüstü ve mobil testleri tamamlandı.",
                    "section": "Düşünceler & Hızlı Notlar",
                })
                assert "günlüğ" in res_daily.lower() or "işlendi" in res_daily.lower() or "kaydedildi" in res_daily.lower()

                # 3. Search
                res_search = await edith._execute_tool("obsidian_search", {
                    "query": "optimizasyonu",
                })
                assert "Reaktör Mimarisi" in res_search or "Reaktor_Mimarisi" in res_search

                # 4. Read
                res_read = await edith._execute_tool("obsidian_read", {
                    "title": "Reaktör Mimarisi",
                })
                assert "Reaktör Mimarisi" in res_read
                assert "Ark reaktörü" in res_read

                # 5. Stats
                res_stats = await edith._execute_tool("obsidian_stats", {})
                assert "Obsidian İkinci Beyin İstatistikleri" in res_stats

        asyncio.run(_test())
