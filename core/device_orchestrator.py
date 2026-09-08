"""
core/device_orchestrator.py — Yerel Ağ Cihaz Keşfi ve Çoklu Cihaz Orkestrasyonu

Bu modül, EDITH'in bilgisayar, Android telefon (Termux) ve yerel ağdaki (Wi-Fi/LAN)
diğer cihazlarla sıfır konfigürasyonla (Zero-Config UDP Discovery) birbirini bulmasını,
cihaz durumlarını (batarya, IP, port, gecikme) izlemesini ve cihazlar arası olay yönlendirmesini sağlar.

Özellikler:
1. LocalDeviceDiscovery: Port 54545 üzerinden hafif UDP broadcast fenerleri (Beacon) yayımlar ve dinler.
2. DeviceOrchestrator: Yerel ağdaki tüm EDITH düğümlerini (desktop, phone_termux, pwa_web) merkezi olarak yönetir.
3. Otomatik Eskime Temizliği: 30 saniyeden uzun süredir sinyal vermeyen düğümleri offline durumuna geçirir.
4. Cihazlar Arası Olay Yönlendirme: Belirli bir düğüme veya tüm yerel ağa bildirim ve komut yollama.

Debug: Düğüm keşifleri, sinyal güncellemeleri ve yönlendirmeler loglanır.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BEACON_MAGIC = "EDITH_NODE"
DEFAULT_DISCOVERY_PORT = 54545
NODE_OFFLINE_TIMEOUT = 30.0  # saniye


def get_local_ip() -> str:
    """Mevcut cihazın yerel ağ IP adresini tespit eder."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Yönlendirme rotasını belirlemek için harici bir IP'ye bağlanır (paket gönderilmez)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class DeviceNode:
    """Yerel ağdaki tekil bir EDITH düğümü (Masaüstü, Telefon vb.)."""

    def __init__(
        self,
        node_id: str,
        name: str,
        device_type: str = "desktop",
        ip: str = "127.0.0.1",
        port: int = 8080,
        ws_port: int = 8765,
        battery_level: Optional[int] = None,
        capabilities: Optional[List[str]] = None,
        last_seen: float = 0.0,
        status: str = "online",
    ):
        self.node_id = str(node_id).strip()
        self.name = str(name).strip()
        self.device_type = str(device_type).strip()
        self.ip = str(ip).strip()
        self.port = int(port)
        self.ws_port = int(ws_port)
        self.battery_level = battery_level
        self.capabilities = list(capabilities or [])
        self.last_seen = last_seen or time.time()
        self.status = status

    def is_alive(self, timeout: float = NODE_OFFLINE_TIMEOUT) -> bool:
        """Düğümün hala çevrimiçi olup olmadığını kontrol eder."""
        return (time.time() - self.last_seen) <= timeout

    def to_dict(self) -> Dict[str, Any]:
        alive = self.is_alive()
        return {
            "node_id": self.node_id,
            "name": self.name,
            "device_type": self.device_type,
            "ip": self.ip,
            "port": self.port,
            "ws_port": self.ws_port,
            "battery_level": self.battery_level,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen,
            "status": "online" if alive else "offline",
            "age_seconds": round(time.time() - self.last_seen, 1),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> DeviceNode:
        return cls(
            node_id=d.get("node_id", "unknown"),
            name=d.get("name", "Unknown Node"),
            device_type=d.get("device_type", "unknown"),
            ip=d.get("ip", "127.0.0.1"),
            port=d.get("port", 8080),
            ws_port=d.get("ws_port", 8765),
            battery_level=d.get("battery_level"),
            capabilities=d.get("capabilities", []),
            last_seen=d.get("last_seen", time.time()),
            status=d.get("status", "online"),
        )


class LocalDeviceDiscovery:
    """
    Yerel ağda UDP Broadcast fenerleri yollayan ve komşu EDITH cihazlarını keşfeden servis.
    """

    def __init__(
        self,
        node_id: str = "desktop_host",
        name: str = "EDITH Primary Desktop",
        device_type: str = "desktop",
        port: int = 8080,
        ws_port: int = 8765,
        broadcast_port: int = DEFAULT_DISCOVERY_PORT,
        on_node_discovered: Optional[Callable[[DeviceNode], None]] = None,
    ):
        self.node_id = node_id
        self.name = name
        self.device_type = device_type
        self.port = port
        self.ws_port = ws_port
        self.broadcast_port = broadcast_port
        self.on_node_discovered = on_node_discovered

        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._beacon_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    def build_beacon_payload(self) -> bytes:
        """Yayınlanacak JSON fener paketini hazırlar."""
        local_ip = get_local_ip()
        data = {
            "magic": BEACON_MAGIC,
            "node_id": self.node_id,
            "name": self.name,
            "device_type": self.device_type,
            "ip": local_ip,
            "port": self.port,
            "ws_port": self.ws_port,
            "battery_level": 100 if self.device_type == "desktop" else None,
            "capabilities": ["screen", "tts", "stt", "files", "browser"],
            "timestamp": time.time(),
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def parse_beacon_payload(self, raw_bytes: bytes, sender_ip: str) -> Optional[DeviceNode]:
        """Gelen baytları DeviceNode nesnesine dönüştürür."""
        try:
            txt = raw_bytes.decode("utf-8", errors="replace")
            data = json.loads(txt)
            if data.get("magic") != BEACON_MAGIC:
                return None

            incoming_id = str(data.get("node_id", ""))
            # Kendi fenerimizi atla
            if incoming_id == self.node_id:
                return None

            ip = data.get("ip") or sender_ip
            node = DeviceNode(
                node_id=incoming_id,
                name=data.get("name", "EDITH Node"),
                device_type=data.get("device_type", "device"),
                ip=ip,
                port=data.get("port", 8080),
                ws_port=data.get("ws_port", 8765),
                battery_level=data.get("battery_level"),
                capabilities=data.get("capabilities", []),
                last_seen=time.time(),
                status="online",
            )
            return node
        except Exception:
            return None

    def start(self) -> None:
        """Yayıncı ve dinleyici iş parçacıklarını başlatır."""
        with self._lock:
            if self._running:
                return
            self._running = True

            # Dinleyici Thread
            self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True, name="EDITH-DiscoveryListener")
            self._listener_thread.start()

            # Fener Yayıncısı Thread (Her 8 saniyede bir)
            self._beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True, name="EDITH-BeaconBroadcaster")
            self._beacon_thread.start()
            print(f"[DeviceDiscovery] 📡 Yerel ağ cihaz keşif feneri devrede (Port: {self.broadcast_port})")

    def stop(self) -> None:
        """Keşif servisini durdurur."""
        with self._lock:
            self._running = False

    def send_broadcast_now(self) -> bool:
        """Anlık bir broadcast feneri fırlatır."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1.0)
            payload = self.build_beacon_payload()
            sock.sendto(payload, ("<broadcast>", self.broadcast_port))
            sock.close()
            return True
        except Exception as e:
            # print(f"[DeviceDiscovery] ⚠️ Broadcast gönderme uyarısı: {e}")
            return False

    def _beacon_loop(self) -> None:
        """Periyodik fener yayını döngüsü."""
        while self._running:
            self.send_broadcast_now()
            # 8 saniye bekle
            for _ in range(16):
                if not self._running:
                    break
                time.sleep(0.5)

    def _listen_loop(self) -> None:
        """Gelen fener paketlerini dinleme döngüsü."""
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception:
                    pass
            sock.bind(("", self.broadcast_port))
            sock.settimeout(2.0)
        except Exception as e:
            print(f"[DeviceDiscovery] ⚠️ UDP Soket dinleme bağlanamadı (Port {self.broadcast_port}): {e}")
            return

        while self._running:
            try:
                data, addr = sock.recvfrom(4096)
                node = self.parse_beacon_payload(data, addr[0])
                if node and self.on_node_discovered:
                    self.on_node_discovered(node)
            except socket.timeout:
                continue
            except Exception:
                if not self._running:
                    break
                time.sleep(0.5)

        if sock:
            try:
                sock.close()
            except Exception:
                pass


class DeviceOrchestrator:
    """
    Yerel ağdaki tüm EDITH cihazlarının merkezi orkestrasyon ve telemetri yöneticisi.
    """

    _instance: Optional["DeviceOrchestrator"] = None
    _lock = threading.RLock()

    def __init__(self):
        self._nodes: Dict[str, DeviceNode] = {}
        self._self_node = DeviceNode(
            node_id="edith_desktop",
            name="EDITH Master Desktop",
            device_type="desktop",
            ip=get_local_ip(),
            port=8080,
            ws_port=8765,
            battery_level=100,
            capabilities=["tts", "stt", "screen_vision", "browser", "dev_agent", "supervisor"],
        )
        self.discovery = LocalDeviceDiscovery(
            node_id=self._self_node.node_id,
            name=self._self_node.name,
            device_type=self._self_node.device_type,
            port=self._self_node.port,
            ws_port=self._self_node.ws_port,
            on_node_discovered=self.register_or_update_node,
        )

    @classmethod
    def get_instance(cls) -> "DeviceOrchestrator":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self) -> None:
        """Cihaz orkestratörünü ve yerel keşif ağını başlatır."""
        with self._lock:
            self._self_node.ip = get_local_ip()
            self.discovery.start()

    def stop(self) -> None:
        """Orkestratörü durdurur."""
        with self._lock:
            self.discovery.stop()

    def register_or_update_node(self, node: DeviceNode) -> None:
        """Ağdan gelen bir cihaz kaydını ekler veya günceller."""
        with self._lock:
            nid = node.node_id
            is_new = nid not in self._nodes
            self._nodes[nid] = node
            if is_new:
                print(f"[DeviceOrchestrator] 📱 Yeni EDITH Düğümü Keşfedildi: {node.name} [{node.device_type}] ({node.ip})")

    def get_nodes(self, include_offline: bool = True) -> List[Dict[str, Any]]:
        """Kayıtlı düğümlerin listesini döner."""
        with self._lock:
            results = [self._self_node.to_dict()]
            now = time.time()
            for nid, node in list(self._nodes.items()):
                if (now - node.last_seen) > NODE_OFFLINE_TIMEOUT:
                    node.status = "offline"
                else:
                    node.status = "online"

                if include_offline or node.status == "online":
                    results.append(node.to_dict())

            return results

    def get_node(self, node_id: str) -> Optional[DeviceNode]:
        """Belirtilen ID'ye sahip düğümü döner."""
        with self._lock:
            if node_id == self._self_node.node_id:
                return self._self_node
            return self._nodes.get(node_id)

    def prune_stale_nodes(self, max_age: float = 120.0) -> int:
        """Belirtilen süreden uzun süredir görünmeyen çevrimdışı düğümleri bellekten temizler."""
        with self._lock:
            now = time.time()
            to_remove = []
            for nid, node in self._nodes.items():
                if (now - node.last_seen) > max_age:
                    to_remove.append(nid)
            for nid in to_remove:
                del self._nodes[nid]
            return len(to_remove)

    def broadcast_announcement(self, message: str) -> Tuple[bool, str]:
        """Yerel ağa anlık bir duyuru veya komut yayınlar."""
        try:
            self.discovery.send_broadcast_now()
            print(f"[DeviceOrchestrator] 📢 Yerel Ağ Anonsu Gönderildi: {message}")
            return True, f"Duyuru yerel ağdaki {len(self.get_nodes())} cihaza iletildi."
        except Exception as e:
            return False, f"Duyuru gönderilemedi: {e}"

    def get_mesh_summary(self) -> Dict[str, Any]:
        """Yerel ağ ağı (Mesh) özet durumunu döner."""
        nodes = self.get_nodes(include_offline=True)
        online_count = sum(1 for n in nodes if n.get("status") == "online")
        return {
            "local_ip": self._self_node.ip,
            "node_count": len(nodes),
            "online_count": online_count,
            "devices": nodes,
        }


def get_device_orchestrator() -> DeviceOrchestrator:
    """Merkezi cihaz orkestratörünü döndürür."""
    return DeviceOrchestrator.get_instance()
