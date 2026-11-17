"""Unit tests for actions/sys_info.py formatting and query routing."""

from __future__ import annotations

from collections import namedtuple
import datetime
import unittest
from unittest.mock import MagicMock, patch

from actions import sys_info


class TestSysInfoActions(unittest.TestCase):
    """Deterministic test suite for system information queries."""

    def test_sys_info_unknown_query(self) -> None:
        """Verify invalid query returns guidance message with supported commands."""
        out = sys_info.sys_info("xyz_invalid")
        self.assertIn("Bilinmeyen sorgu: xyz_invalid", out)
        self.assertIn("battery/phone/cpu/ram/disk/time/date/network/all", out)

    @patch("actions.sys_info.datetime")
    def test_sys_info_time_and_date(self, mock_dt) -> None:
        """Verify time and date queries format deterministic timestamps."""
        fake_now = datetime.datetime(2026, 11, 20, 15, 45, 30)
        mock_dt.datetime.now.return_value = fake_now

        time_out = sys_info.sys_info("saat")
        self.assertIn("Saat: 15:45:30", time_out)

        date_out = sys_info.sys_info("tarih")
        self.assertIn("Tarih:", date_out)
        self.assertIn("2026", date_out)

    @patch("actions.sys_info.HAS_PSUTIL", True)
    @patch("actions.sys_info.psutil")
    def test_sys_info_cpu_formatting(self, mock_psutil) -> None:
        """Verify CPU usage, core count, and frequency formatting."""
        mock_psutil.cpu_percent.return_value = 15.5
        mock_psutil.cpu_count.return_value = 8
        Freq = namedtuple("Freq", ["current"])
        mock_psutil.cpu_freq.return_value = Freq(current=3200)

        out = sys_info.sys_info("cpu")
        self.assertIn("CPU: %15.5 kullanım", out)
        self.assertIn("8 çekirdek", out)
        self.assertIn("3200 MHz", out)

    @patch("actions.sys_info.HAS_PSUTIL", True)
    @patch("actions.sys_info.psutil")
    def test_sys_info_ram_formatting(self, mock_psutil) -> None:
        """Verify RAM usage and total capacity formatting in GB."""
        Vm = namedtuple("Vm", ["total", "used", "percent"])
        # 16 GB total, 8 GB used
        mock_psutil.virtual_memory.return_value = Vm(
            total=16 * (1024**3),
            used=8 * (1024**3),
            percent=50.0,
        )

        out = sys_info.sys_info("bellek")
        self.assertIn("RAM: 8.0GB / 16.0GB kullanımda (%50)", out)

    @patch("actions.sys_info.HAS_PSUTIL", True)
    @patch("actions.sys_info.psutil")
    def test_sys_info_battery_charging_and_unplugged(self, mock_psutil) -> None:
        """Verify battery percentage and charge state formatting."""
        Bat = namedtuple("Bat", ["percent", "power_plugged"])

        # Charging
        mock_psutil.sensors_battery.return_value = Bat(percent=85.0, power_plugged=True)
        out_charging = sys_info.sys_info("pil")
        self.assertIn("Pil: %85 — Şarj oluyor", out_charging)

        # Unplugged
        mock_psutil.sensors_battery.return_value = Bat(percent=45.0, power_plugged=False)
        out_unplugged = sys_info.sys_info("pil")
        self.assertIn("Pil: %45 — Pilde", out_unplugged)

    @patch("actions.sys_info.HAS_PSUTIL", True)
    @patch("actions.sys_info.psutil")
    @patch("actions.sys_info.datetime")
    @patch("actions.sys_info._network", return_value="WiFi: TestNetwork bağlı")
    @patch("actions.sys_info._phone_status", return_value="Telefon Durumu: Pil %90")
    def test_sys_info_all_query(self, mock_phone, mock_net, mock_dt, mock_psutil) -> None:
        """Verify 'all' query aggregates multiple system metric sections."""
        fake_now = datetime.datetime(2026, 11, 20, 10, 0, 0)
        mock_dt.datetime.now.return_value = fake_now

        Bat = namedtuple("Bat", ["percent", "power_plugged"])
        mock_psutil.sensors_battery.return_value = Bat(percent=95.0, power_plugged=True)
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_freq.return_value = None
        Vm = namedtuple("Vm", ["total", "used", "percent"])
        mock_psutil.virtual_memory.return_value = Vm(total=16*(1024**3), used=4*(1024**3), percent=25)
        Du = namedtuple("Du", ["total", "used", "free"])
        mock_psutil.disk_usage.return_value = Du(total=500*(1024**3), used=200*(1024**3), free=300*(1024**3))

        out = sys_info.sys_info("all")
        self.assertIn("Pil: %95", out)
        self.assertIn("CPU: %10.0", out)
        self.assertIn("RAM: 4.0GB / 16.0GB", out)
        self.assertIn("Saat: 10:00:00", out)
        self.assertIn("WiFi: TestNetwork bağlı", out)


if __name__ == "__main__":
    unittest.main()
