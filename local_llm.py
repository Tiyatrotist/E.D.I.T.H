"""
local_llm.py — LLM İstemci Arayüzü ve Geriye Dönük Uyumluluk Sarmalayıcısı

Bu modül, `core.llm_pool.LLMPool` üzerinde geriye dönük uyumlu bir katman sunar.
Mevcut kodun `LocalLLMClient` veya `initialize_local_llm()` çağrıları kesintisiz çalışmaya devam eder.

Debug: İstemci başlatma ve yanıt üretimleri loglanır.
"""

from __future__ import annotations

import asyncio
from typing import Optional, AsyncGenerator

from app_config import load_app_config
from core.llm_pool import LLMPool, OllamaProvider


class LocalLLMClient:
    """Multi-Provider LLMPool'u saran geriye dönük uyumlu istemci."""

    def __init__(self, model: str = "", api_url: str = ""):
        self.config = load_app_config()
        self.pool = LLMPool()
        
        # Eğer özel model veya url verildiyse config üzerine yaz
        if model:
            self.config.setdefault("providers", {}).setdefault("ollama", {})["model"] = model
        if api_url:
            self.config.setdefault("providers", {}).setdefault("ollama", {})["api_url"] = api_url

        self.pool.load_config(self.config)
        self.model = model or self.pool.get_active_model()
        self.api_url = api_url or self.config.get("providers", {}).get("ollama", {}).get("api_url", "http://localhost:11434")

    async def check_connection(self) -> bool:
        """Aktif provider'ın bağlantısını test eder."""
        print("[LocalLLMClient] Bağlantı kontrol ediliyor...")
        return await self.pool.initialize()

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_instruction: str = None,
    ) -> str:
        """Prompt'a yanıt üretir."""
        if not system_instruction:
            system_instruction = (
                "Sen EDITH'sin — Windows'ta çalışan kişisel AI asistanı. "
                "Türkçe konuş. Kısa, net ve etkili cevaplar ver. Kullanıcı sorusunu anla ve doğrudan cevap ver."
            )
        return await self.pool.generate(
            prompt=prompt,
            system=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_response_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_instruction: str = "",
    ) -> AsyncGenerator[str, None]:
        """Streaming yanıt üretir."""
        active_name = self.pool.get_active_provider_name()
        provider = self.pool._providers.get(active_name)
        if provider:
            async for chunk in provider.stream(
                prompt=prompt,
                system=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        else:
            # Fallback to simple generate
            res = await self.generate_response(prompt, temperature, max_tokens, system_instruction)
            yield res

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Chat formatında yanıt üretir."""
        prompt = self._format_chat_messages(messages)
        return await self.generate_response(prompt, temperature, max_tokens)

    def _format_chat_messages(self, messages: list[dict]) -> str:
        """Chat mesajlarını metin promptu formatına dönüştürür."""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted) + "\nASSISTANT:"

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        """Görsel analiz desteği."""
        return await self.pool.generate_vision(
            prompt=prompt,
            image_b64=image_b64,
            system=system,
            mime_type=mime_type,
        )

    async def close(self):
        """Bağlantıları kapatır."""
        await self.pool.close()


class OfflineAudioSession:
    """Ses oturumu simülasyonu."""

    def __init__(self, llm: LocalLLMClient):
        self.llm = llm
        self.running = False
        self.audio_buffer = asyncio.Queue()
        self.text_buffer = ""

    async def start(self):
        self.running = True

    async def stop(self):
        self.running = False

    async def send_audio(self, audio_chunk: bytes):
        await self.audio_buffer.put(audio_chunk)

    async def receive_text(self) -> Optional[str]:
        try:
            return self.audio_buffer.get_nowait()
        except asyncio.QueueEmpty:
            return None


async def initialize_local_llm() -> LocalLLMClient:
    """Yerel LLM havuzunu başlat ve bağlantıyı doğrula."""
    print("[EDITH] LLM Havuzu başlatılıyor...")
    llm = LocalLLMClient()

    connected = await llm.check_connection()
    if not connected:
        print("[EDITH] ⚠️ Aktif LLM provider'a bağlanılamadı, fallback zinciri deneniyor...")
        # fallback'leri initialize() zaten dener
        if not llm.pool._initialized:
            print("[EDITH] ❌ Hiçbir LLM sağlayıcısına bağlanılamadı!")
            print("[EDITH] İpucu: Yerel mod için 'ollama serve' çalıştırın veya Ayarlar'dan API anahtarınızı girin.")

    print(f"[EDITH] ✅ LLM Hazır (Aktif: {llm.pool.get_active_provider_name()} | Model: {llm.pool.get_active_model()})")
    return llm


# Uyumluluk alias'ları
Client = LocalLLMClient
