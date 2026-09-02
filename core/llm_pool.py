"""
core/llm_pool.py — Multi-Provider LLM Orchestrator

Desteklenen provider'lar:
  - Ollama (yerel)
  - Google Gemini
  - OpenAI (GPT-4o, o1, o3)
  - Anthropic (Claude)
  - Groq
  - OpenRouter
  - DeepSeek
  - Mistral
  - LM Studio / yerel OpenAI-uyumlu

Fallback chain: Aktif provider başarısız olursa sıradakine geçer.

Debug: Her provider çağrısı ve fallback loglanır.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import traceback
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncGenerator, Optional

# Windows konsol Unicode desteği
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import httpx


# ══════════════════════════════════════════════════════════════════════════════
# Base Provider
# ══════════════════════════════════════════════════════════════════════════════

class BaseLLMProvider(ABC):
    """Tüm LLM provider'ların implemente etmesi gereken interface."""

    provider_name: str = "base"
    supports_vision: bool = False

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", "")
        self.vision_model = config.get("vision_model", "")
        self.api_key = config.get("api_key", "")
        self.api_url = config.get("api_url", "")
        self.temperature = float(config.get("temperature", 0.7))
        self.max_tokens = int(config.get("max_tokens", 1024))
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy HTTP client — ilk çağrıda oluştur."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Metin üret."""
        ...

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        """Görsel analiz ile metin üret. Desteklemeyen provider'lar hata fırlatır."""
        raise NotImplementedError(f"{self.provider_name} vision desteklemiyor.")

    @abstractmethod
    async def check_connection(self) -> bool:
        """Provider'a bağlantı kontrolü."""
        ...

    async def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming metin üret. Varsayılan: generate() wrapper."""
        result = await self.generate(prompt, system, temperature, max_tokens)
        yield result

    async def close(self) -> None:
        """HTTP client'ı kapat."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# ══════════════════════════════════════════════════════════════════════════════
# Ollama Provider
# ══════════════════════════════════════════════════════════════════════════════

class OllamaProvider(BaseLLMProvider):
    """Yerel Ollama üzerinden LLM erişimi. İnternet gerektirmez."""

    provider_name = "ollama"
    supports_vision = True

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.api_url:
            self.api_url = "http://localhost:11434"
        if not self.model:
            self.model = "llama3.1"
        self.top_k = int(config.get("top_k", 40))
        self.top_p = float(config.get("top_p", 0.9))

    async def check_connection(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.api_url}/api/tags")
            ok = resp.status_code == 200
            print(f"[LLMPool/Ollama] Bağlantı: {'✅' if ok else '❌'} ({self.api_url})")
            return ok
        except Exception as e:
            print(f"[LLMPool/Ollama] Bağlantı hatası: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        # System + prompt birleştir
        full_prompt = f"{system}\n\nKullanıcı: {prompt}\n\nEDITH:" if system else prompt

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "num_predict": tokens,
            },
        }

        client = await self._get_client()
        resp = await client.post(f"{self.api_url}/api/generate", json=payload)

        if resp.status_code == 200:
            data = resp.json()
            result = data.get("response", "").strip()
            print(f"[LLMPool/Ollama] ✅ Yanıt ({len(result)} karakter, model={self.model})")
            return result

        print(f"[LLMPool/Ollama] ❌ API hatası: {resp.status_code}")
        raise RuntimeError(f"Ollama API hatası: {resp.status_code}")

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        model = self.vision_model or self.model
        sys_msg = system or "Ekran görüntüsünü analiz et. Türkçe, net ve kısa cevap ver."

        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt, "images": [image_b64]},
            ],
            "options": {"temperature": 0.2, "num_predict": 512},
        }

        client = await self._get_client()
        resp = await client.post(f"{self.api_url}/api/chat", json=payload)

        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("message", {})
            text = str(msg.get("content", "")).strip() if isinstance(msg, dict) else ""
            if not text:
                text = str(data.get("response", "")).strip()
            print(f"[LLMPool/Ollama] ✅ Vision yanıt ({len(text)} kar, model={model})")
            return text

        raise RuntimeError(f"Ollama vision hatası: {resp.status_code}")

    async def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        full_prompt = f"{system}\n\nKullanıcı: {prompt}\n\nEDITH:" if system else prompt

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": {
                "temperature": temp,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "num_predict": tokens,
            },
        }

        client = await self._get_client()
        async with client.stream("POST", f"{self.api_url}/api/generate", json=payload) as resp:
            if resp.status_code != 200:
                return
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
                    except json.JSONDecodeError:
                        pass


