#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# scripts/termux/setup.sh — E.D.I.T.H Termux Otomatik Kurulum ve Başlatma
# ==============================================================================

PC_IP="${1:-172.26.72.238}"
PORT="8080"
SERVER_URL="http://${PC_IP}:${PORT}"

clear
echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;32m      E.D.I.T.H Termux Telefon Asistanı Kurulumu        \033[0m"
echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;33m[*] EDITH Bilgisayar IP:\033[0m ${PC_IP}"

echo -e "\n\033[1;34m[1/3] Gerekli paketler kontrol ediliyor...\033[0m"
pkg update -y >/dev/null 2>&1
pkg install -y termux-api python jq curl >/dev/null 2>&1

mkdir -p ~/edith
cd ~/edith

echo -e "\033[1;34m[2/3] Telefon köprüsü betiği indiriliyor...\033[0m"
curl -s -f -O "${SERVER_URL}/api/termux/edith_phone.py" || {
  echo -e "\033[1;31m[HATA] Bilgisayara bağlanılamadı! Bilgisayarınız ile telefonun aynı Wi-Fi ağında olduğundan emin olun.\033[0m"
  exit 1
}

mkdir -p ~/.termux/boot
cat << 'EOF' > ~/.termux/boot/edith_boot.sh
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
sleep 10
cd ~/edith && python edith_phone.py > /dev/null 2>&1 &
EOF
chmod +x ~/.termux/boot/edith_boot.sh

echo -e "\033[1;32m[3/3] Kurulum tamamlandı! Termux:Boot otomatik açılış devrede.\033[0m\n"
chmod +x edith_phone.py
python edith_phone.py "${PC_IP}"
