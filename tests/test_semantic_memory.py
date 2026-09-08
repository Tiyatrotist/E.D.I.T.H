"""
tests/test_semantic_memory.py — Kesintisiz Bağlam ve Semantik Bellek Test Paketi (Item 9)

Test Kapsamı:
1. SemanticMemoryEngine: Türkçe normalizasyon, TF-IDF / Cosine vektör benzerliği
2. Anlamsal Geri Çağırma (Semantic Recall): "kedimin adı ne", "şarkı tercihim" gibi sorgularda anıların bulunması
3. Kalıcı Bellek CRUD: store_fact, delete_fact, list_all_memories
4. Prompt Bağlam Enjeksiyonu: format_context_for_prompt
5. Dashboard API: /api/memory/list, /api/memory/search, /api/memory/save, /api/memory/item ve PWA HTML doğrulaması
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from dashboard.server import app
from memory.semantic_memory import (
    SemanticMemoryEngine,
    get_semantic_memory,
    normalize_text_semantic,
)


class TestSemanticVectorEngine(unittest.TestCase):
    """Vektör Benzerlik ve Semantik Arama Testleri."""

    def setUp(self):
        self.engine = SemanticMemoryEngine.get_instance()
        self.engine.rebuild_index()

    def test_normalize_text_semantic(self):
        """Türkçe karakter ve noktalama normalizasyonunu test eder."""
        raw = "Şarkı, Çay & Kedim: Pamuk!"
        norm = normalize_text_semantic(raw)
        self.assertEqual(norm, "sarki cay kedim pamuk")

    def test_search_cat_name_semantic(self):
        """'Kedim var mı?' veya 'kedimin adı' sorgusunda Pamuk kaydının bulunduğunu doğrular."""
        results = self.engine.search_relevant_memories("benim kedimin adı neydi", top_k=3, threshold=0.10)
        self.assertTrue(len(results) > 0)
        keys = [r.get("key") for r in results]
        values = [str(r.get("value")) for r in results]
        self.assertTrue(any("cat_name" in k for k in keys) or any("Pamuk" in v for v in values))

    def test_search_music_preferences(self):
        """'Müzik' veya 'şarkı' sorgusunda müzik tercihlerinin listelendiğini doğrular."""
        results = self.engine.search_relevant_memories("favori şarkılarım ve müzik tercihim", top_k=3, threshold=0.10)
        self.assertTrue(len(results) > 0)
        found = any("Baby Doll" in str(r.get("value")) or "music" in r.get("key", "") for r in results)
        self.assertTrue(found)

    def test_search_unrelated_query(self):
        """Tamamen ilgisiz bir sorguda düşük eşleşme veya boş liste döndüğünü test eder."""
        results = self.engine.search_relevant_memories("astronot kuantum yerçekimi hipotezi", top_k=3, threshold=0.45)
        self.assertEqual(len(results), 0)


class TestMemoryPersistenceAndFormatting(unittest.TestCase):
    """Kalıcı Bellek CRUD ve Prompt Biçimlendirme Testleri."""

    def setUp(self):
        self.engine = SemanticMemoryEngine.get_instance()

    def test_format_context_for_prompt_with_match(self):
        """Eşleşen bilgi olduğunda doğru prompt bağlam bloğunun üretildiğini test eder."""
        block = self.engine.format_context_for_prompt("kedimin adı")
        self.assertIn("[HATIRLANAN BİLGİLER VE KULLANICI BAĞLAMI]", block)
        self.assertIn("Pamuk", block)
        self.assertIn("TALİMAT", block)

    def test_format_context_for_prompt_without_match(self):
        """Eşleşme olmadığında token tasarrufu için boş string döndüğünü doğrular."""
        block = self.engine.format_context_for_prompt("mars yörüngesindeki uydular")
        self.assertEqual(block, "")

    def test_store_and_delete_fact_lifecycle(self):
        """Yeni bir bilginin hafızaya eklenip ardından silinmesini test eder."""
        test_key = "deneme_projesi"
        test_val = "Stark Antigravity IDE Projesi"

        # 1. Ekle
        ok, msg = self.engine.store_fact("work", test_key, test_val)
        self.assertTrue(ok)

        # 2. Ara ve doğrula
        mems = self.engine.search_relevant_memories("antigravity projesi", top_k=2, threshold=0.10)
        self.assertTrue(any(test_key in m.get("key", "") for m in mems))

        # 3. Sil
        del_ok, del_msg = self.engine.delete_fact("work", test_key)
        self.assertTrue(del_ok)

        # 4. Artık bulunmadığını doğrula
        all_m = self.engine.list_all_memories()
        self.assertNotIn(test_key, all_m.get("work", {}))


class TestDashboardMemoryEndpoints(unittest.TestCase):
    """Mobil Dashboard Bellek API Uç Noktaları Testleri (Rule 8)."""

    def setUp(self):
        self.client = TestClient(app)

    def test_get_memory_list_endpoint(self):
        """GET /api/memory/list uç noktasının geçerli hafıza kayıtlarını döndürdüğünü doğrular."""
        res = self.client.get("/api/memory/list")
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertEqual(d.get("status"), "ok")
        self.assertIn("memories", d)
        self.assertIsInstance(d["memories"], dict)

    def test_post_memory_search_endpoint(self):
        """POST /api/memory/search uç noktasının semantik sonuç döndürdüğünü test eder."""
        res = self.client.post("/api/memory/search", json={"query": "kedi"})
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertEqual(d.get("status"), "ok")
        self.assertIn("results", d)

    def test_post_memory_save_and_delete_endpoint(self):
        """POST /api/memory/save ve DELETE /api/memory/item uç noktalarını test eder."""
        save_res = self.client.post(
            "/api/memory/save",
            json={"category": "notes", "key": "test_kahve", "value": "Filtre Kahve"},
        )
        self.assertEqual(save_res.status_code, 200)
        self.assertEqual(save_res.json().get("status"), "ok")

        del_res = self.client.request(
            "DELETE",
            "/api/memory/item",
            json={"category": "notes", "key": "test_kahve"},
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json().get("status"), "ok")

    def test_dashboard_html_contains_memory_card(self):
        """Mobil arayüzde Kalıcı Bellek cyber kartının bulunduğunu doğrular."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Kalıcı Bellek & Bağlam", html)
        self.assertIn("memory-search-input", html)
        self.assertIn("loadMemoryList", html)
        self.assertIn("searchMemory", html)


if __name__ == "__main__":
    unittest.main()
