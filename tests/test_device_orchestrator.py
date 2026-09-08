"""
tests/test_device_orchestrator.py — Çevrimdışı ve Yerel Ağ Entegrasyonu Test Paketi (Item 10)

Test Kapsamı:
1. DeviceNode: Veri modeli, JSON serileştirme, durum ve yaşam süresi (TTL) kontrolü.
2. LocalDeviceDiscovery: UDP Beacon paketleme, ayrıştırma ve broadcast testi.
3. DeviceOrchestrator: Merkezi düğüm kaydı, canlılık telemetrisi, eskime temizliği ve mesh özeti.
4. OfflineSyncQueue: Çevrimdışı kuyruğa yazma, okuma, temizleme ve otomatik uzlaştırma (Reconciliation).
5. Dashboard REST API: /api/network/* uç noktaları ve Mobil Web PWA HTML doğrulaması.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from core.device_orchestrator import (
    BEACON_MAGIC,
    DeviceNode,
    DeviceOrchestrator,
    LocalDeviceDiscovery,
    get_device_orchestrator,
    get_local_ip,
)
from core.offline_queue import OfflineSyncQueue, get_offline_queue
from dashboard.server import app


class TestDeviceNode(unittest.TestCase):
    """DeviceNode Veri Modeli ve TTL Testleri."""

    def test_node_serialization_and_deserialization(self):
        """Düğüm nesnesinin sözlüğe çevrilip tekrar oluşturulmasını test eder."""
        node = DeviceNode(
            node_id="test_phone_1",
            name="Buğra Galaxy S23",
            device_type="phone_termux",
            ip="192.168.1.55",
            port=8080,
            ws_port=8765,
            battery_level=88,
            capabilities=["tts", "camera"],
            last_seen=time.time(),
        )
        d = node.to_dict()
        self.assertEqual(d["node_id"], "test_phone_1")
        self.assertEqual(d["name"], "Buğra Galaxy S23")
        self.assertEqual(d["battery_level"], 88)
        self.assertEqual(d["status"], "online")

        restored = DeviceNode.from_dict(d)
        self.assertEqual(restored.node_id, node.node_id)
        self.assertEqual(restored.ip, node.ip)
        self.assertEqual(restored.battery_level, 88)

    def test_node_is_alive_and_timeout(self):
        """Eski düğümlerin çevrimdışı (offline) olarak işaretlendiğini doğrular."""
        node = DeviceNode(
            node_id="old_node",
            name="Eski Düğüm",
            last_seen=time.time() - 45.0,  # 45 saniye önce
        )
        self.assertFalse(node.is_alive(timeout=30.0))
        d = node.to_dict()
        self.assertEqual(d["status"], "offline")


class TestLocalDeviceDiscovery(unittest.TestCase):
    """Yerel Ağ UDP Beacon ve Paket Ayrıştırma Testleri."""

    def setUp(self):
        self.discovery = LocalDeviceDiscovery(
            node_id="self_test_node",
            name="Test Desktop",
            device_type="desktop",
            port=8080,
            ws_port=8765,
        )

    def test_build_and_parse_beacon_payload(self):
        """Beacon paketinin oluşturulup komşu düğüm tarafından başarıyla ayrıştırıldığını test eder."""
        raw_bytes = self.discovery.build_beacon_payload()
        self.assertIsInstance(raw_bytes, bytes)

        # Başka bir dinleyici gözünden ayrıştır
        other_listener = LocalDeviceDiscovery(node_id="other_remote_node")
        parsed_node = other_listener.parse_beacon_payload(raw_bytes, sender_ip="192.168.1.100")
        self.assertIsNotNone(parsed_node)
        self.assertEqual(parsed_node.node_id, "self_test_node")
        self.assertEqual(parsed_node.name, "Test Desktop")
        self.assertEqual(parsed_node.device_type, "desktop")

    def test_beacon_ignores_own_node_id(self):
        """Düğümün kendi gönderdiği UDP paketini yoksaydığını doğrular."""
        raw_bytes = self.discovery.build_beacon_payload()
        parsed_self = self.discovery.parse_beacon_payload(raw_bytes, sender_ip="127.0.0.1")
        self.assertIsNone(parsed_self)

    def test_beacon_send_broadcast_now(self):
        """Broadcast paketinin hatasız gönderildiğini doğrular."""
        res = self.discovery.send_broadcast_now()
        # UDP soket hatası vermemeli
        self.assertIsInstance(res, bool)


class TestDeviceOrchestrator(unittest.TestCase):
    """DeviceOrchestrator Registry ve Mesh Yönetimi Testleri."""

    def setUp(self):
        self.orchestrator = DeviceOrchestrator.get_instance()

    def test_register_and_get_nodes(self):
        """Yeni bir düğümün kaydedilip listede yer aldığını doğrular."""
        test_node = DeviceNode(
            node_id="termux_companion_test",
            name="Termux Phone",
            device_type="phone_termux",
            ip="192.168.1.42",
            battery_level=75,
            last_seen=time.time(),
        )
        self.orchestrator.register_or_update_node(test_node)

        nodes = self.orchestrator.get_nodes(include_offline=True)
        node_ids = [n["node_id"] for n in nodes]
        self.assertIn("termux_companion_test", node_ids)
        self.assertIn("edith_desktop", node_ids)

        found = self.orchestrator.get_node("termux_companion_test")
        self.assertIsNotNone(found)
        self.assertEqual(found.battery_level, 75)

    def test_prune_stale_nodes(self):
        """Çok eski düğümlerin bellekten temizlendiğini test eder."""
        stale_node = DeviceNode(
            node_id="stale_node_to_prune",
            name="Stale Node",
            last_seen=time.time() - 300.0,  # 5 dakika önce
        )
        self.orchestrator.register_or_update_node(stale_node)
        pruned_count = self.orchestrator.prune_stale_nodes(max_age=120.0)
        self.assertTrue(pruned_count >= 1)
        self.assertIsNone(self.orchestrator.get_node("stale_node_to_prune"))

    def test_mesh_summary_structure(self):
        """get_mesh_summary çıktısının beklenen alanları içerdiğini doğrular."""
        summary = self.orchestrator.get_mesh_summary()
        self.assertIn("local_ip", summary)
        self.assertIn("node_count", summary)
        self.assertIn("online_count", summary)
        self.assertIn("devices", summary)
        self.assertTrue(summary["node_count"] >= 1)

    def test_broadcast_announcement(self):
        """broadcast_announcement fonksiyonunun doğru yanıt verdiğini test eder."""
        ok, msg = self.orchestrator.broadcast_announcement("Test Mesajı")
        self.assertTrue(ok)
        self.assertIn("cihaza iletildi", msg)


class TestOfflineSyncQueue(unittest.TestCase):
    """OfflineSyncQueue Çevrimdışı Kuyruk ve Uzlaştırma Testleri."""

    def setUp(self):
        self.temp_file = Path(tempfile.mktemp(suffix=".json", prefix="edith_test_queue_"))
        self.queue = OfflineSyncQueue(queue_path=self.temp_file)

    def tearDown(self):
        if self.temp_file.exists():
            try:
                self.temp_file.unlink()
            except Exception:
                pass

    def test_enqueue_and_peek(self):
        """Kuyruğa eleman ekleme ve inceleme testini doğrular."""
        item = self.queue.enqueue("save_memory", {"category": "test", "key": "offline_k", "value": "offline_v"})
        self.assertIn("id", item)
        self.assertEqual(item["action_type"], "save_memory")
        self.assertEqual(self.queue.count(), 1)

        peeked = self.queue.peek(limit=5)
        self.assertEqual(len(peeked), 1)
        self.assertEqual(peeked[0]["id"], item["id"])

    def test_remove_and_clear(self):
        """Kuyruktan eleman silme ve tamamen temizleme testleri."""
        it1 = self.queue.enqueue("chat_message", {"content": "offline msg 1"})
        it2 = self.queue.enqueue("chat_message", {"content": "offline msg 2"})
        self.assertEqual(self.queue.count(), 2)

        del_ok = self.queue.remove(it1["id"])
        self.assertTrue(del_ok)
        self.assertEqual(self.queue.count(), 1)

        cleared = self.queue.clear()
        self.assertEqual(cleared, 1)
        self.assertEqual(self.queue.count(), 0)

    def test_reconcile_with_custom_callback(self):
        """Özel işleyici ile kuyruk uzlaştırma işlemini test eder."""
        self.queue.enqueue("action_success", {"data": 1})
        self.queue.enqueue("action_fail", {"data": 2})

        def mock_handler(action_type: str, payload: dict) -> bool:
            return action_type == "action_success"

        res = self.queue.reconcile_with_network(handler_callback=mock_handler)
        self.assertEqual(res["total"], 2)
        self.assertEqual(res["processed"], 1)
        self.assertEqual(res["remaining"], 1)
        self.assertEqual(self.queue.count(), 1)


class TestDashboardNetworkEndpoints(unittest.TestCase):
    """Mobil Web PWA Yerel Ağ Uç Noktaları Testleri (Rule 8)."""

    def setUp(self):
        self.client = TestClient(app)

    def test_get_network_devices_endpoint(self):
        """GET /api/network/devices uç noktasını test eder."""
        res = self.client.get("/api/network/devices")
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertEqual(d.get("status"), "ok")
        self.assertIn("devices", d)
        self.assertIn("local_ip", d)

    def test_post_network_broadcast_endpoint(self):
        """POST /api/network/broadcast uç noktasını test eder."""
        res = self.client.post("/api/network/broadcast", json={"message": "Akşam toplantısı var"})
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertEqual(d.get("status"), "ok")
        self.assertIn("message", d)

    def test_get_network_queue_and_sync_now_endpoints(self):
        """GET /api/network/queue ve POST /api/network/sync_now uç noktalarını test eder."""
        q_res = self.client.get("/api/network/queue")
        self.assertEqual(q_res.status_code, 200)
        qd = q_res.json()
        self.assertEqual(qd.get("status"), "ok")
        self.assertIn("count", qd)

        sync_res = self.client.post("/api/network/sync_now")
        self.assertEqual(sync_res.status_code, 200)
        sd = sync_res.json()
        self.assertEqual(sd.get("status"), "ok")
        self.assertIn("processed", sd)

    def test_dashboard_html_contains_network_card(self):
        """PWA ana sayfasında Yerel Ağ kartı ve butonlarının bulunduğunu doğrular."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Yerel Ağ & Cihaz Orkestrasyonu", html)
        self.assertIn("loadNetworkDevices", html)
        self.assertIn("sendNetworkBroadcast", html)
        self.assertIn("syncOfflineQueue", html)


if __name__ == "__main__":
    unittest.main()
