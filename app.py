from flask import Flask, request
import requests

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
        if not response.ok:
            print("خطأ في إرسال الرسالة:", response.text)
    except Exception as e:
        print("خطأ في إرسال الرسالة:", e)

# 🔹 استقبال Webhook من TradingView
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("استلمنا البيانات:", data)
    if not data:
        return {"status": "error", "msg": "لا توجد بيانات"}, 400

    # إرسال أي إشارة تصل مباشرة للتليجرام
    send_telegram(f"🚨 إشارة جديدة من TradingView:\n{data}")
    return {"status": "ok"}

if __name__ == '__main__':
    # تشغيل Flask على Render
    app.run(host="0.0.0.0", port=5000)
