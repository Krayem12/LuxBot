import time
from datetime import datetime, timedelta
from flask import Flask, request
import requests

app = Flask(__name__)

# ✅ بيانات التوكن والـ ID للتليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# نخزن الإشارات الواردة مؤقتاً
signals_buffer = []

# المدة الزمنية للفحص (15 دقيقة)
TIME_LIMIT = timedelta(minutes=15)

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
    timestamp = datetime.utcnow()

    # حفظ الإشارة
    signals_buffer.append((timestamp, signal_name, indicator_name))

    # تنظيف الإشارات القديمة (أكثر من 15 دقيقة)
    cutoff = datetime.utcnow() - TIME_LIMIT
    signals_buffer[:] = [s for s in signals_buffer if s[0] > cutoff]

    # ✅ الآن الشرط: إذا تحقق إشارتين أو أكثر (من أي مؤشر) خلال 15 دقيقة → يرسل تنبيه
    if len(signals_buffer) >= 2:
        unique_signals = {f"{s[1]}-{s[2]}" for s in signals_buffer}
        if len(unique_signals) >= 2:
            message = "🚨 LuxAlgo Alert:\nتحققت إشارتين أو أكثر من المؤشرات خلال 15 دقيقة ✅"
            send_telegram_alert(message)
            signals_buffer.clear()  # نبدأ من جديد بعد التنبيه

    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
