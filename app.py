from flask import Flask, request
import requests

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)

# 🔹 Webhook endpoint لاستقبال إشعارات TradingView
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # 🔹 قراءة الإشارات من LuxAlgo
    bullish = data.get("strong_bullish_confluence", "false")  # ارتفاع
    bearish = data.get("strong_bearish_confluence", "false")  # هبوط
    reversal_up = data.get("reversal_any_up", "false")         # إشارة صعود
    reversal_down = data.get("reversal_any_down", "false")     # إشارة هبوط

    # 🔹 تحديد نوع الإشارة
    active_signals = 0
    message = "📊 LuxAlgo Alert:\n"

    if bullish == "true" or reversal_up == "true":
        active_signals += 1
        message += "💚 Signal: CALL\n"
    if bearish == "true" or reversal_down == "true":
        active_signals += 1
        message += "💔 Signal: PUT\n"

    # 🔹 أرسل رسالة إذا تحقق شرطين أو أكثر
    if active_signals >= 2:
        send_telegram(message)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
