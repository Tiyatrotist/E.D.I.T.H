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
import io
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from PIL import Image
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
    <title>E.D.I.T.H // Mobil Asistan & Masaüstü Eşitliği</title>
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
            --green: #00ff88;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background: var(--bg); color: var(--text); padding-bottom: 90px; min-height: 100vh; overflow-x: hidden; }

        /* HEADER */
        .topbar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px 16px; background: rgba(4, 20, 20, 0.88); backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--panel-border); position: sticky; top: 0; z-index: 100;
        }
        .brand { font-size: 17px; font-weight: 900; letter-spacing: 2px; color: var(--primary); text-shadow: 0 0 10px var(--primary-glow); }
        .live-badge { font-size: 10px; font-weight: bold; color: var(--green); display: flex; align-items: center; gap: 5px; }
        .pulse-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); animation: blink 1.5s infinite; }
        .install-btn {
            background: var(--primary); color: var(--bg); border: none; border-radius: 4px;
            padding: 4px 8px; font-size: 10px; font-weight: bold; cursor: pointer; display: none;
            box-shadow: 0 0 8px var(--primary-glow);
        }
        .mode-select {
            background: #041818; color: var(--primary); border: 1px solid var(--panel-border);
            border-radius: 6px; padding: 4px 6px; font-size: 10px; font-weight: bold; outline: none;
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        /* TABS CONTENT */
        .tab-content { display: none; padding: 14px; animation: fadeIn 0.25s ease-out; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

        /* CARDS & PANELS */
        .card { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 12px; padding: 14px; margin-bottom: 12px; }
        .card-title { font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; color: var(--text-dim); margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }

        /* ARC REACTOR ORB */
        .orb-wrapper { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 14px 0; }
        .orb {
            width: 130px; height: 130px; border-radius: 50%;
            background: radial-gradient(circle, #022020 0%, #010a0a 70%);
            border: 2px solid var(--primary);
            box-shadow: 0 0 24px var(--primary-glow), inset 0 0 16px var(--primary-glow);
            display: flex; align-items: center; justify-content: center; position: relative;
            cursor: pointer; transition: 0.3s;
        }
        .orb:active { transform: scale(0.96); }
        .orb-ring {
            position: absolute; border-radius: 50%; border: 1px dashed var(--primary);
            width: 108px; height: 108px; animation: spin 16s linear infinite;
        }
        .orb-inner {
            width: 65px; height: 65px; border-radius: 50%; background: var(--panel);
            border: 1px solid var(--primary); display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 12px var(--primary);
        }
        .orb-state { margin-top: 8px; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; color: var(--primary); text-transform: uppercase; }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        /* CHAT STREAM */
        .chat-container {
            background: var(--panel); border: 1px solid var(--panel-border); border-radius: 12px;
            height: 240px; overflow-y: auto; padding: 12px; margin-bottom: 12px;
            display: flex; flex-direction: column; gap: 8px;
        }
        .bubble { padding: 9px 12px; border-radius: 10px; font-size: 13px; line-height: 1.45; max-width: 88%; word-wrap: break-word; }
        .bubble.user { background: #082a28; color: #fff; align-self: flex-end; border: 1px solid var(--primary); border-bottom-right-radius: 2px; }
        .bubble.bot { background: #021212; color: var(--text); align-self: flex-start; border: 1px solid var(--panel-border); border-bottom-left-radius: 2px; }
        .bubble.sys { background: transparent; color: var(--gold); align-self: center; font-size: 11px; border: none; }

        /* INPUT ROW */
        .input-bar { display: flex; gap: 8px; align-items: center; }
        .input-bar input {
            flex: 1; background: #021212; border: 1px solid var(--panel-border); border-radius: 24px;
            color: #fff; padding: 11px 16px; font-size: 14px; outline: none; transition: 0.2s;
        }
        .input-bar input:focus { border-color: var(--primary); box-shadow: 0 0 10px var(--primary-glow); }
        .btn-mic {
            width: 44px; height: 44px; border-radius: 50%; background: #032020; border: 1px solid var(--primary);
            color: var(--primary); font-size: 18px; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: 0.2s; flex-shrink: 0; box-shadow: 0 0 10px var(--primary-glow);
        }
        .btn-mic.recording { background: var(--danger); border-color: #fff; color: #fff; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
        .btn-send {
            width: 44px; height: 44px; border-radius: 50%; background: var(--primary); border: none;
            color: #000; font-size: 16px; font-weight: bold; display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: 0.2s; flex-shrink: 0;
        }

        /* LIVE SCREEN CONTAINER */
        .screen-container {
            position: relative; width: 100%; border-radius: 10px; overflow: hidden;
            border: 1px solid var(--panel-border); background: #010808; min-height: 200px;
            display: flex; align-items: center; justify-content: center; margin-bottom: 12px;
        }
        .screen-container img { width: 100%; height: auto; display: block; border-radius: 8px; }
        .screen-overlay {
            position: absolute; bottom: 8px; right: 8px; background: rgba(0, 0, 0, 0.7);
            padding: 4px 8px; border-radius: 4px; font-size: 10px; color: var(--primary);
            border: 1px solid var(--panel-border);
        }

        /* CONTROLS GRID */
        .ctrl-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .ctrl-btn {
            background: #031818; border: 1px solid var(--panel-border); border-radius: 8px;
            color: var(--text); padding: 12px 10px; font-size: 12px; font-weight: bold;
            cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px;
        }
        .ctrl-btn:active { background: var(--primary); color: #000; }
        .ctrl-btn.active { background: var(--primary); color: #000; }

        /* STATS GRID */
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .stat-box { background: #021010; border: 1px solid var(--panel-border); border-radius: 8px; padding: 10px; text-align: center; }
        .stat-num { font-size: 20px; font-weight: bold; color: #fff; margin-top: 3px; }

        /* LIVING COMPANION BADGE */
        .companion-badge {
            background: linear-gradient(135deg, #032020 0%, #063835 100%);
            border: 1px solid var(--primary); border-radius: 10px; padding: 12px; margin-bottom: 12px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .companion-info { display: flex; flex-direction: column; gap: 3px; }
        .companion-title { font-size: 10px; color: var(--text-dim); text-transform: uppercase; font-weight: bold; }
        .companion-status { font-size: 14px; font-weight: 900; color: var(--text); }

        /* FILE BROWSER */
        .file-crumbs {
            display: flex; gap: 6px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 8px;
            scrollbar-width: none; font-size: 11px;
        }
        .crumb-chip {
            background: #042020; border: 1px solid var(--panel-border); color: var(--primary);
            padding: 4px 10px; border-radius: 14px; cursor: pointer; white-space: nowrap;
        }
        .file-list { max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
        .file-item {
            background: #021010; border: 1px solid var(--panel-border); border-radius: 6px;
            padding: 9px 12px; display: flex; justify-content: space-between; align-items: center;
            cursor: pointer; transition: 0.15s; font-size: 12px;
        }
        .file-item:active { background: #082a28; }
        .file-meta { font-size: 10px; color: var(--text-dim); }

        /* BOTTOM NAVBAR */
        .bottom-nav {
            position: fixed; bottom: 0; left: 0; right: 0; height: 68px;
            background: rgba(3, 14, 14, 0.96); backdrop-filter: blur(14px);
            border-top: 1px solid var(--panel-border); display: flex; justify-content: space-around;
            align-items: center; z-index: 100; padding-bottom: env(safe-area-inset-bottom);
        }
        .nav-item {
            display: flex; flex-direction: column; align-items: center; gap: 3px;
            color: var(--text-dim); text-decoration: none; font-size: 10px; font-weight: bold;
            cursor: pointer; transition: 0.2s; padding: 6px 8px; flex: 1; text-align: center;
        }
        .nav-item.active { color: var(--primary); }
        .nav-icon { font-size: 18px; }
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
        <button id="pwaInstallBtn" class="install-btn" onclick="installPWA()">📱 YÜKLE</button>
        <div class="live-badge"><div class="pulse-dot"></div> CANLI</div>
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

    <!-- TAB 2: CANLI EKRAN & VİZYON -->
    <div id="tab-screen" class="tab-content">
        <div class="card">
            <div class="card-title">
                <span>🖥️ Bilgisayar Ekranı (Canlı)</span>
                <span id="screen-ts" style="font-size:10px; color:var(--text-dim);">Hazır</span>
            </div>
            <div class="screen-container">
                <img id="screen-img" src="/api/screen/snapshot" alt="Canlı Ekran" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'400\\' height=\\'200\\'><rect fill=\\'%23021414\\' width=\\'400\\' height=\\'200\\'/><text fill=\\'%2300d4c0\\' x=\\'50%\\' y=\\'50%\\' text-anchor=\\'middle\\'>Ekran Kilitli / Yükleniyor</text></svg>'">
                <div class="screen-overlay" id="screen-mode-tag">SNAPSHOT</div>
            </div>
            <div class="ctrl-grid">
                <button class="ctrl-btn" onclick="refreshScreen()">📸 Ekranı Yenile</button>
                <button class="ctrl-btn" id="stream-toggle-btn" onclick="toggleScreenStream()">🔄 Canlı Akış (3s)</button>
                <button class="ctrl-btn" onclick="analyzeScreenAI()">🤖 Ekranı Analiz Et</button>
                <button class="ctrl-btn" id="cam-toggle-btn" onclick="toggleCameraView()">📷 Kamerayı Gör</button>
            </div>
        </div>

        <div class="card" id="analysis-card" style="display:none;">
            <div class="card-title">👁️ Görsel Analiz Sonucu</div>
            <div id="analysis-text" style="font-size:13px; line-height:1.45; color:#fff;"></div>
        </div>

        <!-- Otonom Web Gezgini Kartı (Rule 8) -->
        <div class="card" style="border: 1px solid rgba(0, 212, 192, 0.4); background: linear-gradient(135deg, rgba(0, 212, 192, 0.08), rgba(0, 0, 0, 0.4));">
            <div class="card-title">
                <span>🌐 Otonom Web Gezgini</span>
                <span id="browser-status-badge" style="font-size:10px; color:var(--primary);">Hazır</span>
            </div>
            <div style="font-size:12px; color:var(--text-dim); margin-bottom:10px;">
                Herhangi bir linki başsız okuyun, özetletin veya dosyayı doğrudan bilgisayara indirin.
            </div>
            <input type="text" id="browser-url-input" placeholder="https://ornek.com veya dosya linki..." style="width:100%; box-sizing:border-box; background:rgba(0,0,0,0.4); border:1px solid rgba(0,212,192,0.3); border-radius:6px; padding:8px 10px; color:#fff; font-size:12px; margin-bottom:8px;">
            <div class="ctrl-grid">
                <button class="ctrl-btn" id="browser-read-btn" onclick="triggerBrowserRead()">📄 Sayfayı Oku & Özetle</button>
                <button class="ctrl-btn" id="browser-download-btn" onclick="triggerBrowserDownload()">📥 PC'ye İndir</button>
            </div>
            <div id="browser-result-box" style="display:none; margin-top:10px; padding:10px; background:rgba(0,0,0,0.6); border-radius:8px; font-size:12px; line-height:1.45; color:#fff; max-height:220px; overflow-y:auto; white-space:pre-wrap;"></div>
        </div>
    </div>

    <!-- TAB 3: UZAK DOSYALAR & TRANSFER -->
    <div id="tab-files" class="tab-content">
        <div class="card">
            <div class="card-title">
                <span>📂 PC Dosya Yöneticisi</span>
                <span onclick="loadFiles(currentPath)" style="cursor:pointer; color:var(--primary);">Yenile ↻</span>
            </div>
            <div class="file-crumbs">
                <span class="crumb-chip" onclick="loadFiles('')">🏠 Ana Dizin</span>
                <span class="crumb-chip" onclick="quickJump('Desktop')">🖥️ Masaüstü</span>
                <span class="crumb-chip" onclick="quickJump('Downloads')">📥 İndirilenler</span>
                <span class="crumb-chip" onclick="quickJump('Documents')">📄 Belgeler</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div id="current-path-label" style="font-size:10px; color:var(--text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%;">/</div>
                <button class="ctrl-btn" style="padding:4px 8px; font-size:10px;" onclick="goUpDir()">⬆️ Üst</button>
            </div>
            <div class="file-list" id="file-list-container">
                <div style="text-align:center; color:var(--text-dim); padding:16px;">Yükleniyor...</div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">📤 Telefondan PC'ye Dosya Yükle</div>
            <input type="file" id="file-upload-input" style="display:none;" onchange="handleFileUpload(this)">
            <button class="ctrl-btn" style="width:100%;" onclick="document.getElementById('file-upload-input').click()">➕ Telefondan Dosya Seç ve Gönder</button>
            <div id="upload-status" style="font-size:11px; margin-top:8px; color:var(--primary); text-align:center; display:none;"></div>
        </div>
    </div>

    <!-- TAB 4: PC KONTROL & YAŞAM REFAKATÇİSİ -->
    <div id="tab-pc" class="tab-content">
        <!-- Canlı Refakatçi Rozeti -->
        <div class="companion-badge">
            <div class="companion-info">
                <div class="companion-title">🛡️ Canlı Refakatçi Durumu</div>
                <div class="companion-status" id="companion-badge-text">💻 Hazır</div>
            </div>
            <button class="ctrl-btn" id="dnd-btn" style="padding:6px 10px; font-size:10px;" onclick="toggleDnd()">🌙 DND: KAPALI</button>
        </div>

        <div class="ctrl-grid" style="margin-bottom:12px;">
            <button class="ctrl-btn" onclick="snoozeAlerts(30)">⏱️ 30 Dk Ertele</button>
            <button class="ctrl-btn" onclick="showDailyReport()">📊 Günlük Yaşam Raporu</button>
        </div>

        <!-- Sabah Brifingi Kartı (Rule 8 Parity) -->
        <div class="card" style="border: 1px solid rgba(0, 212, 192, 0.4); background: linear-gradient(135deg, rgba(0, 212, 192, 0.08), rgba(0, 0, 0, 0.4));">
            <div class="card-title">
                <span>☕ Yönetici Sabah Brifingi</span>
                <span id="briefing-time-badge" style="font-size:10px; color:var(--primary);">Hazır</span>
            </div>
            <div style="font-size:12px; color:var(--text-dim); margin-bottom:10px;">
                Hava durumu, donanım sağlığı, bugünkü hatırlatıcılar ve telefon sekreteri çağrılarını tek tıkla özetleyin.
            </div>
            <button class="ctrl-btn" id="morning-briefing-btn" style="width:100%; border-color:var(--primary); font-weight:bold;" onclick="fetchMorningBriefing(true)">☕ Sabah Brifingi Al & Seslendir</button>
            <div id="briefing-result-box" style="display:none; margin-top:12px; padding:10px; background:rgba(0,0,0,0.5); border-radius:8px; font-size:12px; line-height:1.5; color:#fff; max-height:220px; overflow-y:auto; white-space:pre-wrap;"></div>
        </div>

        <!-- Donanım Telemetrisi -->
        <div class="card">
            <div class="card-title">⚡ Donanım Telemetrisi</div>
            <div class="stats-grid">
                <div class="stat-box">
                    <div style="font-size:10px; color:var(--text-dim);">CPU KULLANIMI</div>
                    <div class="stat-num" id="stat-cpu">--%</div>
                </div>
                <div class="stat-box">
                    <div style="font-size:10px; color:var(--text-dim);">RAM KULLANIMI</div>
                    <div class="stat-num" id="stat-ram">--%</div>
                </div>
            </div>
        </div>

        <!-- Ses & Parlaklık Kontrolleri -->
        <div class="card">
            <div class="card-title">🔊 Ses & Ekran Kontrolleri</div>
            <div class="ctrl-grid">
                <button class="ctrl-btn" onclick="sendQuickCmd('volume_up')">🔊 Ses Aç (+5)</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('volume_down')">🔉 Ses Kıs (-5)</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('volume_mute')">🔇 Sesi Sustur</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('brightness_up')">☀️ Parlaklık (+)</button>
            </div>
        </div>

        <!-- Masaüstü & Güç -->
        <div class="card">
            <div class="card-title">🖥️ Masaüstü & Güç</div>
            <div class="ctrl-grid">
                <button class="ctrl-btn" onclick="sendQuickCmd('show_desktop')">🖥️ Masaüstü</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('screen_lock')">🔒 Ekranı Kilitle</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('media_play_pause')">⏯️ Medya Oynat</button>
                <button class="ctrl-btn" onclick="sendQuickCmd('sleep')">💤 Uyku Modu</button>
            </div>
        </div>

        <!-- Hızlı Uygulama Başlatıcı -->
        <div class="card">
            <div class="card-title">🚀 Hızlı Uygulama Başlatıcı</div>
            <div class="ctrl-grid">
                <button class="ctrl-btn" onclick="launchApp('spotify')">🎧 Spotify</button>
                <button class="ctrl-btn" onclick="launchApp('chrome')">🌐 Chrome</button>
                <button class="ctrl-btn" onclick="launchApp('vscode')">💻 VS Code</button>
                <button class="ctrl-btn" onclick="launchApp('terminal')">⚡ Terminal</button>
            </div>
        </div>

        <!-- Otonom Geliştirici (Dev Agent) Kartı (Rule 8) -->
        <div class="card" style="border: 1px solid rgba(0, 212, 192, 0.4); background: linear-gradient(135deg, rgba(0, 212, 192, 0.08), rgba(0, 0, 0, 0.4));">
            <div class="card-title">
                <span>🧑‍💻 Otonom Geliştirici (Dev Agent)</span>
                <span id="dev-agent-status-badge" style="font-size:10px; color:var(--primary);">Boşta</span>
            </div>
            <div style="font-size:12px; color:var(--text-dim); margin-bottom:10px;">
                Yazılım görevini tanımlayın; EDITH kodları yazsın, lint etsin, test etsin ve çalıştırsın.
            </div>
            <div style="display:flex; gap:8px; margin-bottom:8px;">
                <input type="text" id="dev-task-input" placeholder="Örn: Fibonacci hesaplayan CLI aracı yaz..." style="flex:1; background:rgba(0,0,0,0.4); border:1px solid rgba(0,212,192,0.3); border-radius:6px; padding:8px 10px; color:#fff; font-size:12px;">
                <button class="ctrl-btn" id="dev-agent-run-btn" style="border-color:var(--primary); font-weight:bold; white-space:nowrap;" onclick="triggerDevAgent()">🚀 Başlat</button>
            </div>
            <div id="dev-agent-log-box" style="display:none; margin-top:10px; padding:10px; background:rgba(0,0,0,0.6); border-radius:8px; font-size:11px; font-family:monospace; line-height:1.4; color:#00ffcc; max-height:220px; overflow-y:auto; white-space:pre-wrap;"></div>
        </div>

        <!-- Discord Canlı Ses & Topluluk Köprüsü (Rule 8) -->
        <div class="card" style="border: 1px solid rgba(139, 92, 246, 0.4); background: linear-gradient(135deg, rgba(139, 92, 246, 0.08), rgba(0, 0, 0, 0.4));">
            <div class="card-title">
                <span>🎧 Discord Canlı Ses Köprüsü</span>
                <span id="discord-status-badge" style="font-size:10px; color:#8b5cf6;">Kontrol Ediliyor...</span>
            </div>
            <div style="font-size:12px; color:var(--text-dim); margin-bottom:10px;">
                Discord ses odasında holografik kadın sesiyle duyuru yapın veya bot eylemlerini yönetin.
            </div>
            <div style="display:flex; gap:8px; margin-bottom:8px;">
                <input type="text" id="discord-speak-input" placeholder="Ses odasında söylenecek mesaj..." style="flex:1; background:rgba(0,0,0,0.4); border:1px solid rgba(139,92,246,0.3); border-radius:6px; padding:8px 10px; color:#fff; font-size:12px;">
                <button class="ctrl-btn" id="discord-speak-btn" style="border-color:#8b5cf6; font-weight:bold; white-space:nowrap;" onclick="triggerDiscordSpeak()">🗣️ Konuş</button>
            </div>
            <div class="ctrl-grid">
                <button class="ctrl-btn" onclick="triggerDiscordAction('sound', 'chime')">🔔 Stark Chime Çal</button>
                <button class="ctrl-btn" onclick="triggerDiscordAction('leave')">📴 Odadan Ayrıl</button>
            </div>
            <div id="discord-result-box" style="display:none; margin-top:10px; padding:8px; background:rgba(0,0,0,0.6); border-radius:6px; font-size:11px; color:#cbfbf8;"></div>
        </div>
    </div>

    <!-- TAB 5: ÇAĞRILAR & SEKRETER -->
    <div id="tab-calls" class="tab-content">
        <div class="card">
            <div class="card-title">
                <span>📞 GSM Çağrı Sekreteri</span>
                <span onclick="loadCalls()" style="cursor:pointer; color:var(--primary);">Yenile ↻</span>
            </div>
            <div style="font-size:12px; color:#cbfbf8; margin-bottom:10px; line-height:1.4;">
                Gelen aramaları EDITH yanıtlar, sekreteriniz gibi konuşur ve not alır.
            </div>
            <button class="ctrl-btn" style="width:100%; margin-bottom:10px;" onclick="simulateIncomingCall()">🧪 Arama Simüle Et</button>
            <div id="call-logs-list">
                <div style="text-align:center; color:var(--text-dim); padding:16px;">Kayıtlı arama bulunmuyor.</div>
            </div>
        </div>
    </div>

    <!-- BOTTOM NAVBAR -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchTab('tab-voice', this)">
            <div class="nav-icon">🎙️</div>
            <div>Asistan</div>
        </div>
        <div class="nav-item" onclick="switchTab('tab-screen', this)">
            <div class="nav-icon">👁️</div>
            <div>Ekran</div>
        </div>
        <div class="nav-item" onclick="switchTab('tab-files', this)">
            <div class="nav-icon">📂</div>
            <div>Dosyalar</div>
        </div>
        <div class="nav-item" onclick="switchTab('tab-pc', this)">
            <div class="nav-icon">💻</div>
            <div>PC & Yaşam</div>
        </div>
        <div class="nav-item" onclick="switchTab('tab-calls', this)">
            <div class="nav-icon">📞</div>
            <div>Çağrılar</div>
        </div>
    </div>

    <!-- AUDIO ELEMENT FOR PIPER TTS -->
    <audio id="tts-audio" style="display:none;"></audio>

    <script>
        let currentTab = 'tab-voice';
        let isRecording = false;
        let recognition = null;
        let screenStreamTimer = null;
        let isCameraActive = false;
        let currentPath = '';
        let parentPath = '';

        function switchTab(tabId, el) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            el.classList.add('active');
            currentTab = tabId;

            if(tabId === 'tab-calls') loadCalls();
            if(tabId === 'tab-files' && !currentPath) loadFiles('');
            if(tabId === 'tab-screen') refreshScreen();
            if(tabId === 'tab-pc') fetchActivityStatus();
        }

        // ── 1. SES & DİNLENME ───────────────────────────────────────────────
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
            recognition.onerror = () => stopRecording();
            recognition.onend = () => stopRecording();
        }

        function toggleVoiceInput() {
            if(!recognition) {
                alert("Tarayıcınız ses tanıma desteklemiyor. Metin kutusunu kullanabilirsiniz.");
                return;
            }
            if(isRecording) recognition.stop();
            else { try { recognition.start(); } catch(e) {} }
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
            const clean = text.replace(/<[^>]+>/g, '').replace(/TOOL_CALL:[^\\n]+/g, '').trim();
            if(!clean) return;
            const audio = document.getElementById('tts-audio');
            audio.src = '/api/tts?text=' + encodeURIComponent(clean);
            audio.play().catch(e => console.log("Ses oynatılamadı:", e));
        }

        // ── 2. CANLI EKRAN & VİZYON ──────────────────────────────────────────
        function refreshScreen() {
            const img = document.getElementById('screen-img');
            const endpoint = isCameraActive ? '/api/camera/snapshot' : '/api/screen/snapshot';
            img.src = endpoint + '?t=' + Date.now();
            document.getElementById('screen-ts').innerText = new Date().toLocaleTimeString();
        }

        function toggleScreenStream() {
            const btn = document.getElementById('stream-toggle-btn');
            if(screenStreamTimer) {
                clearInterval(screenStreamTimer);
                screenStreamTimer = null;
                btn.classList.remove('active');
                btn.innerText = '🔄 Canlı Akış (3s)';
            } else {
                refreshScreen();
                screenStreamTimer = setInterval(refreshScreen, 3000);
                btn.classList.add('active');
                btn.innerText = '⏹️ Akışı Durdur';
            }
        }

        async function analyzeScreenAI() {
            appendMsg('sys', '👁️ Bilgisayar ekranı multimodal vision ile taranıyor...');
            const card = document.getElementById('analysis-card');
            const textEl = document.getElementById('analysis-text');
            card.style.display = 'block';
            textEl.innerText = 'Analiz ediliyor, lütfen bekleyin...';

            try {
                const res = await fetch('/api/screen/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: "Bu ekranda ne görüyorsun? Önemli pencereleri ve içeriği kısaca özetle."})
                });
                const d = await res.json();
                textEl.innerText = d.analysis || 'Analiz tamamlandı.';
                appendMsg('bot', '🖥️ **Ekran Analizi:** ' + (d.analysis || 'Görsel tarandı.'));
            } catch(e) {
                textEl.innerText = 'Ekran analizi başarısız oldu: ' + e;
            }
        }

        async function triggerBrowserRead() {
            const inp = document.getElementById('browser-url-input');
            const url = inp.value.trim();
            if(!url) {
                alert("Lütfen bir web adresi (URL) girin.");
                return;
            }
            const box = document.getElementById('browser-result-box');
            const badge = document.getElementById('browser-status-badge');
            box.style.display = 'block';
            box.innerText = '🌐 Web sayfası başsız olarak okunuyor ve özetleniyor...';
            badge.innerText = 'Taranıyor...';

            try {
                const res = await fetch('/api/browser/read', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url, summarize: true})
                });
                const d = await res.json();
                if(d.status === 'ok') {
                    badge.innerText = 'Okundu';
                    let output = '';
                    if(d.summary) output += '📌 **Yönetici Özeti:**\n' + d.summary + '\n\n---\n\n';
                    output += d.content;
                    box.innerText = output;
                    appendMsg('bot', '📄 **Web Sayfası İncelendi:** ' + url + '\n' + (d.summary || ''));
                } else {
                    badge.innerText = 'Hata';
                    box.innerText = '❌ ' + (d.content || 'Sayfa okunamadı.');
                }
            } catch(e) {
                badge.innerText = 'Hata';
                box.innerText = 'İstek hatası: ' + e;
            }
        }

        async function triggerBrowserDownload() {
            const inp = document.getElementById('browser-url-input');
            const url = inp.value.trim();
            if(!url) {
                alert("Lütfen indirilecek dosya adresini (URL) girin.");
                return;
            }
            const box = document.getElementById('browser-result-box');
            const badge = document.getElementById('browser-status-badge');
            box.style.display = 'block';
            box.innerText = '📥 Dosya bilgisayara indiriliyor...';
            badge.innerText = 'İndiriliyor...';

            try {
                const res = await fetch('/api/browser/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const d = await res.json();
                if(d.status === 'ok') {
                    badge.innerText = 'Tamamlandı';
                    box.innerText = '✅ ' + d.message;
                    appendMsg('sys', '📥 ' + d.message);
                } else {
                    badge.innerText = 'Hata';
                    box.innerText = '❌ ' + d.message;
                }
            } catch(e) {
                badge.innerText = 'Hata';
                box.innerText = 'İndirme hatası: ' + e;
            }
        }

        function toggleCameraView() {
            isCameraActive = !isCameraActive;
            const btn = document.getElementById('cam-toggle-btn');
            const tag = document.getElementById('screen-mode-tag');
            if(isCameraActive) {
                btn.innerText = '🖥️ Ekrana Dön';
                tag.innerText = 'WEBCAM';
            } else {
                btn.innerText = '📷 Kamerayı Gör';
                tag.innerText = 'SNAPSHOT';
            }
            refreshScreen();
        }

        // ── 3. UZAK DOSYA YÖNETİCİSİ ─────────────────────────────────────────
        async function loadFiles(path) {
            const cont = document.getElementById('file-list-container');
            cont.innerHTML = '<div style="text-align:center; color:var(--text-dim); padding:16px;">Yükleniyor...</div>';
            try {
                const res = await fetch('/api/files/list?path=' + encodeURIComponent(path || ''));
                const d = await res.json();
                if(d.status !== 'ok') {
                    cont.innerHTML = '<div style="color:var(--danger); padding:12px;">' + (d.message || 'Hata') + '</div>';
                    return;
                }
                currentPath = d.current_path;
                parentPath = d.parent_path;
                document.getElementById('current-path-label').innerText = currentPath;

                if(!d.items || d.items.length === 0) {
                    cont.innerHTML = '<div style="text-align:center; color:var(--text-dim); padding:16px;">Bu klasör boş.</div>';
                    return;
                }

                cont.innerHTML = d.items.map(item => {
                    const icon = item.is_dir ? '📁' : '📄';
                    const action = item.is_dir
                        ? `onclick="loadFiles('${item.path.replace(/\\\\/g, '/')}')"`
                        : `onclick="downloadFile('${item.path.replace(/\\\\/g, '/')}')"`;
                    const subText = item.is_dir ? 'Klasör' : item.size;
                    return `
                        <div class="file-item" ${action}>
                            <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:70%;">
                                ${icon} <b>${item.name}</b>
                            </div>
                            <div class="file-meta">
                                ${subText} ${!item.is_dir ? '⬇️' : '➔'}
                            </div>
                        </div>
                    `;
                }).join('');
            } catch(e) {
                cont.innerHTML = '<div style="color:var(--danger); padding:12px;">Dosya listesi alınamadı: ' + e + '</div>';
            }
        }

        function goUpDir() {
            if(parentPath) loadFiles(parentPath);
        }

        function quickJump(dirName) {
            loadFiles(dirName);
        }

        function downloadFile(filePath) {
            window.open('/api/files/download?path=' + encodeURIComponent(filePath), '_blank');
        }

        async function handleFileUpload(input) {
            if(!input.files || input.files.length === 0) return;
            const file = input.files[0];
            const statusEl = document.getElementById('upload-status');
            statusEl.style.display = 'block';
            statusEl.innerText = 'Yükleniyor: ' + file.name + '...';

            const formData = new FormData();
            formData.append('file', file);
            formData.append('target_dir', currentPath || '');

            try {
                const res = await fetch('/api/files/upload', {
                    method: 'POST',
                    body: formData
                });
                const d = await res.json();
                if(d.status === 'ok') {
                    statusEl.innerText = '✅ Başarıyla yüklendi: ' + file.name;
                    loadFiles(currentPath);
                } else {
                    statusEl.innerText = '❌ Yükleme hatası: ' + d.message;
                }
            } catch(e) {
                statusEl.innerText = '❌ Hata: ' + e;
            }
            setTimeout(() => { statusEl.style.display = 'none'; }, 4000);
        }

        // ── 4. PC KONTROL & YAŞAM REFAKATÇİSİ ────────────────────────────────
        async function fetchActivityStatus() {
            try {
                const res = await fetch('/api/activity/status');
                const d = await res.json();
                if(d.status === 'ok' && d.badge) {
                    document.getElementById('companion-badge-text').innerText = d.badge;
                    const dndBtn = document.getElementById('dnd-btn');
                    if(d.dnd_enabled) {
                        dndBtn.innerText = '🌙 DND: AÇIK';
                        dndBtn.classList.add('active');
                    } else {
                        dndBtn.innerText = '🌙 DND: KAPALI';
                        dndBtn.classList.remove('active');
                    }
                }
            } catch(e) {}
        }
        setInterval(fetchActivityStatus, 3000);

        async function toggleDnd() {
            try {
                const res = await fetch('/api/activity/dnd', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}' });
                const d = await res.json();
                appendMsg('sys', '🛡️ ' + d.message);
                fetchActivityStatus();
            } catch(e) {}
        }

        async function snoozeAlerts(mins) {
            try {
                const res = await fetch('/api/activity/snooze', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({minutes: mins}) });
                const d = await res.json();
                appendMsg('sys', '⏱️ ' + d.message);
            } catch(e) {}
        }

        async function showDailyReport() {
            try {
                const res = await fetch('/api/activity/report');
                const d = await res.json();
                appendMsg('bot', d.report || 'Rapor hazır.');
            } catch(e) {}
        }

        async function fetchMorningBriefing(speakDesktop) {
            const box = document.getElementById('briefing-result-box');
            const badge = document.getElementById('briefing-time-badge');
            box.style.display = 'block';
            box.innerText = '☕ Sabah brifingi hazırlanıyor, sistemler taranıyor...';
            badge.innerText = 'Alınıyor...';

            try {
                const res = await fetch('/api/briefing/trigger', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({speak_desktop: speakDesktop})
                });
                const d = await res.json();
                box.innerText = d.markdown || d.spoken || 'Brifing hazırlandı.';
                badge.innerText = d.time || 'Güncel';
                appendMsg('bot', '☕ **Sabah Brifingi:**\n' + (d.markdown || d.spoken));
                if(!speakDesktop && d.spoken) {
                    playPiperAudio(d.spoken);
                }
            } catch(e) {
                box.innerText = 'Brifing alınamadı: ' + e;
                badge.innerText = 'Hata';
            }
        }

        async function sendQuickCmd(cmd) {
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: cmd})
                });
                const d = await res.json();
                appendMsg('sys', '⚙️ ' + (d.result || 'İşlem yapıldı.'));
            } catch(e) {}
        }

        async function launchApp(appName) {
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: 'launch_app', app_name: appName})
                });
                const d = await res.json();
                appendMsg('sys', '🚀 ' + (d.result || appName + ' açılıyor...'));
            } catch(e) {}
        }

        let devPollInterval = null;

        async function triggerDevAgent() {
            const inp = document.getElementById('dev-task-input');
            const task = inp.value.trim();
            if(!task) {
                alert("Lütfen bir yazılım görevi belirtin.");
                return;
            }
            inp.value = '';
            const box = document.getElementById('dev-agent-log-box');
            const badge = document.getElementById('dev-agent-status-badge');
            box.style.display = 'block';
            box.innerText = '🚀 Otonom ajan başlatılıyor...';
            badge.innerText = 'Çalışıyor...';

            try {
                const res = await fetch('/api/dev/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({task: task})
                });
                const d = await res.json();
                appendMsg('sys', '🧑‍💻 Dev Agent görevi başlattı: ' + task);

                if(devPollInterval) clearInterval(devPollInterval);
                devPollInterval = setInterval(pollDevAgentStatus, 2000);
            } catch(e) {
                box.innerText = 'Ajan başlatılamadı: ' + e;
                badge.innerText = 'Hata';
            }
        }

        async function pollDevAgentStatus() {
            try {
                const res = await fetch('/api/dev/status');
                const d = await res.json();
                const box = document.getElementById('dev-agent-log-box');
                const badge = document.getElementById('dev-agent-status-badge');

                badge.innerText = d.status ? d.status.toUpperCase() : 'BİLİNMİYOR';
                if(d.logs && d.logs.length > 0) {
                    box.innerText = d.logs.join('\n');
                    box.scrollTop = box.scrollHeight;
                }

                if(d.status === 'completed' || d.status === 'failed') {
                    if(devPollInterval) clearInterval(devPollInterval);
                    devPollInterval = null;
                    if(d.status === 'completed') {
                        appendMsg('bot', '🎉 **Dev Agent Görevi Tamamlandı!**\nDosyalar: ' + (d.files_created || []).join(', '));
                    } else {
                        appendMsg('sys', '⚠️ Dev Agent tamamlanamadı: ' + (d.error || 'Bilinmeyen hata'));
                    }
                }
            } catch(e) {}
        }

        async function fetchDiscordStatus() {
            try {
                const res = await fetch('/api/discord/status');
                const d = await res.json();
                const badge = document.getElementById('discord-status-badge');
                if(!badge) return;
                if(d.online && d.voice && d.voice.connected) {
                    badge.innerText = '🎙️ Ses Bağlı (' + (d.voice.channel_name || 'Aktif') + ')';
                    badge.style.color = '#10B981';
                } else if(d.online) {
                    badge.innerText = '🟢 Çevrimiçi (' + (d.bot_user || 'Bot') + ')';
                    badge.style.color = '#00d4c0';
                } else {
                    badge.innerText = '⚪ Çevrimdışı';
                    badge.style.color = 'var(--text-dim)';
                }
            } catch(e) {}
        }
        setInterval(fetchDiscordStatus, 5000);
        setTimeout(fetchDiscordStatus, 1500);

        async function triggerDiscordSpeak() {
            const inp = document.getElementById('discord-speak-input');
            const text = inp.value.trim();
            if(!text) {
                alert("Lütfen ses odasında konuşulacak bir mesaj yazın.");
                return;
            }
            inp.value = '';
            const box = document.getElementById('discord-result-box');
            box.style.display = 'block';
            box.innerText = '🗣️ Ses sentezleniyor ve Discord ses odasına gönderiliyor...';

            try {
                const res = await fetch('/api/discord/speak', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text})
                });
                const d = await res.json();
                if(d.status === 'ok') {
                    box.innerText = '✅ ' + d.message;
                    appendMsg('sys', '🎧 Discord: ' + text);
                } else {
                    box.innerText = '❌ ' + (d.message || 'Hata oluştu.');
                }
            } catch(e) {
                box.innerText = 'Bağlantı hatası: ' + e;
            }
        }

        async function triggerDiscordAction(action, param) {
            const box = document.getElementById('discord-result-box');
            box.style.display = 'block';
            box.innerText = 'İşlem yürütülüyor...';

            try {
                const res = await fetch('/api/discord/action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: action, param: param || ''})
                });
                const d = await res.json();
                if(d.status === 'ok') {
                    box.innerText = '✅ ' + d.message;
                    fetchDiscordStatus();
                } else {
                    box.innerText = '❌ ' + (d.message || 'İşlem başarısız.');
                }
            } catch(e) {
                box.innerText = 'Hata: ' + e;
            }
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

        async function loadMode() {
            try {
                const res = await fetch('/api/mode');
                const data = await res.json();
                const sel = document.getElementById('mode-select');
                if (sel && data.mode) sel.value = data.mode;
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
                if (d.status === 'ok') appendMsg('sys', '⚙️ Mod Değiştirildi: ' + newMode.toUpperCase());
            } catch(e) {}
        }

        // ── 5. ÇAĞRILAR & SEKRETER ──────────────────────────────────────────
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
                    <div style="background:#021010; border:1px solid var(--panel-border); border-radius:8px; padding:10px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; font-weight:bold; font-size:13px; margin-bottom:4px;">
                            <span style="color:var(--primary);">📞 ${c.caller_name}</span>
                            <span style="font-size:10px; color:var(--text-dim);">${c.time}</span>
                        </div>
                        <div style="font-size:12px; color:var(--text-dim); line-height:1.4;">${c.summary || (c.transcript && c.transcript.length > 0 ? c.transcript[0].content : 'Görüşme tamamlandı.')}</div>
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

        // PWA Kurulum
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
                alert("EDITH'i ana ekrana eklemek için tarayıcı menüsünden 'Ana Ekrana Ekle' seçeneğine dokunun.");
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
    """Telefondan gönderilen donanım, medya ve masaüstü komutlarını yürütür."""
    action = payload.get("action", "")
    from actions.computer_control import control_computer
    from actions.desktop import manage_desktop
    from actions.open_app import open_app

    if action in ("volume_mute", "mute"):
        res = control_computer("mute")
    elif action in ("volume_up", "vol_up"):
        res = control_computer("volume_up")
    elif action in ("volume_down", "vol_down"):
        res = control_computer("volume_down")
    elif action in ("brightness_up", "bright_up"):
        res = control_computer("brightness_up")
    elif action in ("brightness_down", "bright_down"):
        res = control_computer("brightness_down")
    elif action in ("screen_lock", "lock"):
        res = control_computer("lock")
    elif action == "sleep":
        res = control_computer("sleep")
    elif action == "restart":
        res = control_computer("restart")
    elif action == "show_desktop":
        res = manage_desktop("show_desktop")
    elif action == "media_play_pause":
        res = control_computer("media_play_pause")
    elif action == "media_next":
        res = control_computer("media_next")
    elif action == "media_prev":
        res = control_computer("media_prev")
    elif action == "launch_app":
        app_name = payload.get("app_name", "chrome")
        res = open_app(app_name)
    else:
        res = f"Bilinmeyen komut: {action}"

    return {"status": "ok", "result": res}


