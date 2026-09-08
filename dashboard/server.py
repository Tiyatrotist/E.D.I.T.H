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


def get_public_url() -> str:
    """Cloudflare Tunnel veya genel HTTPS erişim adresini döndürür."""
    tunnel_log = Path("/var/log/edith-tunnel.log")
    if tunnel_log.exists():
        try:
            with open(tunnel_log, "r", encoding="utf-8", errors="ignore") as f:
                for line in reversed(f.readlines()):
                    if ".trycloudflare.com" in line:
                        m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                        if m:
                            return m.group(0)
        except Exception:
            pass
    return "https://training-opportunity-experienced-million.trycloudflare.com"


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
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/png" href="https://raw.githubusercontent.com/alppunlu/E.D.I.T.H/main/assets/edith_icon.png">
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
        .install-btn {
            background: var(--primary); color: var(--bg); border: none; border-radius: 4px;
            padding: 4px 10px; font-size: 11px; font-weight: bold; cursor: pointer; display: none;
            box-shadow: 0 0 8px var(--primary-glow);
        }
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
        .mode-select {
            background: #041818;
            color: var(--primary);
            border: 1px solid var(--primary-dim);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 700;
            outline: none;
            cursor: pointer;
        }
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
        <select id="mode-select" class="mode-select" onchange="changeMode(this.value)" title="Çalışma Modu">
            <option value="hybrid">HİBRİT</option>
            <option value="server">SERVER</option>
            <option value="local">LOCAL</option>
            <option value="offline">OFFLINE</option>
        </select>
        <button id="pwaInstallBtn" class="install-btn" onclick="installPWA()">📱 UYGULAMAYI YÜKLE</button>
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

        async function loadMode() {
            try {
                const res = await fetch('/api/mode');
                const data = await res.json();
                const sel = document.getElementById('mode-select');
                if (sel && data.mode) {
                    sel.value = data.mode;
                }
            } catch(e) {}
        }
        setInterval(loadMode, 5000);
        loadMode();

        async function changeMode(newMode) {
            try {
                const res = await fetch('/api/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: newMode })
                });
                const d = await res.json();
                if (d.status === 'ok') {
                    appendMsg('sys', '⚙️ Çalışma Modu Değiştirildi: ' + newMode.toUpperCase());
                }
            } catch(e) {
                console.error('Mode change error:', e);
            }
        }

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
        let deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            const btn = document.getElementById('pwaInstallBtn');
            if (btn) btn.style.display = 'block';
        });
        function installPWA() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then(() => {
                    const btn = document.getElementById('pwaInstallBtn');
                    if (btn) btn.style.display = 'none';
                    deferredPrompt = null;
                });
            } else {
                alert("EDITH'i telefonunuzda tam ekran uygulama olarak çalıştırmak için tarayıcı menüsünden 'Ana Ekrana Ekle' (Add to Home screen) seçeneğine dokunabilirsiniz.");
            }
        }
    </script>
