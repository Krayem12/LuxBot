from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 دالة إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        print("Telegram response:", response.text)
    except Exception as e:
        print("Error sending telegram:", e)

# 🔹 نقطة استقبال Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("Incoming JSON:", data)  # ✅ لطباعة كل الرسائل في اللوق

        if not data:
            return jsonify({"status": "error", "message": "No JSON received"}), 400

        # 🔹 إرسال كل رسالة مباشرة لتليجرام
        send_telegram(f"Raw Alert: {data}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# 🔹 تشغيل السيرفر
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
