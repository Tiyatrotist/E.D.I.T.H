#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# E.D.I.T.H — Android Termux Companion Otomatik Kurulum ve Başlatma Betiği
# Stark Industries — %100 Açık Kaynak / Sıfır Maliyet Standartı (Kural 4)
# ==============================================================================

set -e

echo "=================================================================="
echo "    ______      ____     ____  ______   __  __ "
echo "   / ____/     / __ \   /  _/ /_  __/  / / / / "
echo "  / __/       / / / /   / /    / /    / /_/ /  "
echo " / /___  _   / /_/ /  _/ /    / /    / __  /   "
echo "/_____/ (_) /_____/  /___/   /_/    /_/ /_/    "
echo "                                               "
echo "   STARK INDUSTRIES — ANDROID TERMUX COMPANION "
echo "=================================================================="
echo ""

echo "[1/4] 📦 Paket yöneticisi güncelleniyor..."
pkg update -y

echo "[2/4] 🛠️ Temel paketler yükleniyor (Python, Termux-API, jq)..."
pkg install -y python termux-api jq git

echo "[3/4] 🐍 Python kütüphaneleri yükleniyor (websockets, requests)..."
pip install --upgrade pip
pip install websockets requests

echo "[4/4] 🔋 Arka plan kilit ve başlatıcı betikleri hazırlanıyor..."
cat << 'EOF' > start_edith.sh
#!/data/data/com.termux/files/usr/bin/bash
# Ekran kapandığında Android'in uyumasını önle
termux-wake-lock

echo "🚀 E.D.I.T.H Telefon Düğümü başlatılıyor..."
echo "ℹ️ Çıkmak için CTRL+C tuşlarına basabilirsiniz."
python edith_phone_node.py "$@"
EOF

chmod +x start_edith.sh
chmod +x edith_phone_node.py

echo ""
echo "=================================================================="
echo "✅ KURULUM BAŞARIYLA TAMAMLANDI!"
echo "=================================================================="
echo ""
echo "📱 Kullanım:"
echo "   1. Termux:API uygulamasının telefonunuzda yüklü olduğundan emin olun."
echo "   2. Android Ayarları -> Uygulamalar -> Termux & Termux:API için:"
echo "      - Telefon (Arama yapma/cevaplama) izni verin."
echo "      - SMS (Okuma/Gönderme) izni verin."
echo "      - Konum ve Bildirim izinlerini verin."
echo "      - Pil Tasarrufu / Optimizasyonunu 'Kısıtlamasız' yapın."
echo ""
echo "🚀 Başlatmak için:"
echo "   ./start_edith.sh"
echo ""
echo "📌 Not: Bilgisayarınızla aynı Wi-Fi ağına bağlıysanız IP adresini"
echo "   yazmanıza gerek yoktur; EDITH bilgisayarı otomatik keşfedecektir."
echo "=================================================================="
