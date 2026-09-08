"""
actions/dev_agent.py — E.D.I.T.H Otonom Geliştirici ve Proje Ajanı (Dev Agent & Project Builder)

Kullanıcının verdiği yazılım veya otomasyon görevlerini otonom olarak alt adımlara böler,
proje dizinini ve dosyalarını oluşturur, AST sözdizimi (linting) kontrolü yapar, izole
terminalde çalıştırıp test eder ve hata aldığında kendi kendine düzeltme döngüsüne
(self-healing loop) girerek hatasız çalışan bir çözüm teslim eder.

Kurallar & Standartlar:
- Rule 1: Temiz, dökümante edilmiş kod ve zaman damgalı debug logları.
- Rule 2: Stark Industries asistan standardı, izin isteme döngüsü yok, otonom operatör.
- Rule 7: Çevrimdışı ve yerel modellerle uyumlu esnek ReAct / Self-Healing mimarisi.
- Rule 8: Masaüstü ve Mobil PWA eşitliği (/api/dev/run & /api/dev/status).
"""

from __future__ import annotations

import ast
import asyncio
import datetime
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from local_llm import LocalLLMClient

# Windows konsol Unicode uyumluluğu
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent

# Global Canlı Durum Takibi (Mobil & Masaüstü senkronizasyonu)
_ACTIVE_DEV_TASK: dict[str, Any] = {
    "status": "idle",       # idle | running | completed | failed
    "task": "",
    "work_dir": "",
    "started_at": None,
    "completed_at": None,
    "current_step": "",
    "files_created": [],
    "logs": [],
    "final_output": "",
    "error": None,
}


@dataclass
class DevAgentResult:
    """Dev Ajanı görevinin sonucunu temsil eden yapılandırılmış veri sınıfı."""
    success: bool
    task: str
    work_dir: str
    files_created: list[str] = field(default_factory=list)
    iterations: int = 1
    logs: list[str] = field(default_factory=list)
    final_output: str = ""
    error: Optional[str] = None

    def to_markdown(self) -> str:
        """Kullanıcı ve arayüz için şık Stark Industries raporu üretir."""
        status_icon = "🎉" if self.success else "⚠️"
        status_title = "Görev Başarıyla Tamamlandı" if self.success else "Görev Kısmen Tamamlandı"

        lines = [
            f"### {status_icon} Otonom Dev Ajanı: {status_title}",
            f"**Görev:** {self.task}",
            f"**Çalışma Dizini:** `{self.work_dir}`",
            f"**İterasyon Sayısı:** {self.iterations}",
            "",
            "---",
            "#### 📂 Oluşturulan / Güncellenen Dosyalar:",
        ]

        if self.files_created:
            for f in self.files_created:
                lines.append(f"  • `{f}`")
        else:
            lines.append("  • *Yeni dosya oluşturulmadı.*")

        lines.extend([
            "",
            "#### 🚀 Çalıştırma / Test Çıktısı:",
            "```",
            self.final_output.strip() if self.final_output else "(Çıktı üretilmedi)",
            "```",
        ])

        if self.error:
            lines.extend([
                "",
                f"> [!WARNING]\n> **Dikkat:** {self.error}",
            ])

        lines.extend([
            "---",
            "*Otonom yazılım döngüsü tamamlandı efendim.*",
        ])

        return "\n".join(lines)


def _clean_code_fence(text: str) -> str:
    """LLM çıktısındaki markdown kod bloklarını ayıklar."""
    if not text:
        return ""
    text = text.strip()
    match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Başta ve sondaki ``` temizle
    text = re.sub(r"^```[a-zA-Z0-9_\-]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


