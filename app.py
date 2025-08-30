import time
from datetime import datetime, timedelta
from flask import Flask, request
import requests

app = Flask(__name__)

# ✅ بيانات التوكن والـ ID للتليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# نخزن الإشارات مع وقتها
signals_buffer = []

# ⏳ نافذة الزمن (15 دقيقة للتنظيم فقط، لكنها الآن غير ضرورية كثيراً لأننا نكتفي بإشارة واحدة)
TIME_WINDOW = timedelta(minutes=15)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ في إرسال الرسالة:", e)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or "signal" not in data or "indicator" not in data:
        return {"status": "error", "msg": "بيانات غير صحيحة"}, 400

    signal_name = data["signal"]
    indicator_name = data["indicator"]
    now = datetime.utcnow()

    # نخزن الإشارة الجديدة
    signals_buffer.append({"signal": signal_name, "indicator": indicator_name, "time": now})

    # حذف القديم
    cutoff = now - TIME_WINDOW
    global signals_buffer
    signals_buffer = [s for s in signals_buffer if s["time"] > cutoff]

    # ✅ إرسال تنبيه فوراً بمجرد أول إشارة
    message = f"🚨 إشارة LuxAlgo:\n✅ {signal_name} ({indicator_name})"
    send_telegram_alert(message)

    # تفريغ بعد الإرسال
    signals_buffer.clear()

    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
