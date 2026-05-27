# Llama3.1 + Faster-Whisper STT Optimization

## 🚀 Mevcut Kurulum

Llama3.1 modeli ile iyileştirme yapıldı:

### 1. **STT (Konuşma → Metin) Optimization** ✅
- **Eski**: OpenAI Whisper
- **Yeni**: **Faster-Whisper** (30-50% daha hızlı!)
  - VAD (Voice Activity Detection) ekli
  - Sessizlik filtresi aktif
  - Daha düşük latency

### 2. **TTS (Metin → Ses) Optimization** ✅
- Konuşma Hızı: `120` → `150` (daha hızlı)
- Ses Seviyesi: `1.0` → `0.95`

### 3. **LLM Model**
- Model: **Llama3.1** (stabil, iyi performans)

---

## 📦 Kurulum Adımları

### 1️⃣ Paketleri Güncelle
```bash
pip install --upgrade -r requirements.txt
```

### 2️⃣ Ollama'yı Başlat
```bash
ollama serve
```

### 3️⃣ EDITH Uygulamasını Çalıştır
```bash
python main.py
```

---

## ⚡ Performans Beklentileri

| Adım | Öncesi | Sonrası |
|------|--------|---------|
| Konuşma → Metin (STT) | 3-5s | **1.5-2.5s** ⚡ |
| LLM Cevabı | 2-3s | **2-3s** (Llama3.1 standart) |
| Metin → Ses (TTS) | 1-2s | **0.5-1s** ⚡ |
| **Toplam latency** | **6-10s** | **4-6.5s (30% daha hızlı)** ⚡ |

---

## 🔧 Konfigürasyon

Dosya: `config/api_keys.json`

```json
{
    "ollama_model": "llama3.1",
    "ollama_temperature": 0.7,
    "ollama_top_k": 40,
    "ollama_top_p": 0.9,
    "tts_rate": 150,
    "tts_volume": 0.95,
    "stt_model": "small"
}
```

### İnce Ayarlar:

- **Daha hızlı STT?** → `stt_model` "tiny"'ye değiştir (daha hızlı ama daha az doğru)
- **Daha doğru STT?** → `stt_model` "medium"'a değiştir (daha yavaş ama daha doğru)
- **Daha hızlı TTS?** → `tts_rate` 200'e yükselt
- **Daha yavaş TTS?** → `tts_rate` 100'e düşür

---

## 🎤 Ses Modülü Detayları

### STT Pipeline:
1. PyAudio ile mikrofon kayıdı (16kHz, mono)
2. **Faster-Whisper** ile transkripsiyon
3. VAD filtresi ile sessizlik kaldırma
4. Halüsinasyon filtresi uygulanır

### TTS Pipeline:
1. Gemma 4 e4b yanıtı alındı
2. Pyttsx3 veya Windows SAPI ile okunur
3. Türkçe ses seçilir (varsa)

---

## ✅ Kontrol Listesi

- [ ] `requirements.txt` güncellendi (`pip install -r requirements.txt`)
- [ ] Ollama servisi çalışıyor (`ollama serve`)
- [ ] Mikrofon test edildi (`python _check_audio.py`)
- [ ] EDITH başlatıldı ve ses çalışıyor (`python main.py`)

---

## 🆘 Sorun Giderme

### Ollama bağlantısı başarısız?
```bash
ollama serve  # Ayrı bir terminal'de
```

### Faster-Whisper modeli download edilmiyor?
```bash
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small')"
```

### Ses detektlenmiyor?
```bash
python _check_audio.py
```

### Llama3.1 çalışmıyor?
```bash
ollama list  # Modelleri kontrol et
ollama pull llama3.1  # Eğer yoksa indir
```

---

## 📚 Kaynaklar

- **Llama**: https://huggingface.co/meta-llama/Llama-3.1
- **Faster-Whisper**: https://github.com/SYSTRAN/faster-whisper
- **Ollama**: https://ollama.ai

