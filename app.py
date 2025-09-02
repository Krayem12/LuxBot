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

    # 🔹 قراءة جميع الـ placeholders الممكنة من LuxAlgo
    signal = data.get("strong_bullish_confluence", "NONE")   # اقوى إشارة شراء
    oscillator = data.get("strong_bearish_confluence", "NONE") # اقوى إشارة بيع
    price_action = data.get("reversal_any_up", "NONE")        # مثال على إشارة price action

    # 🔹 عد عدد المؤشرات النشطة
    active_signals = sum(1 for x in [signal, oscillator, price_action] if x != "NONE" and x != "false")

    # 🔹 أرسل رسالة للتليجرام إذا تحقق شرطين أو أكثر
    if active_signals >= 2:
        msg = f"📊 LuxAlgo Alert:\n"
        if signal != "NONE" and signal != "false":
            msg += f"💚 Strong Bullish Confluence: {signal}\n"
        if oscillator != "NONE" and oscillator != "false":
            msg += f"💔 Strong Bearish Confluence: {oscillator}\n"
        if price_action != "NONE" and price_action != "false":
            msg += f"⚡ Price Action Signal: {price_action}\n"
        send_telegram(msg)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
