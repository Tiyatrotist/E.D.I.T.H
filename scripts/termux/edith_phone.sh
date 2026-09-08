#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# scripts/termux/edith_phone.sh — E.D.I.T.H Android Termux Bash Telefon Dinleyicisi
# ==============================================================================

PC_IP="${1:-172.26.72.238}"
PORT="8080"
SERVER_URL="http://${PC_IP}:${PORT}"

echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;32m   🤖 E.D.I.T.H — Android Telefon Köprüsü (Bash)\033[0m"
echo -e "\033[1;33m   Sunucu:\033[0m ${SERVER_URL}"
echo -e "\033[1;36m========================================================\033[0m"

# Termux-API kontrolü
if ! command -v termux-notification-list &>/dev/null; then
  echo -e "\033[1;31m[HATA] termux-api paketi bulunamadı!\033[0m"
  echo "Lütfen 'pkg install termux-api jq curl' komutunu çalıştırın."
  exit 1
fi

termux-toast "EDITH Telefon Köprüsü Bağlandı!" 2>/dev/null || true

# İlk batarya bildirimi
BATTERY=$(termux-battery-status 2>/dev/null)
if [ -n "$BATTERY" ]; then
  curl -s -X POST "${SERVER_URL}/api/phone/battery" \
    -H "Content-Type: application/json" \
    -d "$BATTERY" >/dev/null 2>&1 || true
fi

echo -e "\033[1;32m[EDITH] 🟢 Dinleme devrede. Çağrılar bekleniyor...\033[0m"

IN_CALL=false
CALL_ID=""
CALLER_NAME=""
CALLER_NUM=""
CALL_START=0

while true; do
  NOTIFS=$(termux-notification-list 2>/dev/null)

  # Arama bildirimi var mı kontrol et
  CALL_NOTIF=$(echo "$NOTIFS" | jq -c '.[] | select((.packageName | test("dialer|incall|telecom|phone"; "i")) or (.tag | test("call"; "i")) or (.actions[]?.title | test("cevap|answer|yanıt"; "i")))' 2>/dev/null | head -n 1)

  if [ -n "$CALL_NOTIF" ] && [ "$IN_CALL" = false ]; then
    IN_CALL=true
    CALL_START=$(date +%s)
    CALLER_NAME=$(echo "$CALL_NOTIF" | jq -r '.title // "Bilinmeyen Numara"')
    CALLER_NUM=$(echo "$CALL_NOTIF" | jq -r '.content // ""')

    echo -e "\033[1;33m[EDITH] 🔔 GELEN ÇAĞRI: ${CALLER_NAME} (${CALLER_NUM})\033[0m"

    # EDITH'e bildir
    RESP=$(curl -s -X POST "${SERVER_URL}/api/phone/incoming_call" \
      -H "Content-Type: application/json" \
      -d "{\"caller_name\": \"${CALLER_NAME}\", \"caller_number\": \"${CALLER_NUM}\", \"source\": \"termux_bash\"}")

    CALL_ID=$(echo "$RESP" | jq -r '.call_id // empty')
    GREETING=$(echo "$RESP" | jq -r '.greeting // "Merhaba, ben Buğra nın asistanı EDITH. Nasıl yardımcı olabilirim?"')

  elif [ -z "$CALL_NOTIF" ] && [ "$IN_CALL" = true ]; then
    IN_CALL=false
    DURATION=$(( $(date +%s) - CALL_START ))
    echo -e "\033[1;36m[EDITH] 📴 ÇAĞRI BİTTİ: ${CALLER_NAME} (${DURATION}s)\033[0m"

    curl -s -X POST "${SERVER_URL}/api/phone/call_ended" \
      -H "Content-Type: application/json" \
      -d "{\"call_id\": \"${CALL_ID}\", \"caller_name\": \"${CALLER_NAME}\", \"caller_number\": \"${CALLER_NUM}\", \"duration\": ${DURATION}}" >/dev/null 2>&1 || true

    CALL_ID=""
    CALLER_NAME=""
    CALLER_NUM=""
  fi

  sleep 1
done
