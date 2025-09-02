from flask import Flask, request
import requests

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 دالة إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

# 🔹 دالة للتحقق من الإشارات
def check_signal(data, min_confirmed=2):
    layers_confirmed = 0
    details = []

    # bullish signals
    if data.get("signal") == "bullish":
        layers_confirmed += 1
        details.append("Signal: Bullish")
    if data.get("oscillator") == "bullish":
        layers_confirmed += 1
        details.append("Oscillator: Bullish")
    if data.get("price_action") == "bullish":
        layers_confirmed += 1
        details.append("Price Action: Bullish")

    # bearish signals
    if data.get("signal") == "bearish":
        layers_confirmed += 1
        details.append("Signal: Bearish")
    if data.get("oscillator") == "bearish":
        layers_confirmed += 1
        details.append("Oscillator: Bearish")
    if data.get("price_action") == "bearish":
        layers_confirmed += 1
        details.append("Price Action: Bearish")

    return layers_confirmed >= min_confirmed, details

# 🔹 Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return {"status": "error", "message": "No JSON received"}, 400

    confirmed, details = check_signal(data)
    if confirmed:
        message = "LuxAlgo Alert:\n" + "\n".join(details)
        send_telegram(message)
        return {"status": "success", "message": "Telegram alert sent"}, 200

    return {"status": "ignored", "message": "Conditions not met"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