# ══════════════════════════════════════════════════════════════════════════════
# OpenAI-Compatible Provider (OpenAI, Groq, OpenRouter, DeepSeek, LM Studio)
# ══════════════════════════════════════════════════════════════════════════════

class OpenAICompatibleProvider(BaseLLMProvider):
    """
    OpenAI Chat Completions API uyumlu provider.
    OpenAI, Groq, OpenRouter, DeepSeek, Together AI, LM Studio ile çalışır.
    """

    provider_name = "openai_compatible"
    supports_vision = True

    # Alt sınıflar için özel endpoint URL'leri
    _PROVIDER_URLS = {
        "openai": "https://api.openai.com/v1",
        "groq": "https://api.groq.com/openai/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "together": "https://api.together.xyz/v1",
        "mistral": "https://api.mistral.ai/v1",
        "nim": "https://integrate.api.nvidia.com/v1",
        "nvidia": "https://integrate.api.nvidia.com/v1",
        "local_openai": "http://localhost:1234/v1",
    }

    def __init__(self, config: dict, provider_key: str = "openai"):
        super().__init__(config)
        self.provider_name = provider_key
        if not self.api_url:
            self.api_url = self._PROVIDER_URLS.get(provider_key, "https://api.openai.com/v1")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider_name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/edith-ai"
            headers["X-Title"] = "E.D.I.T.H"
        return headers

    async def check_connection(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.api_url}/models",
                headers=self._headers(),
            )
            ok = resp.status_code == 200
            print(f"[LLMPool/{self.provider_name}] Bağlantı: {'✅' if ok else '❌'}")
            return ok
        except Exception as e:
            print(f"[LLMPool/{self.provider_name}] Bağlantı hatası: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        client = await self._get_client()
        resp = await client.post(
            f"{self.api_url}/chat/completions",
            json=payload,
            headers=self._headers(),
        )

        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            print(f"[LLMPool/{self.provider_name}] ✅ Yanıt ({len(text)} kar, model={self.model})")
            return text

        error_body = resp.text[:200]
        print(f"[LLMPool/{self.provider_name}] ❌ API hatası {resp.status_code}: {error_body}")
        raise RuntimeError(f"{self.provider_name} API hatası: {resp.status_code}")

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        model = self.vision_model or self.model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                },
            ],
        })

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        client = await self._get_client()
        resp = await client.post(
            f"{self.api_url}/chat/completions",
            json=payload,
            headers=self._headers(),
        )

        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            print(f"[LLMPool/{self.provider_name}] ✅ Vision yanıt ({len(text)} kar)")
            return text

        raise RuntimeError(f"{self.provider_name} vision hatası: {resp.status_code}")

    async def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": True,
        }

        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self.api_url}/chat/completions",
            json=payload,
            headers=self._headers(),
        ) as resp:
            if resp.status_code != 200:
                return
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        chunk = delta.get("content", "")
                        if chunk:
                            yield chunk
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass


# ══════════════════════════════════════════════════════════════════════════════
# Gemini Provider
# ══════════════════════════════════════════════════════════════════════════════

