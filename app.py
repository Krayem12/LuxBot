from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# =========================
# ⏱ إدارة تنبيهات LuxAlgo
# =========================
signal_tracker = []
MAX_WINDOW = timedelta(minutes=15)  # ربع ساعة

# 🟢 تعريف الأوزان لكل إشارة
signal_weights = {
    # Signals & Overlays
    "{bullish_confirmation+}": 3,
    "{bearish_confirmation+}": 3,
    "{bullish_contrarian+}": 2,
    "{bearish_contrarian+}": 2,

    # Price Action Concepts
    "{bullish_ibos}": 3,
    "{bearish_ibos}": 3,
    "{bullish_ichoch+}": 2,
    "{bearish_ichoch+}": 2,

    # Oscillator Matrix
    "{strong_bullish_confluence}": 3,
    "{strong_bearish_confluence}": 3,
    "{regular_bullish_hyperwave_signal}": 2,
    "{regular_bearish_hyperwave_signal}": 2
}

MIN_WEIGHT_THRESHOLD = 5  # الحد الأدنى لمجموع الأوزان للإرسال

# =========================
# 🔹 إرسال رسالة للتليجرام
# =========================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال التليجرام:", e)

# =========================
# 🔹 إرسال POST خارجي
# =========================
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

# =========================
# 🔹 معالجة التنبيهات
# =========================
def process_alerts(alerts):
    global signal_tracker
    now = datetime.utcnow()

    for alert in alerts:
        indicator = alert.get("indicator", "")
        signal = alert.get("signal", "")

        if signal in signal_weights:
            signal_tracker.append({"signal": signal, "indicator": indicator, "time": now})

    # تنظيف الإشارات الأقدم من 15 دقيقة
    signal_tracker = [s for s in signal_tracker if now - s["time"] <= MAX_WINDOW]

    # حساب مجموع الأوزان
    total_weight = sum(signal_weights.get(s["signal"], 0) for s in signal_tracker)

    # التحقق من عدد المؤشرات المختلفة
    unique_indicators = set(s["indicator"] for s in signal_tracker)

    # شرط الإرسال: مجموع الأوزان + مؤشرين مختلفين
    if total_weight >= MIN_WEIGHT_THRESHOLD and len(unique_indicators) >= 2:
        indicators_list = ", ".join(unique_indicators)
        telegram_message = f"🚀 LuxAlgo Strong Weighted Alert!\nTotal Weight: {total_weight}\nIndicators: {indicators_list}"
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)
        signal_tracker = []  # إعادة الضبط بعد الإرسال
        return True
    return False

# =========================
# 🔹 استقبال الويب هوك
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    raw_data = request.data.decode('utf-8')
    print("⚠️ Received raw webhook:", raw_data)

    try:
        data = request.get_json(force=True)
        alerts = data.get("alerts", [])
        if alerts:
            triggered = process_alerts(alerts)
            return jsonify({"status": "alert_sent" if triggered else "not_enough_signals"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200
    except Exception as e:
        print("⚠️ Invalid JSON received, ignoring. Error:", e)
        return jsonify({"status": "ignored_invalid_json"}), 200

# =========================
# 🔹 تشغيل التطبيق على Render
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