# ── CANLI EKRAN & VİZYON UÇ NOKTALARI ────────────────────────────────────────

@app.get("/api/screen/snapshot")
async def get_screen_snapshot(quality: int = 70, max_width: int = 1280):
    """PC'nin anlık ekran görüntüsünü optimize JPEG olarak döner."""
    from actions.screen_vision import capture_screen_image

    ok, file_path_or_err, title = capture_screen_image(target="full_screen")
    if not ok or not file_path_or_err or not os.path.exists(file_path_or_err):
        # Ekran kilitli veya hata: 640x360 koyu bir placeholder oluştur
        img = Image.new("RGB", (640, 360), color=(8, 20, 20))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    try:
        with Image.open(file_path_or_err) as im:
            if im.width > max_width:
                ratio = max_width / float(im.width)
                new_h = int(im.height * ratio)
                im = im.resize((max_width, new_h), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
            return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception:
        img = Image.new("RGB", (640, 360), color=(10, 20, 20))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    finally:
        try:
            if file_path_or_err and os.path.exists(file_path_or_err):
                os.remove(file_path_or_err)
        except Exception:
            pass


@app.post("/api/screen/analyze")
async def post_screen_analyze(payload: dict = None):
    """Ekranı multimodal vision ile analiz eder."""
    from actions.screen_vision import analyze_screen
    query = (payload or {}).get("query", "Bu ekranda ne görüyorsun? Önemli pencereleri ve içeriği kısaca özetle.")
    res = analyze_screen(query=query)
    return {"status": "ok", "analysis": res}


@app.get("/api/camera/snapshot")
async def get_camera_snapshot():
    """PC kamerasından (webcam) anlık görüntü döner."""
    from actions.screen_vision import capture_camera_image

    ok, res = capture_camera_image()
    if not ok or not res or not os.path.exists(res):
        img = Image.new("RGB", (640, 480), color=(15, 15, 15))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    try:
        with Image.open(res) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=75)
            return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception:
        img = Image.new("RGB", (640, 480), color=(15, 15, 15))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    finally:
        try:
            if res and os.path.exists(res):
                os.remove(res)
        except Exception:
            pass