</body>
</html>
"""


@app.get("/manifest.json")
async def get_manifest():
    """PWA Web Manifesti."""
    return {
        "name": "E.D.I.T.H Mobile Assistant",
        "short_name": "EDITH",
        "description": "Stark Industries Yapay Zeka Mobil Asistan & Telefon Sekreteri",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#020c0c",
        "theme_color": "#00d4c0",
        "orientation": "portrait",
        "icons": [
            {
                "src": "https://raw.githubusercontent.com/alppunlu/E.D.I.T.H/main/assets/edith_icon.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://raw.githubusercontent.com/alppunlu/E.D.I.T.H/main/assets/edith_icon.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }


@app.get("/api/config")
async def get_server_config():
    """Sunucu yapılandırmasını döndürür."""
    cfg = load_app_config()
    return {
        "active_provider": cfg.get("active_provider", "nim"),
        "fallback_chain": cfg.get("fallback_chain", []),
        "phone_companion": cfg.get("phone_companion", {}),
        "discord": {
            "enabled": cfg.get("discord", {}).get("enabled", False),
            "personality": cfg.get("discord", {}).get("personality", "casual"),
            "bot_configured": bool(cfg.get("discord", {}).get("bot_token")),
        },
        "server_sync": cfg.get("server_sync", {}),
    }


@app.post("/api/config")
async def update_server_config(payload: dict):
    """Sunucu ayarlarını günceller."""
    from app_config import save_app_config
    try:
        save_app_config(payload)
        return {"status": "ok", "message": "Sunucu ayarları başarıyla kaydedildi."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


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
        "public_url": get_public_url(),
        "port": 8080,
        "ws_port": 8765,
        "app": "EDITH",
        "version": "3.0.0",
    }


@app.get("/api/tts")
async def api_tts(text: str = ""):
    """EDITH zarif kadın sesi ile metni seslendirip doğrudan telefona akıtır."""
    if not text.strip():
        return Response(status_code=400)

    # 1. Metni temizle
    clean_text = re.sub(r"<[^>]+>", "", text).strip()
    if not clean_text:
        return Response(status_code=400)

    # 2. VoiceEngine ile sentezleme (Edge-TTS EmelNeural / Piper fallback)
    try:
        from core.voice_engine import get_voice_engine
        engine = get_voice_engine()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        ok = engine.synthesize_to_file(clean_text[:400], tmp_path, language="tr")
        if ok and os.path.exists(tmp_path):
            with open(tmp_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        print(f"[DashboardTTS] ⚠️ VoiceEngine denemesi: {e}")

    # 3. Piper WAV Fallback
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
        print(f"[DashboardTTS] ⚠️ Piper Fallback hatası: {e}")

    return Response(status_code=500)


@app.post("/api/chat")
async def api_chat(payload: dict):
    prompt = payload.get("prompt", "")
    if not prompt.strip():
        return {"response": "Sizi dinliyorum."}

    client = LocalLLMClient()
    try:
        from main import TOOLS_DESCRIPTION, load_system_prompt
        sys_instruction = load_system_prompt("tr") + "\n\n" + TOOLS_DESCRIPTION
    except Exception:
        prompt_file = Path(__file__).resolve().parent.parent / "core" / "prompt.txt"
        sys_instruction = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "Sen E.D.I.T.H yapay zeka asistanısın."

    raw_resp = await client.generate_response(prompt=prompt, system_instruction=sys_instruction, max_tokens=512)

    # Araç Çağrısı Kontrolü
    clean_text = raw_resp
    try:
        from main import EdithLive
        edith_dummy = EdithLive.__new__(EdithLive)
        tool_name, args, parsed_text = edith_dummy._parse_tool_call(raw_resp)
        clean_text = parsed_text or raw_resp

        if tool_name:
            print(f"[Dashboard] 🛠️ Mobil Komut Araç Çağrısı: {tool_name} {args}")
            tool_res = await edith_dummy._execute_tool(tool_name, args)
            followup = await client.generate_response(
                prompt=f"{prompt}\nAraç sonucu: {tool_res}\nKullanıcıya bilgi ver:",
                system_instruction=sys_instruction,
                max_tokens=256,
            )
            return {"response": followup or tool_res}
    except Exception as e:
        print(f"[Dashboard] Tool parse/exec fallback: {e}")

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


@app.get("/api/history")
async def get_history(limit: int = 50, since_ts: float = 0.0):
    """Merkezi sohbet geçmişini döndürür."""
    from core.chat_history import get_chat_history
    mgr = get_chat_history()
    if since_ts > 0:
        return mgr.get_since(since_ts)
    return mgr.get_recent(limit)


@app.post("/api/history")
async def post_history(payload: dict):
    """Sohbet geçmişine yeni mesaj ekler."""
    from core.chat_history import get_chat_history
    mgr = get_chat_history()
    role = payload.get("role", "user")
    content = payload.get("content", "")
    source = payload.get("source", "desktop")
    metadata = payload.get("metadata", {})
    ts = payload.get("timestamp")
    msg_id = payload.get("id")
    msg = mgr.add_message(role=role, content=content, source=source, metadata=metadata, msg_id=msg_id, timestamp=ts)
    return {"status": "ok", "message": msg}


@app.get("/api/sync")
async def api_sync(since_ts: float = 0.0, last_call_id: int = 0):
    """İstemcinin yeni çağrıları ve sohbet geçmişini tek seferde senkronize etmesini sağlar."""
    from core.chat_history import get_chat_history
    mgr = get_chat_history()
    recent_messages = mgr.get_since(since_ts) if since_ts > 0 else mgr.get_recent(20)
    all_calls = load_call_logs()
    new_calls = [c for c in all_calls if c.get("id", 0) > last_call_id]

    return {
        "timestamp": time.time(),
        "messages": recent_messages,
        "new_calls": new_calls,
        "all_recent_calls": all_calls[:10],
    }


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
    delay = int(cfg.get("auto_answer_delay_seconds", 14))
    greeting = cfg.get("greeting", f"Merhaba, ben Buğra'nın asistanı EDITH. {caller_name}, nasıl yardımcı olabilirim?")

    # Masaüstü gelen çağrı bildirimini anında tetikle
    if _INCOMING_CALL_CALLBACK:
        try:
            _INCOMING_CALL_CALLBACK(caller_name, caller_number)
        except Exception as e:
            print(f"[PhoneBridge] ⚠️ Gelen arama callback hatası: {e}")

    return {
        "call_id": call_id,
        "auto_answer": auto_answer,
        "answer_delay_seconds": delay,
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


_CALL_NOTIFY_CALLBACK = None
_INCOMING_CALL_CALLBACK = None

def set_call_notify_callback(cb):
    """Masaüstü bildirimleri için callback kaydeder."""
    global _CALL_NOTIFY_CALLBACK
    _CALL_NOTIFY_CALLBACK = cb

def set_incoming_call_callback(cb):
    """Gelen arama çaldığında masaüstü uyarısı için callback kaydeder."""
    global _INCOMING_CALL_CALLBACK
    _INCOMING_CALL_CALLBACK = cb


@app.post("/api/phone/call_ended")
async def phone_call_ended(payload: dict):
    """Arama sonlandığında görüşme kaydını hafızaya yazar, Discord'a ve bilgisayara sesli bildirir."""
    call_id = payload.get("call_id", "")
    session = _ACTIVE_CALLS.pop(call_id, None)

    caller_name = (session["caller_name"] if session else payload.get("caller_name")) or "Bilinmeyen Numara"
    caller_number = (session["caller_number"] if session else payload.get("caller_number")) or ""

    if session:
        handler = session["handler"]
        summary = ""
        if len(handler.history) > 1:
            try:
                transcript_text = "\n".join([f"{m['role']}: {m['content']}" for m in handler.history])
                client = LocalLLMClient()
                summary = await client.generate_response(
                    prompt=f"Aşağıdaki telefon konuşmasını 1 cümlede özetle ve arayanın bıraktığı notu yaz:\n{transcript_text}",
                    system_instruction="Sen bir sekretersin. Sadece arayanın bıraktığı mesajı veya notu 1 kısa Türkçe cümleyle yaz.",
                    max_tokens=80
                )
            except Exception:
                summary = f"{len(handler.history)} mesajlık görüşme yapıldı."
        else:
            summary = "Görüşme tamamlandı."

        clean_summary = summary.strip()
        history = handler.history
    else:
        clean_summary = payload.get("summary", "Arama tamamlandı.").strip()
        history = []

    # 1. Çağrı günlüğüne kaydet
    save_call_log(
        caller_name,
        caller_number,
        history,
        summary=clean_summary,
    )

    # 2. Kalıcı ortak sohbet geçmişine ekle
    from core.chat_history import get_chat_history
    get_chat_history().add_message(
        role="phone_call",
        content=f"Arayan: {caller_name}. Bıraktığı Not: {clean_summary}",
        source="phone",
        metadata={
            "caller_name": caller_name,
            "caller_number": caller_number,
            "summary": clean_summary,
        }
    )

    # 3. Discord Bot açıksa kanala anında zengin bildirim gönder
    try:
        from discord_bot.bot import send_discord_alert
        send_discord_alert(
            title="Telefon Çağrısı Tamamlandı",
            description=f"**Not:** {clean_summary}",
            caller_name=f"{caller_name} ({caller_number})",
        )
    except Exception as e:
        print(f"[PhoneBridge] ⚠️ Discord bildirim hatası: {e}")

    # 4. Masaüstü yerel callback'i tetikle
    if _CALL_NOTIFY_CALLBACK:
        try:
            _CALL_NOTIFY_CALLBACK(caller_name, clean_summary)
        except Exception as e:
            print(f"[PhoneBridge] ⚠️ Bildirim hatası: {e}")

    # 5. Telefon kapalıysa çevrimdışı kuyruğa ekle (telefon açıldığında bildirmek için)
    now = time.time()
    last_seen = _PHONE_STATUS.get("last_seen", 0.0)
    is_phone_offline = (last_seen == 0.0) or (now - last_seen > 180)
    if is_phone_offline or payload.get("source") != "termux":
        if "offline_queue" not in _PHONE_STATUS:
            _PHONE_STATUS["offline_queue"] = []
        _PHONE_STATUS["offline_queue"].append({
            "type": "missed_call",
            "caller_name": caller_name,
            "caller_number": caller_number,
            "summary": clean_summary,
            "timestamp": now,
        })

    return {"status": "recorded"}



