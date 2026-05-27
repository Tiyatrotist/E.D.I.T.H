"""
Yerel LLM Desteği - Ollama Entegrasyonu
Bu modül, Google Gemini yerine Ollama aracılığıyla yerel bir LLM kullanır.
İnternet bağlantısı olmadan çalışır.

Llama3.1 ile iyileştirilmiş Faster-Whisper STT desteği.
"""

import asyncio
import json
import httpx
from typing import Optional, AsyncGenerator
from app_config import get_app_config_value


class LocalLLMClient:
    """Ollama aracılığıyla Llama3.1'e bağlanır (Faster-Whisper STT optimizasyonu ile)"""
    
    def __init__(self, model: str = "mistral", api_url: str = "http://localhost:11434"):
        self.model = model or get_app_config_value("ollama_model", "mistral")
        self.api_url = api_url or get_app_config_value("ollama_api_url", "http://localhost:11434")
        self.client = httpx.AsyncClient(timeout=120)
        
    async def check_connection(self) -> bool:
        """Ollama'ya bağlı olup olmadığını kontrol et"""
        try:
            response = await self.client.get(f"{self.api_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            print(f"[LOCAL LLM] Baglanti hatasi: {e}")
            return False
    
    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_instruction: str = None,
    ) -> str:
        """Prompt'a yanıt üret (Llama3.1 tarafından)"""
        try:
            # Türkçe system instruction ekle
            if not system_instruction:
                system_instruction = """Sen EDITH'sin — Windows'ta çalışan kişisel AI asistanı.
Türkçe konuş. Kısa, net ve etkili cevaplar ver. Kullanıcı sorusunu anla ve doğrudan cevap ver."""
            
            full_prompt = f"{system_instruction}\n\nKullanıcı: {prompt}\n\nEDITH:"
            
            top_k = int(get_app_config_value("ollama_top_k", 40) or 40)
            top_p = float(get_app_config_value("ollama_top_p", 0.9) or 0.9)

            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_k": top_k,
                    "top_p": top_p,
                    "num_predict": max_tokens,
                },
            }

            response = await self.client.post(
                f"{self.api_url}/api/generate",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                print(f"[LOCAL LLM] API hatasi: {response.status_code}")
                return ""
                
        except Exception as e:
            print(f"[LOCAL LLM] Yanit uretme hatasi: {e}")
            return ""
    
    async def generate_response_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Streaming yanıt üret (gerçek zamanlı)"""
        try:
            top_k = int(get_app_config_value("ollama_top_k", 40) or 40)
            top_p = float(get_app_config_value("ollama_top_p", 0.9) or 0.9)

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "top_k": top_k,
                    "top_p": top_p,
                    "num_predict": max_tokens,
                },
            }

            async with self.client.stream(
                "POST",
                f"{self.api_url}/api/generate",
                json=payload
            ) as response:
                if response.status_code != 200:
                    print(f"[LOCAL LLM] API hatasi: {response.status_code}")
                    return
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            chunk = data.get("response", "")
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            pass
                            
        except Exception as e:
            print(f"[LOCAL LLM] Streaming hatasi: {e}")
    
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Chat formatında yanıt üret"""
        # Mesajları metin formatına dönüştür
        prompt = self._format_chat_messages(messages)
        return await self.generate_response(prompt, temperature, max_tokens)
    
    def _format_chat_messages(self, messages: list[dict]) -> str:
        """Chat mesajlarını metin promptu'na dönüştür"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted) + "\nASSISTANT:"
    
    async def close(self):
        """Bağlantıyı kapat"""
        await self.client.aclose()


class OfflineAudioSession:
    """Yerel LLM'nin gerçek zamanlı ses sesi destekleme simülasyonu"""
    
    def __init__(self, llm: LocalLLMClient):
        self.llm = llm
        self.running = False
        self.audio_buffer = asyncio.Queue()
        self.text_buffer = ""
        
    async def start(self):
        """Ses oturumunu başlat"""
        self.running = True
    
    async def stop(self):
        """Ses oturumunu durdur"""
        self.running = False
    
    async def send_audio(self, audio_chunk: bytes):
        """Ses veri gönder (gerçek zamanlı STT için)"""
        await self.audio_buffer.put(audio_chunk)
    
    async def receive_text(self) -> Optional[str]:
        """İşlenen metni al"""
        # Bu basit bir simülasyondur
        # Gerçek uygulamada speech-to-text pipeline'ı burada olurdu
        try:
            return self.audio_buffer.get_nowait()
        except asyncio.QueueEmpty:
            return None


async def initialize_local_llm() -> LocalLLMClient:
    """Yerel LLM'yi başlat ve bağlantıyı kontrol et"""
    print("[EDITH] Llama3.1 LLM baslatiliyor (Faster-Whisper STT ile)...")
    
    llm = LocalLLMClient()
    
    # Bağlantı kontrolü
    if not await llm.check_connection():
        print("[EDITH] HATA: Ollama calismiyor!")
        print("[EDITH] Lütfen 'ollama serve' komutunu çalıştırın")
        raise ConnectionError(
            "Ollama bağlantısı başarısız. "
            "Ollama'yı çalıştırın: ollama serve"
        )
    
    print("[EDITH] Yerel LLM hazir")
    return llm


# Uyumluluk alias'ları (mevcut kodu kırmamak için)
Client = LocalLLMClient
