from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ✅ إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال التليجرام:", e)

# ✅ إرسال POST خارجي
def send_post_request(message, indicators):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    payload = {
        "type": message,
        "extras": {
            "indicators": indicators
        }
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال POST:", e)

# ✅ تخزين مؤقت للإشارات
alert_cache = []
CACHE_DURATION = timedelta(seconds=60)  # مدة التجميع: 60 ثانية

# ✅ معالجة الإشارات
def process_alerts(alerts):
    global alert_cache
    now = datetime.utcnow()

    # أضف الإشارات الجديدة مع وقت الوصول
    for alert in alerts:
        alert_cache.append({
            "indicator": alert.get("indicator", ""),
            "signal": alert.get("signal", ""),
            "time": now
        })

    # احتفظ بالإشارات ضمن مدة CACHE_DURATION فقط
    alert_cache = [a for a in alert_cache if now - a["time"] <= CACHE_DURATION]

    # اجمع المؤشرات والإشارات
    indicators_triggered = [a["indicator"] for a in alert_cache]
    signals_triggered = [a["signal"] for a in alert_cache]

    if len(indicators_triggered) >= 2:
        indicators_list = " + ".join(indicators_triggered)
        signals_list = " + ".join(signals_triggered)
        telegram_message = f"Signals 🚀 ({len(indicators_triggered)} Confirmed)\n📊 Indicators: {indicators_list}\n⚡ Signals: {signals_list}"
        
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)

        # بعد الإرسال، نظف التخزين المؤقت
        alert_cache.clear()
        return True
    return False

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("Received webhook:", data)

        alerts = data.get("alerts", [])
        if alerts:
            triggered = process_alerts(alerts)
            if triggered:
                return jsonify({"status": "alert_sent"}), 200
            else:
                return jsonify({"status": "not_enough_signals"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 400

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))  # Render يرسل البورت في متغير البيئة
    app.run(host="0.0.0.0", port=port)
