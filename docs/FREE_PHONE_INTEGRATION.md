# E.D.I.T.H — Termux + Termux:API Telefon Entegrasyonu Rehberi

Bu rehber, Android telefonunuzdaki **Termux** ve **Termux:API** araçlarını kullanarak EDITH masaüstü asistanınızla tam uyumlu çalışan, sıfır maliyetli ve açık kaynaklı telefon köprüsünü kurmanızı sağlar.

---

## 🚀 Hızlı Başlangıç (Tek Komutla Kurulum)

Telefonunuz ile bilgisayarınızın aynı Wi-Fi ağına bağlı olduğundan emin olun.

Telefonunuzda **Termux** uygulamasını açın ve şu tek satırlık komutu yapıştırıp `Enter` tuşuna basın:

```bash
curl -s http://172.26.72.238:8080/api/termux/setup | bash
```

*(Not: Bilgisayarınızın IP adresi değişirse komuttaki `172.26.72.238` yerine yeni IP'yi yazabilirsiniz)*

Bu komut:
1. Gerekli paketleri (`termux-api`, `python`, `jq`, `curl`) otomatik kontrol eder/kurar.
2. `~/edith/edith_phone.py` köprüsünü bilgisayarınızdan indirir.
3. Arka plan çağrı dinleyicisini başlatır ve telefonunuza bir başlangıç bildirimi (toast) gönderir.

---

## 📋 Gerekli Android İzinleri (Önemli!)

Termux'un çağrıları ve bildirimleri yakalayabilmesi için **Termux:API** uygulamasının şu Android izinlerine sahip olması gerekir:

1. **Bildirim Erişimi (Notification Access):**
   - Android Ayarları → **Uygulamalar ve Bildirimler** → **Özel Uygulama Erişimi** → **Bildirim Erişimi**
   - **Termux:API** seçeneğini **Açık / İzin Verildi** yapın.
2. **Telefon ve Arama İzni:**
   - Android Ayarları → **Uygulamalar** → **Termux:API** → **İzinler**
   - **Telefon (Phone)** ve **Kişiler (Contacts)** izinlerini verin.
3. **Pil Optimizasyonunu Devre Dışı Bırakma:**
   - Termux'un ekran kapalıyken uyutulmaması için: Termux bildirim çubuğunda `Acquire Wakelock` butonuna basabilir veya Android Ayarlarında Termux için *Pil Optimizasyonunu Kapat* yapabilirsiniz.

---

## ⚡ Özellikler ve Çalışma Mantığı

### 1. Canlı Çağrı Algılama ve Masaüstü Uyarısı
- Birisi aradığında telefonunuz çalar çalmaz Termux bunu 0.8 saniye içinde yakalar.
- Bilgisayarınızdaki EDITH hoparlörden sesli olarak:
  > *"Buğra, telefonun çalıyor. Ahmet arıyor!"*
  diye uyarır ve sol HUD telemetri panelinde `PHONE_RING` kaydı oluşturur.

### 2. Tam Kapanmadan Önce Otomatik Cevaplama (14 Saniye Kuralı)
- Siz telefonunuza uzanamazsanız veya 14 saniye boyunca telefonu açmazsanız:
  - Termux çağrıyı otomatik olarak cevaplar (`input keyevent 79`).
  - Telefonun hoparlöründen Türkçe TTS sesiyle EDITH konuşur:
    > *"Merhaba, ben Buğra'nın asistanı EDITH. Ahmet, nasıl yardımcı olabilirim? Lütfen notunuzu bırakın."*

### 3. Arama Bittiğinde Masaüstü Özeti & Discord Bildirimi
- Görüşme tamamlandığında EDITH bilgisayarınızda sesli anons geçer:
  > *"Buğra, az önce Ahmet aradı. Bıraktığı not: Yarınki toplantı saat 14:00'te."*
- Arama notu `memory/chat_history.json` ve `memory/call_logs.json` dosyalarına kalıcı işlenir.
- Kullanıcı dilediği zaman *"Beni kimler aradı?"* veya *"Telefon notlarım var mı?"* diye sorduğunda EDITH anında yanıtlar.

### 4. Telefon Şarj Seviyesi Takibi
- Termux her 3 dakikada bir batarya durumunu bilgisayara iletir.
- EDITH'e *"Telefonumun şarjı kaç?"* veya *"Telefonumun pili yüzde kaç?"* diye sorduğunuzda anlık durumu bildirir.

---

## 🛠️ Manuel Çalıştırma Seçenekleri

### Python ile Çalıştırma:
```bash
cd ~/edith
python edith_phone.py
```

### Bash ile Çalıştırma (Python olmadan):
```bash
curl -s http://172.26.72.238:8080/api/termux/edith_phone.sh | bash
```

---

## 🔍 Test ve Doğrulama
Köprünün çalışıp çalışmadığını bilgisayarınızdan test etmek için:
```powershell
python tests/test_fix_verification.py
```
komutunu çalıştırabilirsiniz (Tüm testler ve API uç noktaları doğrulanmıştır).
