from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    bullish_count = 0
    bearish_count = 0

    # === LuxAlgo Signal & Overlays ===
    if str(data.get("bullish_confirmation+")) == "True":
        bullish_count += 1
    if str(data.get("bearish_confirmation+")) == "True":
        bearish_count += 1

    # === Oscillator Matrix ===
    if str(data.get("regular_bullish_hyperwave_signal")) == "True":
        bullish_count += 1
    if str(data.get("regular_bearish_hyperwave_signal")) == "True":
        bearish_count += 1

    # === Price Action Concepts ===
    if str(data.get("bullish_ichoch")) == "True":
        bullish_count += 1
    if str(data.get("bearish_ichoch")) == "True":
        bearish_count += 1

    # إرسال إشعار فقط إذا تحقق شرطين أو أكثر
    message = ""
    if bullish_count >= 2:
        message = f"{data.get('ticker','')} CALL"
    elif bearish_count >= 2:
        message = f"{data.get('ticker','')} PUT"

    if message:
        send_telegram(message)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