# ── Termux & Telefon Durumu (Batarya / Kurulum / Çevrimdışı Kuyruk) ─────────
_PHONE_STATUS = {
    "battery": None,
    "status": "unknown",
    "last_seen": 0.0,
    "offline_queue": [],
}

@app.post("/api/phone/battery")
async def phone_battery(payload: dict):
    """Termux'tan gelen batarya telemetrisini kaydeder ve varsa çevrimdışı kuyruğu teslim eder."""
    global _PHONE_STATUS
    pct = payload.get("percentage")
    st = payload.get("status", "")
    now = time.time()

    last_seen = _PHONE_STATUS.get("last_seen", 0.0)
    was_offline = (last_seen == 0.0) or (now - last_seen > 180)

    queued_events = list(_PHONE_STATUS.get("offline_queue", []))
    if was_offline and queued_events:
        _PHONE_STATUS["offline_queue"] = []

    _PHONE_STATUS["battery"] = pct
    _PHONE_STATUS["status"] = st
    _PHONE_STATUS["last_seen"] = now

    return {
        "status": "ok",
        "was_offline": was_offline,
        "pending_offline_events": queued_events,
    }

@app.get("/api/phone/status")
async def phone_status():
    """Bağlı telefonun durumunu, şarjını ve çevrimiçi/çevrimdışı bilgisini döndürür."""
    now = time.time()
    last_seen = _PHONE_STATUS.get("last_seen", 0.0)
    is_online = (last_seen > 0.0) and (now - last_seen <= 300)
    return {
        "battery": _PHONE_STATUS.get("battery"),
        "status": _PHONE_STATUS.get("status"),
        "last_seen": last_seen,
        "is_online": is_online,
        "pending_offline_count": len(_PHONE_STATUS.get("offline_queue", [])),
    }