class GeminiProvider(BaseLLMProvider):
    """Google Gemini API — google-genai SDK üzerinden."""

    provider_name = "gemini"
    supports_vision = True

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.model:
            self.model = "gemini-2.0-flash"
        self._genai_client = None

    def _get_genai_client(self):
        """Lazy genai client."""
        if self._genai_client is None:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
                print(f"[LLMPool/Gemini] ✅ genai client oluşturuldu")
            except ImportError:
                raise RuntimeError(
                    "google-genai paketi kurulu değil. "
                    "Kur: pip install google-genai"
                )
        return self._genai_client

    async def check_connection(self) -> bool:
        if not self.api_key:
            print("[LLMPool/Gemini] ❌ API key yok")
            return False
        try:
            client = self._get_genai_client()
            # Basit bir test çağrısı
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=self.model,
                    contents="Say 'ok'",
                ),
            )
            ok = bool(resp.text)
            print(f"[LLMPool/Gemini] Bağlantı: {'✅' if ok else '❌'}")
            return ok
        except Exception as e:
            print(f"[LLMPool/Gemini] Bağlantı hatası: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        client = self._get_genai_client()

        config_dict = {
            "temperature": temp,
            "max_output_tokens": tokens,
        }
        if system:
            config_dict["system_instruction"] = system

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config_dict,
            ),
        )

        text = resp.text.strip() if resp.text else ""
        print(f"[LLMPool/Gemini] ✅ Yanıt ({len(text)} kar, model={self.model})")
        return text

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        from PIL import Image
        import io

        model = self.vision_model or self.model
        client = self._get_genai_client()

        # Base64 → PIL Image
        img_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(img_bytes))

        config_dict = {"temperature": 0.2, "max_output_tokens": 1024}
        if system:
            config_dict["system_instruction"] = system

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model,
                contents=[prompt, img],
                config=config_dict,
            ),
        )

        text = resp.text.strip() if resp.text else ""
        print(f"[LLMPool/Gemini] ✅ Vision yanıt ({len(text)} kar)")
        return text


