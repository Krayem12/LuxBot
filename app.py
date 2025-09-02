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

    # 🔹 استخرج القيم من نص الرسالة
    signal = data.get("signal", "NONE")
    oscillator = data.get("oscillator", "NONE")
    price_action = data.get("price_action", "NONE")
  ticker = data.get("ticker", "NONE")
    # 🔹 عد عدد المؤشرات التي ليست NONE
    active_signals = sum(1 for x in [signal, oscillator, price_action] if x != "NONE")

    # 🔹 أرسل رسالة للتليجرام إذا تحقق شرطين أو أكثر
    if active_signals >= 2:
        msg = f"📊 LuxAlgo Alert:\nSignal: {signal}\nOscillator: {oscillator}\nPrice Action: {price_action}"
        send_telegram(msg)
    
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
