from flask import Flask, request
import requests

app = Flask(__name__)

# 🔹 بيانات التليقرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 إرسال رسالة للتليقرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # ✅ استخراج إشارات LuxAlgo
    signal = data.get("signal", False)          # مثال: True إذا كول أو بوت
    oscillator = data.get("oscillator", False)
    price_action = data.get("price_action", False)

    # تحويل القيم النصية أو Boolean
    layers_confirmed = sum([bool(signal), bool(oscillator), bool(price_action)])

    # 🔹 تحقق شرطين أو أكثر
    if layers_confirmed >= 2:
        message = ""
        if signal:
            message += "كول " if signal == "call" else "بوت "
        if oscillator:
            message += "كول " if oscillator == "call" else "بوت "
        if price_action:
            message += "كول " if price_action == "call" else "بوت "
        send_telegram(message.strip())

    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
