# 📱 E.D.I.T.H — Android Termux Companion (Telefon Entegrasyonu)

Bu dizin, E.D.I.T.H projesinin Android telefon entegrasyonu için geliştirilmiş **%100 açık kaynaklı, sıfır ücretli ve hafif** arka plan dinleyicisini içerir.

> [!IMPORTANT]
> **Kural 4 Standartı:** MacroDroid gibi ücret veya abonelik talep eden üçüncü parti kısıtlı araçlar kesinlikle kullanılmaz. Android entegrasyonu tamamen açık kaynaklı Termux ve Termux:API standardı üzerine kuruludur.

---

## ⚡ Temel Yetenekler

1. **Sıfır Yapılandırma (Zero-Config UDP Discovery):**
   - Telefon ve bilgisayar aynı Wi-Fi / yerel ağa bağlı olduğunda elle IP adresi yazmanıza gerek kalmaz. UDP Port `54545` üzerinden EDITH bilgisayarı saniyeler içinde otomatik olarak bulunur ve bağlanılır.
2. **Gecikmeli Otomatik Karşılama (14 Saniye Kuralı):**
   - Gelen çağrılarda telefon çalar çalmaz anında açılmaz.
   - Kullanıcının bizzat açabilmesi için **14 saniye** beklenir.
   - Eğer 14 saniye içinde kullanıcı açmazsa, arama tam kapanmadan hemen önce otomatik olarak cevaplanır ve EDITH sekreter karşılama konuşması yapar:
     > *"Merhaba efendim. Ben Buğra'nın yapay zeka asistanı EDITH. Buğra şu anda çağrınıza doğrudan yanıt veremiyor. Lütfen notunuzu belirtiniz; kendisine ivedilikle ileteceğim."*
3. **Masaüstü Sesli Bildirimi:**
   - Telefon çaldığında veya yeni bir SMS geldiğinde bilgisayar hoparlöründen Türkçe sesli anons yapılır (`VoiceEngine: tr-TR-EmelNeural`).
   - Arama sona erdiğinde özet çağrı geçmişine (`memory/call_logs.json`) kaydedilir.
4. **Çift Yönlü Donanım Kontrolü:**
   - Bilgisayardan sesli komutla veya Mobil Web PWA Dashboard üzerinden telefona doğrudan komut verilebilir:
     - *"Ahmet'e SMS gönder: 10 dakikaya oradayım."*
     - *"Telefonun fenerini aç / kapat."*
     - *"Telefonun şarjı ne kadar?"*
     - *"Telefonun konumunu göster."*

---

## 🚀 60 Saniyede Hızlı Kurulum

### Adım 1: Termux ve Termux:API Kurulumu
Telefonunuza aşağıdaki iki açık kaynaklı uygulamayı kurun:
1. **Termux (F-Droid):** [F-Droid Termux İndir](https://f-droid.org/packages/com.termux/)
2. **Termux:API (F-Droid):** [F-Droid Termux:API İndir](https://f-droid.org/packages/com.termux.api/)

*(Not: Google Play Store'daki Termux sürümleri eski ve güncellenmemektedir. F-Droid sürümleri önerilir.)*

### Adım 2: Gerekli Android İzinleri
Telefonunuzun **Ayarlar ➔ Uygulamalar ➔ Termux** ve **Termux:API** bölümlerine giderek:
- **Telefon:** İzin ver (Arama yapma ve durumu okuma)
- **SMS:** İzin ver (SMS alma ve gönderme)
- **Kişiler & Konum:** İzin ver
- **Pil Optimizasyonu:** *Kısıtlamasız* (Ekran kapandığında arka planda kapanmaması için)

### Adım 3: Kurulum ve Çalıştırma
Termux uygulamasını açın ve aşağıdaki komutları yazın:

```bash
# Depoyu klonlayın veya termux_companion dizinini telefonunuza aktarın:
cd termux_companion

# Kurulum betiğini çalıştırın (Paketleri ve kütüphaneleri otomatik kurar):
bash install.sh

# Başlatın:
./start_edith.sh
```

---

## 🛠️ Manuel Parametreler

Eğer farklı bir alt ağdaysanız veya elle IP girmek isterseniz:

```bash
python edith_phone_node.py --pc-ip 192.168.1.50 --port 8765
```

Arka planda ekran kapalıyken kesintisiz çalışması için `termux-wake-lock` otomatik olarak devreye girer.
