from flask import Flask, request
import requests
import json

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload)
        print("Telegram response:", response.text)
    except Exception as e:
        print("Telegram error:", e)

# 🔹 Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            raw_data = request.data.decode('utf-8')
            try:
                data = json.loads(raw_data)
            except:
                data = {"signal": raw_data}

        print("📩 Received Webhook:", data)

        # نرسل نفس النص بدون أي تعديل
        signal = data.get("signal", "unknown")
        send_telegram(f"🚨 LuxAlgo Signal: {signal}")

        return {"status": "ok"}, 200
    except Exception as e:
        print("❌ Error:", e)
        return {"status": "error", "message": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