# ══════════════════════════════════════════════════════════════════════════════
# Anthropic Provider
# ══════════════════════════════════════════════════════════════════════════════

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API — httpx ile doğrudan."""

    provider_name = "anthropic"
    supports_vision = True

    _API_URL = "https://api.anthropic.com/v1/messages"
    _API_VERSION = "2023-06-01"

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.model:
            self.model = "claude-sonnet-4-20250514"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self._API_VERSION,
        }

    async def check_connection(self) -> bool:
        if not self.api_key:
            print("[LLMPool/Anthropic] ❌ API key yok")
            return False
        try:
            # Kısa bir test çağrısı
            client = await self._get_client()
            resp = await client.post(
                self._API_URL,
                json={
                    "model": self.model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}],
                },
                headers=self._headers(),
            )
            ok = resp.status_code == 200
            print(f"[LLMPool/Anthropic] Bağlantı: {'✅' if ok else '❌'}")
            return ok
        except Exception as e:
            print(f"[LLMPool/Anthropic] Bağlantı hatası: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        payload: dict = {
            "model": self.model,
            "max_tokens": tokens,
            "temperature": temp,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        client = await self._get_client()
        resp = await client.post(
            self._API_URL, json=payload, headers=self._headers()
        )

        if resp.status_code == 200:
            data = resp.json()
            blocks = data.get("content", [])
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            ).strip()
            print(f"[LLMPool/Anthropic] ✅ Yanıt ({len(text)} kar, model={self.model})")
            return text

        error_body = resp.text[:200]
        print(f"[LLMPool/Anthropic] ❌ API hatası {resp.status_code}: {error_body}")
        raise RuntimeError(f"Anthropic API hatası: {resp.status_code}")

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        model = self.vision_model or self.model

        payload: dict = {
            "model": model,
            "max_tokens": 1024,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        if system:
            payload["system"] = system

        client = await self._get_client()
        resp = await client.post(
            self._API_URL, json=payload, headers=self._headers()
        )

        if resp.status_code == 200:
            data = resp.json()
            blocks = data.get("content", [])
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            ).strip()
            print(f"[LLMPool/Anthropic] ✅ Vision yanıt ({len(text)} kar)")
            return text

        raise RuntimeError(f"Anthropic vision hatası: {resp.status_code}")


# ══════════════════════════════════════════════════════════════════════════════
# Provider Factory
# ══════════════════════════════════════════════════════════════════════════════

# OpenAI-uyumlu provider'lar — hepsi aynı sınıfla farklı endpoint
_OPENAI_COMPATIBLE_KEYS = {
    "openai", "groq", "openrouter", "deepseek",
    "together", "mistral", "nim", "nvidia", "local_openai",
}


def _create_provider(name: str, config: dict) -> BaseLLMProvider:
    """Provider adına göre doğru sınıfı oluştur."""
    if name == "ollama":
        return OllamaProvider(config)
    elif name == "gemini":
        return GeminiProvider(config)
    elif name == "anthropic":
        return AnthropicProvider(config)
    elif name in _OPENAI_COMPATIBLE_KEYS:
        return OpenAICompatibleProvider(config, provider_key=name)
    else:
        # Bilinmeyen provider — OpenAI-uyumlu varsay
        print(f"[LLMPool] ⚠️ Bilinmeyen provider '{name}', OpenAI-uyumlu varsayılıyor")
        return OpenAICompatibleProvider(config, provider_key=name)


# ══════════════════════════════════════════════════════════════════════════════
# LLMPool — Ana Orchestrator
# ══════════════════════════════════════════════════════════════════════════════

class LLMPool:
    """
    Multi-provider LLM orchestrator.

    Kullanım:
        pool = LLMPool()
        pool.load_config(config_dict)
        await pool.initialize()

        response = await pool.generate("Merhaba!")
        vision   = await pool.generate_vision("Bu ne?", image_b64)
    """

    def __init__(self):
        self._providers: dict[str, BaseLLMProvider] = {}
        self._active_provider: str = "ollama"
        self._fallback_chain: list[str] = ["ollama"]
        self._initialized = False
        print("[LLMPool] 🏗️ Pool oluşturuldu")

    def load_config(self, full_config: dict) -> None:
        """Config dict'ten provider'ları yükle.

        Args:
            full_config: api_keys.json içeriği (providers dict'i dahil)
        """
        self._active_provider = full_config.get("active_provider", "ollama")
        self._fallback_chain = full_config.get("fallback_chain", ["ollama"])

        providers_cfg = full_config.get("providers", {})

        # Eski flat config format desteği (backward compat)
        if not providers_cfg and full_config.get("ollama_model"):
            providers_cfg = {
                "ollama": {
                    "enabled": True,
                    "api_url": full_config.get("ollama_api_url", "http://localhost:11434"),
                    "model": full_config.get("ollama_model", "llama3.1"),
                    "vision_model": full_config.get("ollama_vision_model", ""),
                    "temperature": full_config.get("ollama_temperature", 0.7),
                    "top_k": full_config.get("ollama_top_k", 40),
                    "top_p": full_config.get("ollama_top_p", 0.9),
                    "max_tokens": 1024,
                }
            }
            self._active_provider = "ollama"
            self._fallback_chain = ["ollama"]
            print("[LLMPool] ℹ️ Eski config formatı algılandı, Ollama olarak yüklendi")

        for name, cfg in providers_cfg.items():
            if not cfg.get("enabled", False):
                print(f"[LLMPool] ⏭️ {name} devre dışı, atlanıyor")
                continue
            try:
                provider = _create_provider(name, cfg)
                self._providers[name] = provider
                print(f"[LLMPool] ✅ {name} yüklendi (model={cfg.get('model', '?')})")
            except Exception as e:
                print(f"[LLMPool] ❌ {name} yüklenemedi: {e}")

        print(
            f"[LLMPool] Aktif: {self._active_provider} | "
            f"Chain: {self._fallback_chain} | "
            f"Yüklü: {list(self._providers.keys())}"
        )

    async def initialize(self) -> bool:
        """Aktif provider'ın bağlantısını kontrol et."""
        active = self._providers.get(self._active_provider)
        if active:
            ok = await active.check_connection()
            self._initialized = ok
            return ok

        # Aktif yoksa fallback'ten dene
        for name in self._fallback_chain:
            provider = self._providers.get(name)
            if provider:
                ok = await provider.check_connection()
                if ok:
                    self._active_provider = name
                    self._initialized = True
                    print(f"[LLMPool] ↪️ Aktif provider değiştirildi: {name}")
                    return True

        print("[LLMPool] ❌ Hiçbir provider'a bağlanılamadı!")
        return False

    def _resolve_chain(self) -> list[str]:
        """Denenecek provider sırasını döndür: aktif → fallback chain."""
        chain = [self._active_provider]
        for name in self._fallback_chain:
            if name not in chain:
                chain.append(name)
        # Yüklü olmayanları filtrele
        return [n for n in chain if n in self._providers]

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Fallback chain ile metin üret."""
        chain = self._resolve_chain()
        if not chain:
            return "Hata: Hiçbir LLM provider yapılandırılmamış."

        last_error: Exception | None = None
        for name in chain:
            provider = self._providers[name]
            try:
                result = await provider.generate(prompt, system, temperature, max_tokens)
                if result:
                    return result
            except Exception as e:
                last_error = e
                print(f"[LLMPool] ⚠️ {name} başarısız: {e}")
                traceback.print_exc()
                continue

        error_msg = str(last_error) if last_error else "Bilinmeyen hata"
        print(f"[LLMPool] ❌ Tüm provider'lar başarısız: {error_msg}")
        return ""

    async def generate_vision(
        self,
        prompt: str,
        image_b64: str,
        system: str = "",
        mime_type: str = "image/png",
    ) -> str:
        """Fallback chain ile vision üret. Sadece vision destekleyen provider'lar denenir."""
        chain = self._resolve_chain()
        vision_chain = [
            n for n in chain if self._providers[n].supports_vision
        ]
        if not vision_chain:
            return "Hata: Vision destekleyen bir provider yapılandırılmamış."

        last_error: Exception | None = None
        for name in vision_chain:
            provider = self._providers[name]
            try:
                result = await provider.generate_vision(
                    prompt, image_b64, system, mime_type
                )
                if result:
                    return result
            except Exception as e:
                last_error = e
                print(f"[LLMPool] ⚠️ {name} vision başarısız: {e}")
                continue

        error_msg = str(last_error) if last_error else "Vision hatası"
        return f"Vision analizi başarısız: {error_msg}"

    async def check_connection(self) -> bool:
        """Aktif provider bağlantı kontrolü."""
        return await self.initialize()

    async def health_check(self) -> dict[str, bool]:
        """Tüm provider'ların sağlık durumunu kontrol et."""
        results = {}
        for name, provider in self._providers.items():
            try:
                ok = await provider.check_connection()
                results[name] = ok
            except Exception:
                results[name] = False
        print(f"[LLMPool] 🏥 Sağlık kontrolü: {results}")
        return results

    def get_active_provider_name(self) -> str:
        """Aktif provider adını döndür."""
        return self._active_provider

    def get_active_model(self) -> str:
        """Aktif provider'ın model adını döndür."""
        provider = self._providers.get(self._active_provider)
        return provider.model if provider else "unknown"

    def list_providers(self) -> list[dict]:
        """UI için provider listesi."""
        result = []
        for name, provider in self._providers.items():
            result.append({
                "name": name,
                "model": provider.model,
                "active": name == self._active_provider,
                "vision": provider.supports_vision,
            })
        return result

    async def close(self) -> None:
        """Tüm provider'ların bağlantılarını kapat."""
        for provider in self._providers.values():
            await provider.close()
        print("[LLMPool] 🔌 Tüm bağlantılar kapatıldı")