@app.get("/api/phone/sync_offline")
async def phone_sync_offline():
    """Telefon açıldığında birikmiş çevrimdışı notları ve çağrıları çeker."""
    global _PHONE_STATUS
    events = list(_PHONE_STATUS.get("offline_queue", []))
    _PHONE_STATUS["offline_queue"] = []
    return {"events": events, "count": len(events)}


@app.get("/api/mode")
async def get_operating_mode():
    """Sistem çalışma modunu ve geçerli fiziksel modu döndürür."""
    from core.mode_manager import get_mode_manager
    mgr = get_mode_manager()
    return {
        "mode": mgr.get_mode(),
        "effective_mode": mgr.get_effective_mode(),
        "display_text": mgr.get_display_text(),
        "is_online": mgr.is_online(),
        "available_modes": ["hybrid", "server", "local", "offline"],
    }

@app.post("/api/mode")
async def set_operating_mode(payload: dict):
    """Mobil cihaz veya harici istemciden sistem modunu günceller."""
    from core.mode_manager import get_mode_manager
    new_mode = payload.get("mode", "")
    mgr = get_mode_manager()
    success = mgr.set_mode(new_mode)
    if success:
        return {
            "status": "ok",
            "mode": mgr.get_mode(),
            "effective_mode": mgr.get_effective_mode(),
            "message": f"Çalışma modu '{new_mode}' olarak güncellendi.",
        }
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": f"Geçersiz mod: {new_mode}. (hybrid, server, local, offline olmalı)"}
    )

