from flask import Flask, request
import requests

app = Flask(__name__)

# بيانات البوت
BOT_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# دالة لإرسال الرسالة للتليجرام
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        print(response.text)  # لعرض النتيجة في لوج Render
    except Exception as e:
        print("Error sending message:", e)

# نقطة النهاية لاستقبال Webhook من TradingView
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    # نجرب رسالة بسيطة عند كل Webhook
    message = "✅ إشعار من TradingView: أغلق شمعة جديدة!"
    
    # لو حبيت، يمكن تعديل الكود لاحقًا لإرسال بيانات من payload
    send_telegram(message)
    return {"status": "success"}, 200

# لتشغيل التطبيق محليًا (اختياري)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
