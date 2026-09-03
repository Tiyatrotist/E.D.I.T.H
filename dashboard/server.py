"""
dashboard/server.py — EDITH Web & Mobil Kontrol Paneli (Mobile Companion & Call Secretary)

FastAPI tabanlı modern web ve mobil asistan sunucusu:
- Android ve iOS (PWA - Ana Ekrana Eklenebilir) uyumlu fütüristik Stark Industries HUD
- Telefonda Web Speech API ile sesli Türkçe konuşma ve sesli dinleme
- Piper Neural TTS ile sesli yanıtları doğrudan telefonda çalma (/api/tts)
- Bilgisayardaki tüm araçları (Müzik açma, Ses kontrolü, Web arama, Ekran kilidi) uzaktan çalıştırma
- Android GSM Arama Asistanı & Sekreter Köprüsü (MacroDroid / Tasker / WebSocket entegrasyonu)
- Canlı PC Donanım Telemetrisi (CPU, RAM, GPU, Disk)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from actions.system_monitor import get_system_stats
from app_config import load_app_config
from local_llm import LocalLLMClient

app = FastAPI(title="EDITH Mobile Companion & Dashboard")

BASE_DIR = Path(__file__).resolve().parent.parent
CALL_LOGS_FILE = BASE_DIR / "memory" / "call_logs.json"


def get_local_ip() -> str:
    """Bilgisayarın yerel ağ (Wi-Fi) IP adresini döndürür (Sanal bağdaştırıcıları filtreler)."""
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            if any(ign in iface.lower() for ign in ["vethernet", "wsl", "loopback", "vmware", "virtualbox", "hyper-v"]):
                continue
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    if addr.address.startswith("192.168.") or addr.address.startswith("10."):
                        return addr.address
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.101"


def load_call_logs() -> list[dict]:
    if CALL_LOGS_FILE.exists():
        try:
            with open(CALL_LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_call_log(caller_name: str, caller_number: str, transcript: list[dict], summary: str = ""):
    logs = load_call_logs()
    entry = {
        "id": int(time.time()),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "caller_name": caller_name or "Bilinmeyen Numara",
        "caller_number": caller_number or "",
        "summary": summary,
        "transcript": transcript,
    }
    logs.insert(0, entry)
    CALL_LOGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CALL_LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs[:50], f, indent=2, ensure_ascii=False)


# Canlı Çağrı Oturumu Hafızası
_ACTIVE_CALLS: dict[str, dict] = {}


_MOBILE_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#00d4c0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="EDITH Mobile">
    <title>E.D.I.T.H // Mobil Asistan & Kontrol</title>
    <style>
        :root {
            --bg: #020c0c;
            --panel: #041414;
            --panel-border: #0a2a28;
            --primary: #00d4c0;
            --primary-glow: rgba(0, 212, 192, 0.35);
            --secondary: #4488ff;
            --text: #7dfff6;
            --text-dim: #3a7a75;
            --danger: #ff3344;
            --gold: #ffcc00;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background: var(--bg); color: var(--text); padding-bottom: 90px; min-height: 100vh; overflow-x: hidden; }

        /* HEADER */
        .topbar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 14px 18px; background: rgba(4, 20, 20, 0.85); backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--panel-border); position: sticky; top: 0; z-index: 100;
        }
        .brand { font-size: 18px; font-weight: 900; letter-spacing: 2px; color: var(--primary); text-shadow: 0 0 10px var(--primary-glow); }
        .live-badge { font-size: 11px; font-weight: bold; color: #00ff88; display: flex; align-items: center; gap: 6px; }
        .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #00ff88; box-shadow: 0 0 8px #00ff88; animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        /* TABS CONTENT */
        .tab-content { display: none; padding: 14px; animation: fadeIn 0.25s ease-out; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

        /* ARC REACTOR ORB */
        .orb-wrapper { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 18px 0; }
        .orb {
            width: 140px; height: 140px; border-radius: 50%;
            background: radial-gradient(circle, #022020 0%, #010a0a 70%);
            border: 2px solid var(--primary);
            box-shadow: 0 0 24px var(--primary-glow), inset 0 0 16px var(--primary-glow);
            display: flex; align-items: center; justify-content: center; position: relative;
            cursor: pointer; transition: 0.3s;
        }
        .orb:active { transform: scale(0.96); }
        .orb-ring {
            position: absolute; border-radius: 50%; border: 1px dashed var(--primary);
            width: 116px; height: 116px; animation: spin 16s linear infinite;
        }
        .orb-inner {
            width: 70px; height: 70px; border-radius: 50%; background: var(--panel);
            border: 1px solid var(--primary); display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 12px var(--primary);
        }
        .orb-state { margin-top: 10px; font-size: 12px; font-weight: bold; letter-spacing: 1.5px; color: var(--primary); text-transform: uppercase; }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        /* CHAT STREAM */
        .chat-container {
            background: var(--panel); border: 1px solid var(--panel-border); border-radius: 12px;
            height: 280px; overflow-y: auto; padding: 12px; margin-bottom: 12px;
            display: flex; flex-direction: column; gap: 10px;
        }
        .bubble { padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.45; max-width: 86%; word-wrap: break-word; }
        .bubble.user { background: #082a28; color: #fff; align-self: flex-end; border: 1px solid var(--primary); border-bottom-right-radius: 2px; }
        .bubble.bot { background: #021212; color: var(--text); align-self: flex-start; border: 1px solid var(--panel-border); border-bottom-left-radius: 2px; }
        .bubble.sys { background: transparent; color: var(--gold); align-self: center; font-size: 12px; border: none; }

        /* INPUT ROW */
        .input-bar { display: flex; gap: 8px; align-items: center; }
        .input-bar input {
            flex: 1; background: #021212; border: 1px solid var(--panel-border); border-radius: 24px;
            color: #fff; padding: 12px 16px; font-size: 15px; outline: none; transition: 0.2s;
        }
        .input-bar input:focus { border-color: var(--primary); box-shadow: 0 0 10px var(--primary-glow); }
        .btn-mic {
            width: 48px; height: 48px; border-radius: 50%; background: #032020; border: 1px solid var(--primary);
            color: var(--primary); font-size: 20px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: 0.2s; flex-shrink: 0; box-shadow: 0 0 10px var(--primary-glow);
        }
        .btn-mic.recording { background: var(--danger); border-color: #fff; color: #fff; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
        .btn-send {
            width: 48px; height: 48px; border-radius: 50%; background: var(--primary); border: none;
            color: #000; font-size: 18px; font-weight: bold; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: 0.2s; flex-shrink: 0;
        }

        /* TELEMETRY & CONTROLS GRID */
        .card { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 12px; padding: 14px; margin-bottom: 12px; }
        .card-title { font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; color: var(--text-dim); margin-bottom: 10px; display: flex; justify-content: space-between; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-box { background: #021010; border: 1px solid var(--panel-border); border-radius: 8px; padding: 12px; text-align: center; }
        .stat-num { font-size: 24px; font-weight: bold; color: #fff; margin-top: 4px; }
        .ctrl-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        .ctrl-btn {
            background: #031818; border: 1px solid var(--panel-border); border-radius: 8px;
            color: var(--text); padding: 14px 10px; font-size: 13px; font-weight: bold;
            cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .ctrl-btn:active { background: var(--primary); color: #000; }

        /* CALL SECRETARY */
        .call-banner {
            background: linear-gradient(135deg, #021c1a 0%, #032e2a 100%);
            border: 1px solid var(--primary); border-radius: 12px; padding: 16px; margin-bottom: 14px;
        }
        .call-item {
            background: #021010; border: 1px solid var(--panel-border); border-radius: 8px;
            padding: 12px; margin-bottom: 8px;
        }
        .call-header { display: flex; justify-content: space-between; font-weight: bold; margin-bottom: 6px; font-size: 14px; }
        .call-snippet { font-size: 13px; color: var(--text-dim); line-height: 1.4; }

        /* BOTTOM NAVBAR */
        .bottom-nav {
            position: fixed; bottom: 0; left: 0; right: 0; height: 68px;
            background: rgba(3, 14, 14, 0.95); backdrop-filter: blur(14px);
            border-top: 1px solid var(--panel-border); display: flex; justify-content: space-around;
            align-items: center; z-index: 100; padding-bottom: env(safe-area-inset-bottom);
        }
        .nav-item {
            display: flex; flex-direction: column; align-items: center; gap: 4px;
            color: var(--text-dim); text-decoration: none; font-size: 11px; font-weight: bold;
            cursor: pointer; transition: 0.2s; padding: 8px 12px;
        }
        .nav-item.active { color: var(--primary); }
        .nav-icon { font-size: 20px; }
    </style>
</head>
<body>

    <!-- TOPBAR -->
    <div class="topbar">
        <div class="brand">E.D.I.T.H</div>
        <div class="live-badge"><div class="pulse-dot"></div> CANLI BAĞLANTI</div>
    </div>

    <!-- TAB 1: ASİSTAN & SES -->
    <div id="tab-voice" class="tab-content active">
        <div class="orb-wrapper">
            <div class="orb" id="voice-orb" onclick="toggleVoiceInput()">
                <div class="orb-ring"></div>
                <div class="orb-inner">
                    <span id="orb-icon" style="font-size:26px;">🎙️</span>
                </div>
            </div>
            <div class="orb-state" id="orb-state-text">DİNLİYOR</div>
        </div>

        <div class="chat-container" id="chat-stream">
            <div class="bubble bot"><b>EDITH:</b> Merhaba! Telefonundan bana dilediğin komutu verebilirsin. Seni dinliyorum.</div>
        </div>

        <div class="input-bar">
            <button class="btn-mic" id="mic-btn" onclick="toggleVoiceInput()">🎤</button>
            <input type="text" id="chat-input" placeholder="Bir soru sor veya komut ver..." onkeydown="if(event.key==='Enter') sendText()">
            <button class="btn-send" onclick="sendText()">➤</button>
        </div>
    </div>

    <!-- TAB 2: TELEFON & ÇAĞRI SEKRETERİ -->
    <div id="tab-calls" class="tab-content">
        <div class="call-banner">
            <div style="font-size:16px; font-weight:900; color:var(--primary); margin-bottom:4px;">📞 GSM Çağrı Sekreteri</div>
            <div style="font-size:13px; color:#cbfbf8; line-height:1.4;">
                Android telefonunuza gelen aramaları EDITH otomatik olarak yanıtlar, sekreteriniz gibi konuşur ve not alır.
            </div>
            <div style="margin-top:10px; display:flex; gap:10px;">
                <button class="ctrl-btn" style="flex:1;" onclick="simulateIncomingCall()">🧪 Arama Simüle Et</button>
            </div>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Son Görüşmeler & Notlar</span>
                <span onclick="loadCalls()" style="cursor:pointer; color:var(--primary);">Yenile ↻</span>
            </div>
            <div id="call-logs-list">
                <div style="text-align:center; color:var(--text-dim); padding:16px;">Kayıtlı arama bulunmuyor.</div>
            </div>
        </div>
    </div>

    <!-- TAB 3: BİLGİSAYAR KONTROLÜ & TELEMETRİ -->
    <div id="tab-pc" class="tab-content">
        <div class="card">
            <div class="card-title">Bilgisayar Donanım Durumu</div>
            <div class="stats-grid">
                <div class="stat-box">
                    <div style="font-size:11px; color:var(--text-dim);">CPU KULLANIMI</div>
                    <div class="stat-num" id="stat-cpu">--%</div>
                </div>
                <div class="stat-box">
                    <div style="font-size:11px; color:var(--text-dim);">RAM KULLANIMI</div>
                    <div class="stat-num" id="stat-ram">--%</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">Hızlı Masaüstü Komutları</div>
            <div class="ctrl-grid">
                <button class="ctrl-btn" onclick="sendQuickCmd('volume_mute')">🔇 Sesi Kapat/Aç</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('screen_lock')">🔒 Ekranı Kilitle</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('show_desktop')">🖥️ Masaüstü</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('media_play_pause')">⏯️ Medya Oynat/Dur</button>
            </div>
        </div>
    </div>

    <!-- BOTTOM NAVBAR -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchTab('tab-voice', this)">
            <div class="nav-icon">🎙️</div>
            <div>Asistan</div>
        </div>
        <div class="nav-item" onclick="switchTab('tab-calls', this)">
            <div class="nav-icon">📞</div>
            <div>Çağrılar</div>
        </div>
        <div class="nav-item" onclick="switchTab('tab-pc', this)">
            <div class="nav-icon">💻</div>
            <div>Bilgisayar</div>
        </div>
    </div>

    <!-- AUDIO ELEMENT FOR PIPER TTS -->
    <audio id="tts-audio" style="display:none;"></audio>

    <script>
        let currentTab = 'tab-voice';
        let isRecording = false;
        let recognition = null;

        function switchTab(tabId, el) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            el.classList.add('active');
            currentTab = tabId;
            if(tabId === 'tab-calls') loadCalls();
        }

        // WEB SPEECH RECOGNITION (Türkçe Sesli Giriş)
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRec();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'tr-TR';

            recognition.onstart = () => {
                isRecording = true;
                document.getElementById('mic-btn').classList.add('recording');
                document.getElementById('orb-state-text').innerText = 'DİNLİYOR...';
                document.getElementById('orb-icon').innerText = '👂';
            };

            recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                if(text) {
                    appendMsg('user', text);
                    processCommand(text);
                }
            };

            recognition.onerror = (event) => {
                stopRecording();
            };

            recognition.onend = () => {
                stopRecording();
            };
        }

        function toggleVoiceInput() {
            if(!recognition) {
                alert("Tarayıcınız ses tanıma desteklemiyor. Metin kutusunu kullanabilirsiniz.");
                return;
            }
            if(isRecording) {
                recognition.stop();
            } else {
                try { recognition.start(); } catch(e) {}
            }
        }

        function stopRecording() {
            isRecording = false;
            document.getElementById('mic-btn').classList.remove('recording');
            document.getElementById('orb-state-text').innerText = 'HAZIR';
            document.getElementById('orb-icon').innerText = '🎙️';
        }

        function appendMsg(role, text) {
            const box = document.getElementById('chat-stream');
            const b = document.createElement('div');
            b.className = 'bubble ' + (role === 'user' ? 'user' : role === 'bot' ? 'bot' : 'sys');
            b.innerHTML = (role === 'user' ? '<b>Siz:</b> ' : role === 'bot' ? '<b>EDITH:</b> ' : '') + text;
            box.appendChild(b);
            box.scrollTop = box.scrollHeight;
        }

        function sendText() {
            const inp = document.getElementById('chat-input');
            const txt = inp.value.trim();
            if(!txt) return;
            inp.value = '';
            appendMsg('user', txt);
            processCommand(txt);
        }

        async function processCommand(text) {
            document.getElementById('orb-state-text').innerText = 'DÜŞÜNÜYOR...';
            document.getElementById('orb-icon').innerText = '🧠';

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt: text})
                });
                const data = await res.json();
                appendMsg('bot', data.response);

                // Sesi telefonda çal
                playPiperAudio(data.response);
            } catch(e) {
                appendMsg('sys', '⚠️ Sunucu ile bağlantı kurulamadı.');
            } finally {
                document.getElementById('orb-state-text').innerText = 'HAZIR';
                document.getElementById('orb-icon').innerText = '🎙️';
            }
        }

        function playPiperAudio(text) {
            if(!text) return;
            // Düşünce etiketlerini veya gereksiz karakterleri temizle
            const clean = text.replace(/<[^>]+>/g, '').replace(/TOOL_CALL:[^\\n]+/g, '').trim();
            if(!clean) return;

            const audio = document.getElementById('tts-audio');
            audio.src = '/api/tts?text=' + encodeURIComponent(clean);
            audio.play().catch(e => {
                console.log("Ses otomatik oynatılamadı:", e);
            });
        }

        async function sendQuickCmd(cmd) {
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: cmd})
                });
                const d = await res.json();
                appendMsg('sys', '⚙️ ' + (d.result || 'İşlem tamamlandı.'));
            } catch(e) {}
        }

        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const d = await res.json();
                document.getElementById('stat-cpu').innerText = '%' + Math.round(d.cpu_percent || 0);
                document.getElementById('stat-ram').innerText = '%' + Math.round(d.ram_percent || 0);
            } catch(e) {}
        }
        setInterval(fetchStats, 3000);
        fetchStats();

        async function loadCalls() {
            try {
                const res = await fetch('/api/phone/logs');
                const logs = await res.json();
                const container = document.getElementById('call-logs-list');
                if(!logs || logs.length === 0) {
                    container.innerHTML = '<div style="text-align:center; color:var(--text-dim); padding:16px;">Kayıtlı arama bulunmuyor.</div>';
                    return;
                }
                container.innerHTML = logs.map(c => `
                    <div class="call-item">
                        <div class="call-header">
                            <span style="color:var(--primary);">📞 ${c.caller_name}</span>
                            <span style="font-size:11px; color:var(--text-dim);">${c.time}</span>
                        </div>
                        <div class="call-snippet">${c.summary || (c.transcript && c.transcript.length > 0 ? c.transcript[0].content : 'Görüşme tamamlandı.')}</div>
                    </div>
                `).join('');
            } catch(e) {}
        }

        async function simulateIncomingCall() {
            appendMsg('sys', '🔔 Test Çağrısı Başlatılıyor: Ahmet Yılmaz...');
            try {
                const res = await fetch('/api/phone/simulate', { method: 'POST' });
                const d = await res.json();
                appendMsg('bot', '📞 [TELEFON ÇAĞRISI]: ' + d.reply);
                playPiperAudio(d.reply);
                loadCalls();
            } catch(e) {}
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return _MOBILE_DASHBOARD_HTML


@app.get("/api/stats")
async def api_stats():
    return get_system_stats()


@app.get("/api/info")
async def api_info():
    return {
        "ip": get_local_ip(),
        "port": 8080,
        "ws_port": 8765,
        "app": "EDITH",
        "version": "3.0.0",
    }


@app.get("/api/tts")
async def api_tts(text: str = ""):
    """Piper TTS ile metni WAV formatında doğrudan telefona akıtır."""
    if not text.strip():
        return Response(status_code=400)

    # 1. Metni temizle
    clean_text = re.sub(r"<[^>]+>", "", text).strip()
    if not clean_text:
        return Response(status_code=400)

    # 2. Piper WAV sentezleme
    try:
        from actions.piper_tts import synthesize_to_wav
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        ok = synthesize_to_wav(clean_text[:400], tmp_path, language="tr")
        if ok and os.path.exists(tmp_path):
            with open(tmp_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        print(f"[DashboardTTS] ⚠️ Hata: {e}")

    return Response(status_code=500)


@app.post("/api/chat")
async def api_chat(payload: dict):
    prompt = payload.get("prompt", "")
    if not prompt.strip():
        return {"response": "Sizi dinliyorum."}

    client = LocalLLMClient()
    from main import TOOLS_DESCRIPTION, load_system_prompt
    sys_instruction = load_system_prompt("tr") + "\n\n" + TOOLS_DESCRIPTION

    raw_resp = await client.generate_response(prompt=prompt, system_instruction=sys_instruction, max_tokens=512)

    # Araç Çağrısı Kontrolü
    from main import EdithLive
    edith_dummy = EdithLive.__new__(EdithLive)
    tool_name, args, clean_text = edith_dummy._parse_tool_call(raw_resp)

    if tool_name:
        try:
            print(f"[Dashboard] 🛠️ Mobil Komut Araç Çağrısı: {tool_name} {args}")
            # Aracı çalıştır
            tool_res = await edith_dummy._execute_tool(tool_name, args)
            followup = await client.generate_response(
                prompt=f"{prompt}\nAraç sonucu: {tool_res}\nKullanıcıya bilgi ver:",
                system_instruction=sys_instruction,
                max_tokens=256,
            )
            return {"response": followup or tool_res}
        except Exception as e:
            return {"response": f"{tool_name} işlemi sırasında bir aksaklık oldu."}

    return {"response": clean_text}


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
    elif action == "media_play_pause":
        res = control_computer("media_play_pause")
    else:
        res = "Bilinmeyen komut"

    return {"status": "ok", "result": res}


@app.get("/api/phone/logs")
async def get_phone_logs():
    return load_call_logs()


@app.post("/api/phone/incoming_call")
async def phone_incoming_call(payload: dict):
    """MacroDroid veya mobil istemciden gelen arama bildirimi."""
    caller_name = payload.get("caller_name", "Bilinmeyen Numara")
    caller_number = payload.get("caller_number", "")
    call_id = f"{caller_number}_{int(time.time())}"

    from core.call_handler import CallHandler
    handler = CallHandler(caller_name, caller_number)
    _ACTIVE_CALLS[call_id] = {
        "handler": handler,
        "caller_name": caller_name,
        "caller_number": caller_number,
        "start_time": time.time(),
    }

    cfg = load_app_config().get("phone_companion", {})
    auto_answer = cfg.get("auto_answer", True)
    greeting = cfg.get("greeting", f"Merhaba, ben Buğra'nın asistanı EDITH. {caller_name}, nasıl yardımcı olabilirim?")

    return {
        "call_id": call_id,
        "auto_answer": auto_answer,
        "greeting": greeting,
    }


@app.post("/api/phone/caller_speech")
async def phone_caller_speech(payload: dict):
    """Arayan kişinin konuşma metnini işler ve EDITH sekreter yanıtı üretir."""
    call_id = payload.get("call_id", "")
    text = payload.get("text", "")

    session = _ACTIVE_CALLS.get(call_id)
    if not session:
        from core.call_handler import CallHandler
        handler = CallHandler(payload.get("caller_name", "Arayan"), "")
    else:
        handler = session["handler"]

    reply = await handler.generate_reply(text)
    return {"reply": reply}


@app.post("/api/phone/call_ended")
async def phone_call_ended(payload: dict):
    """Arama sonlandığında görüşme kaydını hafızaya yazar."""
    call_id = payload.get("call_id", "")
    session = _ACTIVE_CALLS.pop(call_id, None)

    if session:
        handler = session["handler"]
        save_call_log(
            session["caller_name"],
            session["caller_number"],
            handler.history,
            summary=f"{len(handler.history)} mesajlık görüşme tamamlandı.",
        )
    return {"status": "recorded"}


@app.post("/api/phone/simulate")
async def phone_simulate():
    """Örnek bir telefon çağrısını simüle eder."""
    from core.call_handler import CallHandler
    handler = CallHandler("Ahmet Yılmaz (İş)", "0532 555 0123")
    reply = await handler.generate_reply("Merhaba Buğra orada mı? Yarınki proje toplantısı saat 14:00'e alındı, haber verebilir misin?")
    save_call_log(
        "Ahmet Yılmaz (İş)",
        "0532 555 0123",
        handler.history,
        summary="Yarınki proje toplantısı saat 14:00'e alındı.",
    )
    return {"reply": reply}


def start_dashboard(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Dashboard sunucusunu arka plan thread'inde başlatır."""
    def _run():
        local_ip = get_local_ip()
        print(f"[Dashboard] 🚀 Mobil Asistan & Web Paneli hazır:")
        print(f"            📱 Telefon Bağlantı Adresi: http://{local_ip}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
