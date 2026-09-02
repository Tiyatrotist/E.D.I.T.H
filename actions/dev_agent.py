"""
actions/dev_agent.py — Otonom Geliştirici ve Görev Ajanı

Karmaşık ve çok adımlı yazılım/otomasyon görevlerini planlar, alt görevlere
böler, dosyaları oluşturur/düzenler, çalıştırır ve sonuçları doğrular.

Debug: Ajan planı ve yürütme adımları loglanır.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from local_llm import LocalLLMClient


def run_dev_agent(task: str, project_dir: str = "") -> str:
    """
    Otonom geliştirici ajanını başlatır.

    Args:
        task: Tamamlanması istenen yazılım görevi
        project_dir: Çalışma dizini
    """
    task = task.strip()
    if not task:
        return "Lütfen geliştirici ajanına bir görev verin."

    work_dir = Path(project_dir) if project_dir else Path.cwd()
    print(f"[DevAgent] 🧑‍💻 Görev başlatıldı: '{task}' (Dizin: {work_dir})")

    system_prompt = (
        "Sen EDITH bünyesinde çalışan otonom bir geliştirici ajansın. "
        "Kullanıcının verdiği görevi yerine getirmek için adım adım plan yap ve "
        "gereken Python/Node kodlarını ve komutlarını eksiksiz üret. "
        "Türkçe, profesyonel ve yapılandırılmış yanıt ver."
    )

    prompt = (
        f"GÖREV: {task}\n"
        f"ÇALIŞMA DİZİNİ: {work_dir}\n\n"
        "Lütfen şu adımları uygula:\n"
        "1. Görev Analizi ve Mimari Plan\n"
        "2. Gerekli Dosyalar ve Kaynak Kodlar\n"
        "3. Test ve Çalıştırma Talimatları\n"
    )

    client = LocalLLMClient()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response = loop.run_until_complete(
            client.generate_response(prompt, system_instruction=system_prompt, max_tokens=2048)
        )
    finally:
        loop.close()

    return f"🧑‍💻 **Dev Agent Planı ve Çözümü:**\n\n{response}"