# ── UZAK DOSYA YÖNETİCİSİ & TRANSFER ─────────────────────────────────────────

@app.get("/api/files/list")
async def list_files(path: str = ""):
    """PC üzerindeki dizin ve dosyaları listeler."""
    p_clean = path.strip() if path else ""
    if not p_clean:
        target_dir = Path.home()
    elif p_clean.lower() == "desktop":
        target_dir = Path.home() / "Desktop"
    elif p_clean.lower() == "downloads":
        target_dir = Path.home() / "Downloads"
    elif p_clean.lower() == "documents":
        target_dir = Path.home() / "Documents"
    else:
        target_dir = Path(p_clean).resolve()

    if not target_dir.exists() or not target_dir.is_dir():
        return JSONResponse(status_code=400, content={"status": "error", "message": "Geçersiz dizin yolu"})

    items = []
    try:
        for entry in os.scandir(target_dir):
            try:
                stat = entry.stat()
                is_d = entry.is_dir()
                size_str = ""
                if not is_d:
                    sz = stat.st_size
                    if sz < 1024:
                        size_str = f"{sz} B"
                    elif sz < 1024 * 1024:
                        size_str = f"{sz/1024:.1f} KB"
                    else:
                        size_str = f"{sz/(1024*1024):.1f} MB"

                mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
                items.append({
                    "name": entry.name,
                    "path": str(Path(entry.path).resolve()),
                    "is_dir": is_d,
                    "size": size_str,
                    "size_bytes": stat.st_size if not is_d else 0,
                    "modified": mod_time,
                })
            except Exception:
                continue

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        parent_dir = str(target_dir.parent) if target_dir != target_dir.parent else ""
        return {
            "status": "ok",
            "current_path": str(target_dir),
            "parent_path": parent_dir,
            "items": items[:150],
        }
    except PermissionError:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Erişim izni reddedildi"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/files/download")
