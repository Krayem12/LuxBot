import time
from datetime import datetime, timedelta
from flask import Flask, request
import requests

app = Flask(__name__)

# 🔹 إعدادات Telegram
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 تخزين الإشارات
condition_tracker = {}

# 🔹 مدة فحص الإشارات (5 دقائق)
CONDITION_WINDOW = timedelta(minutes=5)

# 🔹 قائمة أقوى إشارات Bullish
BULLISH_SIGNALS = [
    "bullish_confirmation+",
    "strong_bullish_confluence",
    "regular_bullish_hyperwave_signal",
    "oversold_bullish_hyperwave_signal",
    "bullish_contrarian+"
]

# إرسال تنبيه Telegram
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ في إرسال الرسالة:", e)

# فحص شروط Bullish الثلاثة متوافقة
def check_high_confidence():
    now = datetime.utcnow()
    for indicator, signals in condition_tracker.items():
        recent_bullish = [
            s for s in signals
            if s["signal"] in BULLISH_SIGNALS and now - s["timestamp"] <= CONDITION_WINDOW
        ]
        if len(recent_bullish) >= 3:
            for s in recent_bullish:
                if not s.get("sent"):
                    msg = f"🚨 CALL 💹\n📊 {s['indicator']}\n⏱ {s['timestamp'].strftime('%H:%M:%S')}"
                    send_telegram_alert(msg)
                    s["sent"] = True

# Webhook لاستقبال إشارات LuxAlgo
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("Received webhook:", data)

    if not data or "alerts" not in data:
        return {"status": "error", "msg": "بيانات غير صحيحة"}, 400

    for alert in data["alerts"]:
        signal_name = alert.get("signal")
        indicator_name = alert.get("indicator")
        strength = alert.get("strength", 0)
        timestamp = datetime.utcnow()
        placeholders = {k: alert.get(k, "") for k in ["close", "hl2"]}

        if not signal_name or not indicator_name:
            continue

        # حفظ الإشارة
        condition_tracker.setdefault(indicator_name, []).append({
            "timestamp": timestamp,
            "signal": signal_name,
            "indicator": indicator_name,
            "strength": strength,
            "placeholders": placeholders,
            "sent": False
        })

    # تنظيف الإشارات القديمة
    cutoff = datetime.utcnow() - CONDITION_WINDOW
    for ind in condition_tracker:
        condition_tracker[ind] = [s for s in condition_tracker[ind] if s["timestamp"] > cutoff]

    # فحص شروط Bullish الثلاثة
    check_high_confidence()

    return {"status": "ok"}

# تشغيل البوت
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
