"""
dashboard/server.py — EDITH Web Kontrol Paneli ve Uzaktan Yönetim Sunucusu

FastAPI tabanlı web sunucusu:
- Bilgisayar ve telefon tarayıcısından EDITH'i kontrol etme
- Canlı sistem metrikleri (CPU, RAM, GPU, Sıcaklık)
- Web üzerinden metinle sohbet ve sesli komut
- Cihaz ve ses kontrolleri
- Eklenti ve LLM havuz durumu

Debug: Web istekleri ve WebSocket bağlantıları loglanır.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from actions.system_monitor import get_system_stats
from app_config import load_app_config
from local_llm import LocalLLMClient

app = FastAPI(title="EDITH Web Dashboard")

_HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E.D.I.T.H — Web Kontrol Paneli</title>
    <style>
        :root {
            --bg: #020c0c;
            --panel: #041414;
            --primary: #00d4c0;
            --secondary: #4488ff;
            --dim: #0a2a28;
            --text: #7dfff6;
            --danger: #ff3344;
            --success: #00ff88;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 16px; min-height: 100vh; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--primary); padding-bottom: 12px; margin-bottom: 20px; }
        .logo { font-size: 24px; font-weight: 900; color: var(--primary); letter-spacing: 2px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
        .card { background: var(--panel); border: 1px solid var(--dim); border-radius: 8px; padding: 16px; }
        .card h3 { color: var(--primary); font-size: 14px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .stat-val { font-size: 28px; font-weight: bold; color: #fff; }
        .btn { background: var(--primary); color: #000; border: none; padding: 10px 16px; border-radius: 4px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn:hover { background: var(--secondary); color: #fff; }
        .chat-box { height: 260px; overflow-y: auto; background: #010606; border: 1px solid var(--dim); border-radius: 4px; padding: 10px; margin-bottom: 10px; }
        .msg { margin-bottom: 8px; line-height: 1.4; }
        .msg.user { color: var(--primary); }
        .msg.bot { color: #fff; }
        .input-row { display: flex; gap: 8px; }
        input[type="text"] { flex: 1; background: var(--dim); border: 1px solid var(--primary); color: #fff; padding: 10px; border-radius: 4px; outline: none; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">E.D.I.T.H // CONTROL</div>
        <div id="status-pill" style="color: var(--success); font-weight: bold;">● CANLI BAĞLANTI</div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Sistem Telemetrisi</h3>
            <div id="telemetry">
                <p>CPU: <span id="cpu-stat" class="stat-val">--%</span></p>
                <p style="margin-top: 10px;">RAM: <span id="ram-stat" class="stat-val">--%</span></p>
            </div>
        </div>

        <div class="card">
            <h3>Hızlı Kontroller</h3>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <button class="btn" onclick="sendCmd('volume_mute')">Sesi Kapat / Aç</button>
                <button class="btn" onclick="sendCmd('screen_lock')">Ekranı Kilitle</button>
                <button class="btn" onclick="sendCmd('show_desktop')">Masaüstü</button>
            </div>
        </div>

        <div class="card" style="grid-column: 1 / -1;">
            <h3>Canlı EDITH Sohbeti</h3>
            <div id="chat-history" class="chat-box">
                <div class="msg bot"><b>EDITH:</b> Merhaba! Web paneline hoş geldiniz. Size nasıl yardımcı olabilirim?</div>
            </div>
            <div class="input-row">
                <input type="text" id="chat-input" placeholder="EDITH'e bir şey yazın..." onkeydown="if(event.key==='Enter') sendChat()">
                <button class="btn" onclick="sendChat()">GÖNDER</button>
            </div>
        </div>
    </div>

    <script>
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('cpu-stat').innerText = '%' + data.cpu_percent;
                document.getElementById('ram-stat').innerText = '%' + data.ram_percent;
            } catch(e) {}
        }
        setInterval(fetchStats, 2000);
        fetchStats();

        async function sendChat() {
            const inp = document.getElementById('chat-input');
            const txt = inp.value.trim();
            if(!txt) return;
            inp.value = '';

            const box = document.getElementById('chat-history');
            box.innerHTML += `<div class="msg user"><b>Siz:</b> ${txt}</div>`;
            box.scrollTop = box.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt: txt})
                });
                const data = await res.json();
                box.innerHTML += `<div class="msg bot"><b>EDITH:</b> ${data.response}</div>`;
                box.scrollTop = box.scrollHeight;
            } catch(e) {
                box.innerHTML += `<div class="msg bot" style="color:var(--danger)">Hata oluştu.</div>`;
            }
        }

        async function sendCmd(cmd) {
            await fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: cmd})
            });
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return _HTML_DASHBOARD


@app.get("/api/stats")
async def api_stats():
    return get_system_stats()


@app.post("/api/chat")
async def api_chat(payload: dict):
    prompt = payload.get("prompt", "")
    client = LocalLLMClient()
    resp = await client.generate_response(prompt)
    return {"response": resp}


@app.post("/api/command")
async def api_command(payload: dict):
    action = payload.get("action", "")
    from actions.computer_control import control_computer
    from actions.desktop import manage_desktop

    if action == "volume_mute":
        res = control_computer("mute")
    elif action == "screen_lock":
        res = control_computer("lock")
    elif action == "show_desktop":
        res = manage_desktop("show_desktop")
    else:
        res = "Bilinmeyen komut"

    return {"status": "ok", "result": res}


def start_dashboard(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Dashboard sunucusunu arka plan thread'inde başlatır."""
    def _run():
        print(f"[Dashboard] 🚀 Web Kontrol Paneli başlatılıyor: http://localhost:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
