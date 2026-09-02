"""
core/plugin_loader.py — Dinamik Eklenti (Plugin) Yükleyici ve Yöneticisi

`plugins/` klasöründeki Python dosyalarını otomatik olarak keşfeder,
doğrular ve LLM Tool çağrı sistemine kaydeder.

Özellikler:
- Sıfır kod değişikliğiyle yeni eklenti ekleme (Drop-in plugin)
- Parametre doğrulama ve çakışma kontrolü
- Çalışma anında eklenti açma/kapama desteği (config_manager üzerinden)

Debug: Eklenti keşfi ve yükleme sonuçları konsola yazdırılır.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from memory.config_manager import get_plugin_enabled

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
_DEFAULT_PARAMS = {"type": "OBJECT", "properties": {}}


@dataclass
class PluginRecord:
    """Tek bir eklentinin metaverilerini ve çalıştırılabilir fonksiyonunu tutar."""
    name: str
    description: str = ""
    parameters: dict = field(default_factory=lambda: dict(_DEFAULT_PARAMS))
    run: Optional[Callable] = None
    file: str = ""
    valid: bool = False
    error: str = ""


class PluginRegistry:
    """Tüm aktif ve geçerli eklentilerin merkezi sicili."""

    def __init__(self, plugins: dict[str, PluginRecord], logger: Optional[Callable[[str], None]] = None):
        self._plugins = plugins          # name -> PluginRecord (Sadece GEÇERLİ olanlar)
        self._all_records: list[PluginRecord] = []
        self._logger = logger or print

    def get_tool_declarations(self) -> list[dict]:
        """LLM tool calling için aktif eklenti deklarasyonlarını döndürür."""
        decls = []
        for name, rec in self._plugins.items():
            if get_plugin_enabled(name):
                decls.append({
                    "name": rec.name,
                    "description": rec.description,
                    "parameters": rec.parameters,
                })
        return decls

    def has(self, name: str) -> bool:
        """Eklenti kayıtlı mı?"""
        return name in self._plugins

    def run(self, name: str, parameters: dict = None, player=None, session_memory=None) -> str:
        """Eklentiyi çalıştırır."""
        parameters = parameters or {}
        rec = self._plugins.get(name)
        if rec is None or not rec.valid:
            return f"Eklenti '{name}' mevcut veya geçerli değil."
        if not get_plugin_enabled(name):
            return f"'{name}' eklentisi şu anda devre dışı bırakılmış."
        
        try:
            # Fonksiyon parametrelerini dinamik olarak kontrol et ve çağır
            sig = inspect.signature(rec.run)
            kwargs = {}
            if "parameters" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs["parameters"] = parameters
            if "player" in sig.parameters:
                kwargs["player"] = player
            if "session_memory" in sig.parameters:
                kwargs["session_memory"] = session_memory

            if not kwargs:
                # Parametresiz fonksiyon
                result = rec.run()
            else:
                result = rec.run(**kwargs)

            return str(result) if result is not None else "İşlem tamamlandı."
        except Exception as e:
            self._logger(f"[PluginRegistry] ❌ Eklenti '{name}' çalışırken hata verdi: {e}")
            traceback.print_exc()
            return f"Eklenti '{name}' çalışırken bir hata oluştu: {e}"

    def list_for_ui(self) -> list[dict]:
        """UI için tüm eklentilerin listesini döndürür."""
        out = []
        for rec in self._all_records:
            out.append({
                "name": rec.name,
                "description": rec.description,
                "file": rec.file,
                "valid": rec.valid,
                "enabled": get_plugin_enabled(rec.name) if rec.valid else False,
                "error": rec.error,
            })
        return out


def discover_plugins(plugins_dir: Path | str | None = None, logger: Optional[Callable[[str], None]] = None) -> PluginRegistry:
    """
    Belirtilen dizindeki (varsayılan: `plugins/`) eklentileri tarar ve yükler.
    """
    _log = logger or print
    if plugins_dir is None:
        base_dir = Path(__file__).resolve().parent.parent
        plugins_dir = base_dir / "plugins"
    else:
        plugins_dir = Path(plugins_dir)

    plugins_dir.mkdir(parents=True, exist_ok=True)
    valid_plugins: dict[str, PluginRecord] = {}
    all_records: list[PluginRecord] = []

    _log(f"[PluginLoader] 🔍 Eklenti dizini taranıyor: {plugins_dir}")

    for py_file in sorted(plugins_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue

        module_name = f"edith_plugin_{py_file.stem}"
        record = PluginRecord(name=py_file.stem, file=str(py_file))

        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                raise ImportError("Modül spec yüklenemedi")

            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            # PLUGIN dict kontrolü
            plugin_dict = getattr(mod, "PLUGIN", None)
            run_fn = getattr(mod, "run", None)

            if not isinstance(plugin_dict, dict):
                raise ValueError("Modül 'PLUGIN' sözlüğü (dict) içermiyor")
            if not callable(run_fn):
                raise ValueError("Modül 'run' fonksiyonu içermiyor")

            name = plugin_dict.get("name", py_file.stem)
            if not _NAME_RE.match(name):
                raise ValueError(f"Geçersiz eklenti adı: '{name}' (alfasayısal ve alt çizgi olmalı)")

            record.name = name
            record.description = str(plugin_dict.get("description", ""))
            record.parameters = plugin_dict.get("parameters", dict(_DEFAULT_PARAMS))
            record.run = run_fn
            record.valid = True

            if name in valid_plugins:
                raise ValueError(f"'{name}' adlı başka bir eklenti zaten mevcut (çakışma)")

            valid_plugins[name] = record
            _log(f"[PluginLoader] ✅ Eklenti yüklendi: '{name}' ({py_file.name})")

        except Exception as e:
            record.valid = False
            record.error = str(e)
            _log(f"[PluginLoader] ❌ Eklenti yüklenemedi '{py_file.name}': {e}")

        all_records.append(record)

    registry = PluginRegistry(valid_plugins, logger=_log)
    registry._all_records = all_records
    _log(f"[PluginLoader] 🎯 Toplam {len(valid_plugins)} geçerli eklenti hazır.")
    return registry
