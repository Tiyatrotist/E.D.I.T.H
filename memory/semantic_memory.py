"""
memory/semantic_memory.py — E.D.I.T.H Kesintisiz Bağlam ve Uzun Vadeli Semantik Bellek Motoru

Bu modül, EDITH'in oturumlar, günler ve platformlar (Masaüstü, Discord, Mobil PWA) arasında
bağlamı asla kaybetmemesini sağlar.

Özellikler:
1. %100 Yerel ve Çevrimdışı: Ağır harici vektör veri tabanları yerine saf Python/numpy tabanlı
   TF-IDF, N-Gram ve Cosine Benzerlik vektör indeksleme motoru.
2. Otomatik Bağlam Enjeksiyonu: Kullanıcı sorgusu geldiğinde en alakalı kişisel tercihleri,
   notları, geçmiş diyalogları ve sistem bilgilerini anında tespit edip LLM sistem prompt'una ekler.
3. Çift Yönlü Persistence: memory/memory.json ve memory/chat_history.json ile tam uyumlu.
4. Otonom Bellek Araçları: remember_fact, recall_memory, forget_memory.

Debug: Semantik arama süreleri, bulunan hafıza parçacıkları ve benzerlik skorları loglanır.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
MEMORY_FILE = BASE_DIR / "memory" / "memory.json"
CHAT_HISTORY_FILE = BASE_DIR / "memory" / "chat_history.json"


def normalize_text_semantic(text: str) -> str:
    """Türkçe karakterleri, alt tireleri ve noktalama işaretlerini anlamsal karşılaştırma için normalize eder."""
    if not text:
        return ""
    text = str(text).strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = (
        text.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    # Alt tire, tire ve bölü işaretlerini boşluk yap (cat_name -> cat name)
    text = text.replace("_", " ").replace("-", " ").replace("/", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


TURKISH_SUFFIXES = [
    # Bileşik ekler (uzundan kısaya)
    "lerinizden", "larinizdan", "lerimizin", "larimizin",
    "lerinden", "larindan", "lerinde", "larinda",
    "lerini", "larini", "leriyle", "lariyla",
    "lerden", "lardan", "lerde", "larda",
    "lerin", "larin", "lerle", "larla",
    "imizden", "imizdan", "umizden", "umuzdan",
    "inize", "iniza", "inize", "iniza",
    "imizde", "imizda", "umuzda", "umuzde",
    "imizi", "imizi", "umuzu", "umuzu",
    "imizin", "imizin", "umuzun", "umuzun",
    "lerinin", "larinin",
    # İyelik + Hal ekleri
    "imin", "imin", "umun", "umun",
    "inde", "inda", "unde", "unda",
    "inden", "indan", "unden", "undan",
    "ini", "ini", "unu", "unu",
    "ine", "ina", "une", "una",
    "imle", "imla", "umle", "umla",
    # 2-3 harfli iyelik ve çoğul ekleri
    "ler", "lar", "nin", "nin", "nun", "nun",
    "min", "min", "mun", "mun",
    "ime", "ima", "ume", "uma",
    "imi", "imi", "umu", "umu",
    "den", "dan", "ten", "tan",
    "de", "da", "te", "ta",
    "ye", "ya", "ne", "na",
    "yi", "yi", "yu", "yu",
    "im", "im", "um", "um",
    "in", "in", "un", "un",
    "li", "li", "lu", "lu",
    "siz", "siz", "suz", "suz",
    "di", "di", "du", "du",
    "i", "u", "e", "a",
]

SEMANTIC_SYNONYMS: Dict[str, List[str]] = {
    # Evcil Hayvanlar
    "kedi": ["cat", "kedim", "pisik", "tekir"],
    "kedim": ["cat", "kedi"],
    "cat": ["kedi", "kedim", "tekir"],
    "kopek": ["dog", "kopegim", "it"],
    "kopegim": ["dog", "kopek"],
    "dog": ["kopek", "kopegim"],
    "hayvan": ["pet", "animal"],
    "pet": ["hayvan", "evcil"],
    # İsim / Kimlik
    "ad": ["name", "isim", "adi"],
    "adi": ["name", "isim", "ad"],
    "isim": ["name", "ad", "adi", "ismi"],
    "ismi": ["name", "ad", "adi", "isim"],
    "name": ["ad", "adi", "isim", "ismi"],
    # Müzik & Şarkı
    "sarki": ["song", "music", "muzik", "track", "parca"],
    "sarkilar": ["songs", "music", "muzik", "sarki"],
    "muzik": ["music", "song", "sarki", "track"],
    "music": ["muzik", "sarki", "song", "track"],
    "song": ["sarki", "muzik"],
    "dinle": ["listen", "play", "cal"],
    "cal": ["play", "listen", "dinle"],
    "play": ["cal", "oynat", "dinle"],
    # Not & Hafıza
    "not": ["note", "notes", "hatirlatici", "bilgi"],
    "note": ["not", "notes"],
    "notes": ["not", "notlar"],
    "hatirla": ["remember", "recall", "hafiza"],
    "hafiza": ["memory", "remember", "bellek"],
    "bellek": ["memory", "hafiza"],
    "memory": ["bellek", "hafiza"],
    # İletişim / Kişiler
    "rehber": ["contacts", "contact", "numara"],
    "contact": ["rehber", "kisi", "iletisim"],
    "contacts": ["rehber", "kisiler"],
    "telefon": ["phone", "tel", "cep"],
    "phone": ["telefon", "mobil"],
    # Proje & Kod
    "proje": ["project", "repo", "kod"],
    "project": ["proje", "repo"],
    "kod": ["code", "script", "yazilim"],
    "code": ["kod", "yazilim"],
    # Tercih
    "favori": ["favorite", "fav", "tercih"],
    "tercih": ["preference", "preferences", "favori"],
    "favorite": ["favori", "tercih"],
    "preference": ["tercih", "favori"],
}


def extract_turkish_stems(word: str) -> List[str]:
    """Kelimenin Türkçe kök türevlerini çıkarır."""
    stems = [word]
    if len(word) <= 3:
        return stems

    for suffix in TURKISH_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            stem = word[: -len(suffix)]
            if stem and stem not in stems:
                stems.append(stem)
    return stems


def expand_tokens_with_semantics(words: List[str]) -> List[str]:
    """Kelimelerden n-gram, kök ve anlamsal eşanlamlı (synonym) token listesi üretir."""
    expanded = list(words)

    # 1. Kökleri çıkar ve ekle
    for w in words:
        stems = extract_turkish_stems(w)
        for st in stems:
            if st not in expanded:
                expanded.append(st)

    # 2. Eşanlamlı ve çift dilli (TR-EN) karşılıkları ekle
    syn_additions = []
    for token in expanded:
        if token in SEMANTIC_SYNONYMS:
            for syn in SEMANTIC_SYNONYMS[token]:
                if syn not in expanded and syn not in syn_additions:
                    syn_additions.append(syn)
    expanded.extend(syn_additions)

    # 3. 2-Gram kelime öbeklerini ekle
    ngrams = extract_ngrams(words, min_n=2, max_n=2)
    expanded.extend(ngrams)

    return expanded


def extract_ngrams(tokens: List[str], min_n: int = 1, max_n: int = 3) -> List[str]:
    """Kelime listesinden 1-gram, 2-gram ve 3-gram n-gram listesi üretir."""
    ngrams = []
    length = len(tokens)
    for n in range(min_n, min(max_n + 1, length + 1)):
        for i in range(length - n + 1):
            ngram = " ".join(tokens[i : i + n])
            ngrams.append(ngram)
    return ngrams


class MemoryItem:
    """Tekil bir bellek veya hafıza kaydı."""

    def __init__(
        self,
        category: str,
        key: str,
        value: Any,
        source: str = "structured",
        timestamp: float = 0.0,
    ):
        self.category = category
        self.key = key
        self.value = value
        self.source = source
        self.timestamp = timestamp or time.time()
        self.text_representation = self._build_text()
        self.tokens = self._tokenize()
        self.token_counts = Counter(self.tokens)

    def _build_text(self) -> str:
        val_str = ""
        if isinstance(self.value, dict):
            val_str = str(self.value.get("value", self.value))
        elif isinstance(self.value, list):
            val_str = ", ".join(str(x) for x in self.value)
        else:
            val_str = str(self.value)
        return f"{self.category} {self.key} {val_str}"

    def _tokenize(self) -> List[str]:
        norm = normalize_text_semantic(self.text_representation)
        words = norm.split()
        return expand_tokens_with_semantics(words)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class SemanticMemoryEngine:
    """
    Hafif, yerel ve yüksek performanslı TF-IDF / N-Gram Cosine Vektör Bellek Motoru.
    """

    _instance: Optional["SemanticMemoryEngine"] = None
    _lock = threading.RLock()

    def __init__(self):
        self.memory_items: List[MemoryItem] = []
        self.doc_frequencies: Counter = Counter()
        self.total_docs: int = 0
        self._last_index_time: float = 0.0
        self.rebuild_index()

    @classmethod
    def get_instance(cls) -> "SemanticMemoryEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def rebuild_index(self) -> None:
        """Kalıcı bellek dosyalarını okur ve vektör arama indeksini yeniden inşa eder."""
        with self._lock:
            t0 = time.time()
            items: List[MemoryItem] = []

            # 1. memory.json yapılandırılmış verilerini oku
            if MEMORY_FILE.exists():
                try:
                    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for cat, bucket in data.items():
                            if isinstance(bucket, dict):
                                for k, v in bucket.items():
                                    items.append(MemoryItem(cat, k, v, source="memory.json"))
                            else:
                                items.append(MemoryItem("general", cat, bucket, source="memory.json"))
                except Exception as e:
                    print(f"[SemanticMemory] ⚠️ memory.json okuma uyarısı: {e}")

            # 2. chat_history.json'dan önemli kullanıcı mesajlarını ve bağlamlarını çek
            if CHAT_HISTORY_FILE.exists():
                try:
                    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                        chats = json.load(f)
                        # Son 60 mesajı incele, kullanıcı mesajlarını veya notları ekle
                        for msg in chats[-60:]:
                            content = msg.get("content", "").strip()
                            role = msg.get("role", "user")
                            if role in ("user", "assistant") and len(content) > 10:
                                items.append(
                                    MemoryItem(
                                        category=f"chat_{role}",
                                        key=f"msg_{msg.get('id', int(time.time()))}",
                                        value=content,
                                        source="chat_history.json",
                                        timestamp=msg.get("timestamp", 0.0),
                                    )
                                )
                except Exception as e:
                    print(f"[SemanticMemory] ⚠️ chat_history.json okuma uyarısı: {e}")

            # Doküman frekanslarını (DF) hesapla
            df = Counter()
            for it in items:
                unique_tokens = set(it.tokens)
                for tok in unique_tokens:
                    df[tok] += 1

            self.memory_items = items
            self.doc_frequencies = df
            self.total_docs = len(items)
            self._last_index_time = time.time()
            print(f"[SemanticMemory] 🧠 Semantik bellek indeksi güncellendi: {self.total_docs} parça ({time.time() - t0:.3f}s)")

    def _compute_vector(self, token_counts: Counter) -> Dict[str, float]:
        """TF-IDF vektör ağırlıklarını hesaplar."""
        vec = {}
        for token, count in token_counts.items():
            tf = count
            df = self.doc_frequencies.get(token, 1)
            # Düzeltilmiş IDF formülü
            idf = math.log(1.0 + (self.total_docs / (1.0 + df)))
            vec[token] = tf * idf

        # Birim vektöre normalize et (L2 norm)
        norm = math.sqrt(sum(w * w for w in vec.values()))
        if norm > 0.00001:
            for tok in vec:
                vec[tok] /= norm
        return vec

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """İki seyrek vektör arasındaki kosinüs benzerliğini hesaplar."""
        if not vec1 or not vec2:
            return 0.0
        # Daha küçük olan sözlük üzerinden dolaş
        if len(vec1) > len(vec2):
            vec1, vec2 = vec2, vec1
        dot_product = sum(weight * vec2.get(token, 0.0) for token, weight in vec1.items())
        return max(0.0, min(1.0, dot_product))

    def search_relevant_memories(
        self,
        query: str,
        top_k: int = 4,
        threshold: float = 0.12,
    ) -> List[Dict[str, Any]]:
        """
        Kullanıcı sorgusuna en uygun hafıza parçalarını kosinüs benzerlik skoruyla bulur.
        """
        if not query or not query.strip() or not self.memory_items:
            return []

        norm_query = normalize_text_semantic(query)
        words = norm_query.split()
        if not words:
            return []

        query_tokens = expand_tokens_with_semantics(words)
        q_counts = Counter(query_tokens)
        q_vec = self._compute_vector(q_counts)

        scored_results: List[Tuple[float, MemoryItem]] = []

        for item in self.memory_items:
            it_vec = self._compute_vector(item.token_counts)
            sim = self._cosine_similarity(q_vec, it_vec)

            # Doğrudan anahtar kelime eşleşmesi için bonus skor
            norm_key = normalize_text_semantic(item.key)
            norm_cat = normalize_text_semantic(item.category)
            if any(tok in norm_key or tok in norm_cat for tok in query_tokens if len(tok) >= 3):
                sim += 0.25

            # Değer içinde doğrudan alt dize geçiyorsa bonus
            val_text = str(item.value).casefold()
            if any(tok in val_text for tok in query_tokens if len(tok) >= 4):
                sim += 0.20

            if sim >= threshold:
                scored_results.append((sim, item))

        # En yüksek skora göre sırala
        scored_results.sort(key=lambda x: x[0], reverse=True)

        results = []
        seen_keys = set()
        for sim, it in scored_results:
            dedup_key = f"{it.category}:{it.key}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            d = it.to_dict()
            d["score"] = round(sim, 3)
            results.append(d)
            if len(results) >= top_k:
                break

        return results

    def format_context_for_prompt(self, query: str) -> str:
        """
        LLM'e gönderilecek temiz [HATIRLANAN BİLGİLER VE KULLANICI BAĞLAMI] bloğunu oluşturur.
        Eğer sorguyla alakalı hiçbir hafıza bulunamazsa boş string döner.
        """
        memories = self.search_relevant_memories(query, top_k=4, threshold=0.18)
        if not memories:
            return ""

        lines = ["[HATIRLANAN BİLGİLER VE KULLANICI BAĞLAMI]"]
        for m in memories:
            cat = m.get("category", "")
            key = m.get("key", "")
            val = m.get("value", "")
            if isinstance(val, dict):
                val = val.get("value", val)

            # Chat geçmişiyse diyalog olarak özetle
            if cat.startswith("chat_"):
                role_name = "Kullanıcı" if "user" in cat else "EDITH"
                lines.append(f"- Geçmiş Konuşma ({role_name}): \"{str(val)[:120]}\"")
            else:
                lines.append(f"- {cat.capitalize()} ({key}): {val}")

        lines.append("(TALİMAT: Yukarıdaki hafıza bilgilerini doğal olarak hatırla, kullanıcının bağlamından kopma.)\n\n")
        return "\n".join(lines)

    def store_fact(self, category: str, key: str, value: Any) -> Tuple[bool, str]:
        """Yeni bir kullanıcı bilgisini veya tercihini kalıcı olarak kaydeder."""
        cat = category.strip().lower() or "notes"
        k = key.strip().lower().replace(" ", "_")
        if not k:
            return False, "Geçerli bir anahtar (key) belirtilmedi."

        try:
            mem_data = {}
            if MEMORY_FILE.exists():
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    mem_data = json.load(f)

            if cat not in mem_data or not isinstance(mem_data[cat], dict):
                mem_data[cat] = {}

            mem_data[cat][k] = {"value": value, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(mem_data, f, indent=2, ensure_ascii=False)

            self.rebuild_index()
            print(f"[SemanticMemory] 💾 Hafızaya kaydedildi: [{cat}] {k} = {value}")
            return True, f"'{k}' bilgisi '{cat}' kategorisine başarıyla kaydedildi."
        except Exception as e:
            return False, f"Hafızaya kaydedilemedi: {e}"

    def delete_fact(self, category: str, key: str) -> Tuple[bool, str]:
        """Belirtilen bilgiyi kalıcı bellekten siler."""
        cat = category.strip().lower()
        k = key.strip().lower().replace(" ", "_")

        try:
            if not MEMORY_FILE.exists():
                return False, "Hafıza dosyası bulunamadı."

            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                mem_data = json.load(f)

            if cat in mem_data and isinstance(mem_data[cat], dict) and k in mem_data[cat]:
                del mem_data[cat][k]
                if not mem_data[cat]:
                    del mem_data[cat]
                with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(mem_data, f, indent=2, ensure_ascii=False)
                self.rebuild_index()
                return True, f"'{k}' bilgisi hafızadan silindi."

            # Eğer kategori belirtilmediyse tüm kategorilerde ara
            for c, bucket in list(mem_data.items()):
                if isinstance(bucket, dict) and k in bucket:
                    del bucket[k]
                    if not bucket:
                        del mem_data[c]
                    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(mem_data, f, indent=2, ensure_ascii=False)
                    self.rebuild_index()
                    return True, f"'{k}' bilgisi '{c}' kategorisinden silindi."

            return False, f"Hafızada '{k}' anahtarıyla eşleşen bir kayıt bulunamadı."
        except Exception as e:
            return False, f"Hafızadan silme hatası: {e}"

    def list_all_memories(self) -> Dict[str, Any]:
        """Tüm yapılandırılmış hafıza kayıtlarını sözlük olarak döner."""
        if not MEMORY_FILE.exists():
            return {}
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def get_semantic_memory() -> SemanticMemoryEngine:
    """Merkezi semantik bellek motorunu döndürür."""
    return SemanticMemoryEngine.get_instance()
