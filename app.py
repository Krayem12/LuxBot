from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": str(message)}  # تحويل لضمان نص
    r = requests.post(url, json=payload)

    print("📤 Payload to Telegram:", payload)
    print("📥 Telegram response:", r.status_code, r.text)

# 🔹 استقبال من TradingView
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # نحاول قراءة JSON أول
        data = request.get_json(force=False, silent=True)
        
        if not data:
            # إذا ما وصل JSON، ناخذ النص الخام
            data_text = request.data.decode("utf-8")
            print("✅ Received raw webhook:", data_text)
            msg = f"📊 Raw alert: {data_text}"
        else:
            print("✅ Received webhook JSON:", data)
            msg = f"🚨 إشارة جديدة: {data.get('type', 'N/A')}\nرمز: {data.get('extras', {}).get('ticker', 'N/A')}\nسعر الإغلاق: {data.get('extras', {}).get('close', 'N/A')}"

        send_telegram(msg)
        return {"status": "ok"}, 200

    except Exception as e:
        print("❌ Error:", e)
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