class AutonomousDevAgent:
    """
    Kendi kendine planlayan, yazan, lint eden, test eden ve hata aldığında
    kendi kendine düzelten otonom geliştirici ajan.
    """

    def __init__(self, project_dir: str = "", max_iterations: int = 3):
        self.project_dir = project_dir.strip()
        if self.project_dir:
            self.work_dir = Path(self.project_dir).resolve()
        else:
            # Varsayılan: Desktop/edith_workspace veya workspace
            self.work_dir = Path.home() / "Desktop" / "edith_projects"

        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max(1, min(max_iterations, 6))
        self.logs: list[str] = []
        self.files_created: list[str] = []

    def log(self, message: str) -> None:
        """Zaman damgalı log kaydeder ve konsola yazar."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{ts}] {message}"
        self.logs.append(log_entry)
        print(f"[DevAgent] {log_entry}")

        # Canlı duruma aktar
        global _ACTIVE_DEV_TASK
        _ACTIVE_DEV_TASK["logs"].append(log_entry)
        _ACTIVE_DEV_TASK["current_step"] = message

    def lint_code(self, code: str, language: str = "python") -> tuple[bool, str]:
        """
        Kodun sözdizimsel (syntax) doğruluğunu kontrol eder.
        """
        lang = (language or "python").lower()
        if lang in ("python", "py"):
            try:
                ast.parse(code)
                return True, "Sözdizimi (AST) hatasız."
            except SyntaxError as e:
                err_msg = f"Sözdizimi hatası (Satır {e.lineno}, Sütun {e.offset}): {e.msg}"
                return False, err_msg
            except Exception as e:
                return False, f"Ayrıştırma hatası: {e}"

        elif lang in ("json",):
            try:
                json.loads(code)
                return True, "JSON geçerli."
            except Exception as e:
                return False, f"JSON hatası: {e}"

        return True, "Desteklenmeyen lint dili, doğrudan onaylandı."

    def write_file(self, rel_path: str, content: str) -> Path:
        """Dizin hiyerarşisi oluşturarak dosyayı güvenle yazar."""
        target = (self.work_dir / rel_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel_str = str(target.relative_to(self.work_dir))
        if rel_str not in self.files_created:
            self.files_created.append(rel_str)
        self.log(f"📝 Dosya kaydedildi: {rel_str} ({len(content)} karakter)")
        return target

    def run_process(self, cmd: list[str], timeout: int = 15) -> tuple[int, str]:
        """İzole alt süreçte komut veya script çalıştırır."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.work_dir),
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            return proc.returncode, output.strip()
        except subprocess.TimeoutExpired:
            return -1, f"Çalıştırma zaman aşımına uğradı ({timeout} saniye)."
        except Exception as e:
            return -1, f"Çalıştırma hatası: {e}"

    def _call_llm_sync(self, prompt: str, system: str = "") -> str:
        """LLM üzerinden senkron yanıt çeker."""
        client = LocalLLMClient()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                client.generate_response(prompt, system_instruction=system, max_tokens=2048)
            )
        finally:
            loop.close()

    def plan_and_execute(self, task: str) -> DevAgentResult:
        """
        Otonom görev yürütme döngüsü:
        Planla -> Sentezle -> Lint Et -> Çalıştır/Test Et -> Hata varsa Kendi Kendini Düzelt (Self-Healing).
        """
        task_clean = task.strip()
        if not task_clean:
            return DevAgentResult(
                success=False,
                task="",
                work_dir=str(self.work_dir),
                error="Görev tanımı boş bırakılamaz."
            )

        global _ACTIVE_DEV_TASK
        _ACTIVE_DEV_TASK["status"] = "running"
        _ACTIVE_DEV_TASK["task"] = task_clean
        _ACTIVE_DEV_TASK["work_dir"] = str(self.work_dir)
        _ACTIVE_DEV_TASK["started_at"] = time.time()
        _ACTIVE_DEV_TASK["logs"] = []
        _ACTIVE_DEV_TASK["files_created"] = []
        _ACTIVE_DEV_TASK["error"] = None

        self.log(f"🚀 Görev Başlatıldı: '{task_clean}'")
        self.log(f"📂 Çalışma Alanı: {self.work_dir}")

        # ── ADIM 1: MİMARİ PLANLAMA ───────────────────────────────────────────
        self.log("🧠 Adım 1: Mimari analiz ve dosya yapısı planlanıyor...")
        plan_system = (
            "Sen Stark Industries otonom yazılım mimarısın. "
            "Kullanıcının görevini analiz et ve oluşturulacak dosyaları belirle. "
            "SADECE aşağıdaki JSON şemasına uygun saf JSON çıktısı ver:\n"
            "{\n"
            '  "summary": "Görev özeti",\n'
            '  "files": [\n'
            '    {"path": "dosya_adi.py", "description": "ne işe yaradığı", "language": "python"}\n'
            "  ],\n"
            '  "entry_point": "dosya_adi.py"\n'
            "}"
        )
        plan_prompt = f"GÖREV:\n{task_clean}\n\nLütfen gereken dosya planını JSON olarak üret."
        raw_plan = self._call_llm_sync(plan_prompt, system=plan_system)

        plan_data: dict[str, Any] = {}
        try:
            # JSON bloğunu ayıkla
            match = re.search(r"\{.*\}", raw_plan, re.DOTALL)
            if match:
                plan_data = json.loads(match.group(0))
        except Exception as e:
            self.log(f"ℹ️ Plan JSON ayrıştırma notu ({e}), varsayılan plan kullanılıyor.")

        if not plan_data or not plan_data.get("files"):
            # Varsayılan tek dosyalık plan
            plan_data = {
                "summary": task_clean,
                "files": [{"path": "main.py", "description": task_clean, "language": "python"}],
                "entry_point": "main.py",
            }

        files_to_create = plan_data.get("files", [])
        entry_point = plan_data.get("entry_point", "main.py")
        self.log(f"📋 Plan onaylandı: {len(files_to_create)} dosya oluşturulacak. Giriş noktası: {entry_point}")

        # ── ADIM 2 & 3: KOD SENTEZİ & LINTING ─────────────────────────────────
        created_files_map: dict[str, str] = {}

        for f_info in files_to_create:
            rel_path = f_info.get("path", "script.py")
            desc = f_info.get("description", task_clean)
            lang = f_info.get("language", "python")

            self.log(f"⚡ Kod üretiliyor: {rel_path} ({desc})...")
            code_system = (
                "Sen kıdemli bir yazılım mühendisisin. "
                "İstenen dosyayı eksiksiz, çalışan, temiz ve dökümante edilmiş kaynak kod olarak üret. "
                "SADECE kod bloğu (```python ... ```) teslim et. Fazladan sohbet yazma."
            )
            code_prompt = (
                f"ANA PROJE GÖREVİ: {task_clean}\n"
                f"ÜRETİLECEK DOSYA: {rel_path}\n"
                f"AMACI: {desc}\n"
                f"DİL: {lang}\n"
            )
            if created_files_map:
                context_str = "\n".join([f"# --- {p} ---\n{c[:300]}" for p, c in created_files_map.items()])
                code_prompt += f"\nMEVCUT PROJE BAĞLAMI:\n{context_str}\n"

            raw_code = self._call_llm_sync(code_prompt, system=code_system)
            clean_code = _clean_code_fence(raw_code)

            # AST Lint Denetimi
            is_valid, lint_msg = self.lint_code(clean_code, lang)
            if not is_valid:
                self.log(f"⚠️ İlk kodda sözdizimi hatası tespit edildi: {lint_msg}. Otomatik düzeltiliyor...")
                fix_prompt = (
                    f"Aşağıdaki {lang} kodunda sözdizimi hatası var:\n{lint_msg}\n\n"
                    f"KOD:\n{clean_code}\n\n"
                    "Lütfen hatayı gidererek sadece düzeltilmiş kod bloğunu yaz."
                )
                fixed_raw = self._call_llm_sync(fix_prompt, system="Sadece düzeltilmiş hatasız kod üret.")
                clean_code = _clean_code_fence(fixed_raw)
                is_valid, lint_msg = self.lint_code(clean_code, lang)

            # Diske yaz
            self.write_file(rel_path, clean_code)
            created_files_map[rel_path] = clean_code

        # ── ADIM 4 & 5: TEST VE KENDİ KENDİNİ DÜZELTME DÖNGÜSÜ (SELF-HEALING) ──
        target_entry = self.work_dir / entry_point
        final_output = ""
        success = False
        iteration = 1

        while iteration <= self.max_iterations:
            self.log(f"🧪 Test/Çalıştırma Denemesi {iteration}/{self.max_iterations}: `{entry_point}`...")
            
            # Python dosyası mı?
            if target_entry.suffix.lower() == ".py":
                cmd = [sys.executable, str(target_entry)]
            elif target_entry.suffix.lower() == ".js":
                cmd = ["node", str(target_entry)]
            else:
                cmd = [sys.executable, str(target_entry)]

            ret_code, proc_output = self.run_process(cmd, timeout=20)
            final_output = proc_output

            if ret_code == 0:
                self.log(f"✅ Başarılı! Çıktı kodu 0 ile tamamlandı. ({iteration}. deneme)")
                success = True
                break
            else:
                self.log(f"⚠️ Çalışma hatası alındı (Exit code: {ret_code}):\n{proc_output[:250]}...")
                
                if iteration >= self.max_iterations:
                    self.log(f"🛑 Maksimum düzeltme denemesine ({self.max_iterations}) ulaşıldı.")
                    break

                # Self-Healing: Hatayı LLM'e besleyip kodu onar
                self.log(f"🩹 Kendi Kendini Düzeltme (Self-Healing) devreye giriyor (Deneme {iteration + 1})...")
                current_code = target_entry.read_text(encoding="utf-8") if target_entry.exists() else ""
                
                heal_system = (
                    "Sen uzman hata ayıklayıcısın (debugger). "
                    "Aşağıdaki kod çalıştırıldığında hata verdi. "
                    "Hata çıktısını ve traceback'i dikkatle incele, problemi kökten çöz ve "
                    "SADECE çalışan, düzeltilmiş tam kodu kod bloğu içinde geri ver."
                )
                heal_prompt = (
                    f"GÖREV: {task_clean}\n"
                    f"HATA ALAN DOSYA: {entry_point}\n\n"
                    f"HATA / TRACEBACK ÇIKTISI:\n{proc_output}\n\n"
                    f"MEVCUT KOD:\n```python\n{current_code}\n```\n\n"
                    "Lütfen hatayı gidererek düzeltilmiş tam kodu yaz."
                )

                healed_raw = self._call_llm_sync(heal_prompt, system=heal_system)
                healed_clean = _clean_code_fence(healed_raw)

                # Yeni kodu lint et ve tekrar kaydet
                is_valid, _ = self.lint_code(healed_clean, "python")
                self.write_file(entry_point, healed_clean)
                created_files_map[entry_point] = healed_clean

                iteration += 1

        # ── ADIM 6: RAPORLAMA VE CANLI DURUM GÜNCELLEMESİ ────────────────────
        result = DevAgentResult(
            success=success,
            task=task_clean,
            work_dir=str(self.work_dir),
            files_created=list(self.files_created),
            iterations=iteration,
            logs=list(self.logs),
            final_output=final_output,
            error=None if success else f"{self.max_iterations} deneme sonrası çalışma hatası giderilemedi.",
        )

        _ACTIVE_DEV_TASK["status"] = "completed" if success else "failed"
        _ACTIVE_DEV_TASK["completed_at"] = time.time()
        _ACTIVE_DEV_TASK["files_created"] = list(self.files_created)
        _ACTIVE_DEV_TASK["final_output"] = final_output
        _ACTIVE_DEV_TASK["error"] = result.error

        self.log("🏁 Dev Ajanı döngüsü sonlandı.")
        return result


def run_dev_agent(task: str, project_dir: str = "", max_iterations: int = 3) -> str:
    """
    EDITH araç çağırma arayüzü ile uyumlu ana fonksiyon.
    
    Args:
        task: Kullanıcının çözülmesini istediği yazılım veya otomasyon görevi
        project_dir: Çalışma dizini (boşsa varsayılan proje dizini)
        max_iterations: Maksimum kendini düzeltme döngü sayısı
    """
    agent = AutonomousDevAgent(project_dir=project_dir, max_iterations=max_iterations)
    result = agent.plan_and_execute(task)
    return result.to_markdown()


def get_dev_agent_status() -> dict[str, Any]:
    """Mobil dashboard veya harici istemciler için anlık ajan durumunu döner."""
    global _ACTIVE_DEV_TASK
    return dict(_ACTIVE_DEV_TASK)