@app.get("/api/termux/setup")
async def termux_setup_script(request: Request):
    """Termux tek satırlık dinamik kurulum betiği."""
    host_ip = request.headers.get("host", "").split(":")[0] or get_local_ip()
    script_path = BASE_DIR / "scripts" / "termux" / "setup.sh"
    if script_path.exists():
        content = script_path.read_text(encoding="utf-8")
        content = re.sub(r'PC_IP="\$\{1:-[^"]+\}"', f'PC_IP="${{1:-{host_ip}}}"', content)
        return Response(content=content, media_type="text/plain; charset=utf-8")
    return Response(content='echo "[HATA] Setup betiği bulunamadı."', media_type="text/plain")

@app.get("/api/termux/edith_phone.py")
async def termux_python_script(request: Request):
    """Termux için Python dinleyici betiği."""
    host_ip = request.headers.get("host", "").split(":")[0] or get_local_ip()
    script_path = BASE_DIR / "scripts" / "termux" / "edith_phone.py"
    if script_path.exists():
        content = script_path.read_text(encoding="utf-8")
        content = re.sub(r'DEFAULT_PC_HOST = "[^"]+"', f'DEFAULT_PC_HOST = "{host_ip}"', content)
        return Response(content=content, media_type="text/plain; charset=utf-8")
    return Response(content="# Not found", media_type="text/plain")

@app.get("/api/termux/edith_phone.sh")
async def termux_bash_script(request: Request):
    """Termux için Bash dinleyici betiği."""
    host_ip = request.headers.get("host", "").split(":")[0] or get_local_ip()
    script_path = BASE_DIR / "scripts" / "termux" / "edith_phone.sh"
    if script_path.exists():
        content = script_path.read_text(encoding="utf-8")
        content = re.sub(r'PC_IP="\$\{1:-[^"]+\}"', f'PC_IP="${{1:-{host_ip}}}"', content)
        return Response(content=content, media_type="text/plain; charset=utf-8")
    return Response(content="# Not found", media_type="text/plain")


@app.post("/api/phone/simulate")
async def phone_simulate():
    """Örnek bir telefon çağrısını simüle eder."""
    from core.call_handler import CallHandler
    from core.chat_history import get_chat_history

    caller_name = "Ahmet Yılmaz (İş)"
    caller_num = "0532 555 0123"
    summary_text = "Yarınki proje toplantısı saat 14:00'e alındı."

    handler = CallHandler(caller_name, caller_num)
    reply = await handler.generate_reply("Merhaba Buğra orada mı? Yarınki proje toplantısı saat 14:00'e alındı, haber verebilir misin?")
    save_call_log(
        caller_name,
        caller_num,
        handler.history,
        summary=summary_text,
    )

    get_chat_history().add_message(
        role="phone_call",
        content=f"Arayan: {caller_name}. Bıraktığı Not: {summary_text}",
        source="phone",
        metadata={"caller_name": caller_name, "caller_number": caller_num, "summary": summary_text}
    )

    try:
        from discord_bot.bot import send_discord_alert
        send_discord_alert(
            title="Yeni Telefon Çağrısı Cevaplandı (Simülasyon)",
            description=f"**Not:** {summary_text}",
            caller_name=f"{caller_name} ({caller_num})",
        )
    except Exception:
        pass

    if _CALL_NOTIFY_CALLBACK:
        try:
            _CALL_NOTIFY_CALLBACK(caller_name, summary_text)
        except Exception:
            pass

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