async def download_file(path: str):
    """PC'den telefona dosya indirir."""
    p = Path(path).resolve()
    if not p.exists() or not p.is_file():
        return JSONResponse(status_code=404, content={"status": "error", "message": "Dosya bulunamadı"})
    return FileResponse(path=str(p), filename=p.name, media_type="application/octet-stream")


@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...), target_dir: str = Form("")):
    """Telefondan PC'ye dosya yükler."""
    t_clean = target_dir.strip() if target_dir else ""
    dest_dir = Path(t_clean).resolve() if t_clean else (Path.home() / "Downloads")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / file.filename

    try:
        content = await file.read()
        dest_file.write_bytes(content)
        print(f"[Dashboard] 📥 Dosya başarıyla yüklendi: {dest_file} ({len(content)} byte)")
        return {
            "status": "ok",
            "message": f"Dosya başarıyla kaydedildi: {file.filename}",
            "path": str(dest_file),
            "size": len(content),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ── CANLI YAŞAM & REFAKATÇİ (ACTIVITY SUPERVISOR SYNC) ───────────────────────

@app.get("/api/activity/status")
async def get_activity_status_endpoint():
    """Canlı refakatçi ve etkinlik durumunu döner."""
    try:
        from core.activity_tracker import get_activity_tracker
        from actions.activity_supervisor import get_activity_supervisor

        tracker = get_activity_tracker()
        supervisor = get_activity_supervisor()

        return {
            "status": "ok",
            "activity": tracker.get_current_status(),
            "dnd_enabled": supervisor.dnd_enabled,
            "supervisor_enabled": supervisor.enabled,
            "badge": tracker.get_formatted_badge(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/activity/dnd")
async def post_activity_dnd(payload: dict = None):
    """Rahatsız Etme Modunu açar veya kapatır."""
    try:
        from actions.activity_supervisor import get_activity_supervisor
        supervisor = get_activity_supervisor()
        val = (payload or {}).get("enabled")
        msg = supervisor.toggle_dnd(val)
        return {"status": "ok", "dnd_enabled": supervisor.dnd_enabled, "message": msg}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/activity/snooze")
async def post_activity_snooze(payload: dict = None):
    """Mola ve uyarıları belirtilen dakika kadar erteler."""
    try:
        from actions.activity_supervisor import get_activity_supervisor
        supervisor = get_activity_supervisor()
        mins = int((payload or {}).get("minutes", 30))
        msg = supervisor.snooze(mins)
        return {"status": "ok", "message": msg}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/api/activity/report")
async def get_activity_report_endpoint():
    """Günlük etkinlik ve refakatçi özet raporunu döner."""
    try:
        from actions.activity_supervisor import get_activity_report
        return {"status": "ok", "report": get_activity_report()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── PROAKTİF SABAH BRİFİNGİ & GÜNLÜK ASİSTANLIK (RULE 8) ────────────────────

@app.get("/api/briefing")
async def get_briefing_endpoint():
    """Güncel sabah brifingi telemetrisini ve raporunu döndürür."""
    try:
        from actions.morning_briefing import get_briefing_summary_dict
        return get_briefing_summary_dict()
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/briefing/trigger")
async def post_briefing_trigger(payload: dict = None):
    """Sabah brifingini anında üretir, talep edilirse masaüstünde seslendirir."""
    try:
        from actions.morning_briefing import generate_morning_briefing, mark_briefing_completed
        speak_desktop = bool((payload or {}).get("speak_desktop", False))
        md, spoken = generate_morning_briefing(force=True)
        mark_briefing_completed()

        if speak_desktop:
            try:
                from actions.tts import speak_text
                import threading
                threading.Thread(target=lambda: speak_text(spoken, language="tr"), daemon=True).start()
            except Exception as e:
                print(f"[Dashboard] ⚠️ Masaüstü brifing seslendirme notu: {e}")

        now_time = time.strftime("%H:%M")
        return {
            "status": "ok",
            "time": now_time,
            "markdown": md,
            "spoken": spoken,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ── OTONOM GELİŞTİRİCİ & KOD AJANI (RULE 8) ──────────────────────────────────

@app.get("/api/dev/status")
async def get_dev_status_endpoint():
    """Otonom dev ajanının canlı durumunu ve loglarını döner."""
    try:
        from actions.dev_agent import get_dev_agent_status
        return get_dev_agent_status()
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/dev/run")
async def post_dev_run_endpoint(payload: dict = None):
    """Mobil panelden veya API'den otonom dev ajanını başlatır."""
    try:
        from actions.dev_agent import AutonomousDevAgent
        task = (payload or {}).get("task", "").strip()
        if not task:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Görev belirtilmedi."})

        p_dir = (payload or {}).get("project_dir", "")
        max_iters = int((payload or {}).get("max_iterations", 3) or 3)

        import threading
        def _run_worker():
            agent = AutonomousDevAgent(project_dir=p_dir, max_iterations=max_iters)
            agent.plan_and_execute(task)

        threading.Thread(target=_run_worker, daemon=True).start()

        return {
            "status": "started",
            "message": f"Dev Agent görevi başlatıldı: '{task}'",
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ── OTONOM WEB TARAYICI VE DERİN ARAŞTIRMA (RULE 8) ──────────────────────────

@app.post("/api/browser/read")
async def post_browser_read(payload: dict = None):
    """Hedef web sayfasını başsız (headless) okur ve isteğe bağlı özetler."""
    try:
        from actions.browser import scrape_and_clean_page
        url = (payload or {}).get("url", "").strip()
        if not url:
            return JSONResponse(status_code=400, content={"status": "error", "message": "URL belirtilmedi."})

        summarize = bool((payload or {}).get("summarize", True))
        ok, content = scrape_and_clean_page(url, max_chars=4000)

        summary = ""
        if ok and summarize and len(content) > 150:
            try:
                from local_llm import LocalLLMClient
                client = LocalLLMClient()
                summary = await client.generate_response(
                    prompt=f"Aşağıdaki web sayfası içeriğini 2-3 maddelik Türkçe yönetici özeti olarak özetle:\n\n{content[:2500]}",
                    system_instruction="Sen Stark Industries web analistisin. Sadece kısa ve öz Türkçe maddeleme yap.",
                    max_tokens=250,
                )
            except Exception as e:
                summary = f"Özetleme yapılamadı: {e}"

        return {
            "status": "ok" if ok else "error",
            "url": url,
            "content": content,
            "summary": summary,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/browser/download")
async def post_browser_download(payload: dict = None):
    """Web üzerinden bir dosyayı doğrudan PC'ye indirir."""
    try:
        from actions.browser import download_web_file
        url = (payload or {}).get("url", "").strip()
        if not url:
            return JSONResponse(status_code=400, content={"status": "error", "message": "İndirilecek URL belirtilmedi."})

        dest = (payload or {}).get("destination", "")
        ok, msg, path = download_web_file(url, destination_dir=dest)
        if ok:
            return {"status": "ok", "message": msg, "path": path}
        return JSONResponse(status_code=400, content={"status": "error", "message": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/browser/research")
async def post_browser_research(payload: dict = None):
    """Web üzerinde çoklu sayfalardan derin araştırma yapar."""
    try:
        from actions.browser import deep_web_research
        query = (payload or {}).get("query", "").strip()
        if not query:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Araştırma sorgusu belirtilmedi."})

        report = deep_web_research(query)
        return {"status": "ok", "report": report}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ── DISCORD CANLI SES VE TOPLULUK KÖPRÜSÜ (RULE 8) ──────────────────────────

@app.get("/api/discord/status")
async def get_discord_status():
    """Discord Bot ve ses motoru durumunu döndürür."""
    try:
        from discord_bot.bot import get_discord_bot
        from app_config import load_app_config
        cfg = load_app_config().get("discord", {})
        bot_inst = get_discord_bot()

        if not bot_inst or not hasattr(bot_inst, "bot"):
            return {
                "status": "ok",
                "enabled": cfg.get("enabled", False),
                "running": False,
                "online": False,
                "bot_user": None,
                "guilds": [],
                "voice": {"connected": False, "speaking": False},
                "primary_voice": cfg.get("tts_voice", "tr-TR-EmelNeural"),
            }

        is_ready = bool(bot_inst.bot and bot_inst.bot.is_ready())
        voice_st = bot_inst.voice_engine.get_voice_status() if hasattr(bot_inst, "voice_engine") else {}
        guild_names = [g.name for g in bot_inst.bot.guilds] if (bot_inst.bot and bot_inst.bot.guilds) else []

        return {
            "status": "ok",
            "enabled": cfg.get("enabled", False),
            "running": True,
            "online": is_ready,
            "bot_user": str(bot_inst.bot.user) if (bot_inst.bot and bot_inst.bot.user) else None,
            "guilds": guild_names,
            "voice": voice_st,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/discord/speak")
async def post_discord_speak(payload: dict = None):
    """Mobil panelden girilen metni Discord ses kanalında holografik sesle konuşur."""
    try:
        text = (payload or {}).get("text", "").strip()
        if not text:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Konuşulacak metin belirtilmedi."})

        from discord_bot.bot import get_discord_bot
        bot_inst = get_discord_bot()
        if not bot_inst or not bot_inst.voice_engine or not bot_inst.voice_engine.is_connected:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Bot herhangi bir Discord ses kanalına bağlı değil."})

        ok = await bot_inst.voice_engine.speak_text(text)
        if ok:
            return {"status": "ok", "message": f"Sesli odada konuşuldu: '{text}'"}
        return JSONResponse(status_code=500, content={"status": "error", "message": "Ses sentezlenemedi veya çalınamadı."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/discord/action")
async def post_discord_action(payload: dict = None):
    """Discord bot eylemlerini (leave, sound, mode) uzaktan yönetir."""
    try:
        action = (payload or {}).get("action", "").lower().strip()
        param = (payload or {}).get("param", "").strip()

        from discord_bot.bot import get_discord_bot
        bot_inst = get_discord_bot()
        if not bot_inst:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Discord botu aktif değil."})

        if action == "leave":
            await bot_inst.voice_engine.leave_channel()
            return {"status": "ok", "message": "Ses kanalından ayrılındı."}

        elif action in ("sound", "play_sound"):
            ok = await bot_inst.voice_engine.play_sound_effect(param or "chime")
            if ok:
                return {"status": "ok", "message": f"'{param or 'chime'}' efekti çalındı."}
            return JSONResponse(status_code=400, content={"status": "error", "message": "Efekt çalınamadı (ses odası bağlı olmalıdır)."})

        return JSONResponse(status_code=400, content={"status": "error", "message": f"Bilinmeyen eylem: {action}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


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

