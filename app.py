from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = "ضع_التوكن_هنا"
CHAT_ID = "ضع_المعرف_هنا"

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": str(message)}  # تحويل لضمان نص
    r = requests.post(url, json=payload)

    print("📤 Payload to Telegram:", payload)
    print("📥 Telegram response:", r.status_code, r.text)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("✅ Received webhook:", data)

        # نرسل رسالة مبسطة أولاً
        msg = f"🚨 إشارة جديدة: {data.get('type', 'N/A')}\nرمز: {data.get('extras', {}).get('ticker', 'N/A')}\nسعر الإغلاق: {data.get('extras', {}).get('close', 'N/A')}"
        
        send_telegram(msg)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
