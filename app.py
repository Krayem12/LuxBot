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
signal_tracker = {
    "Signals & Overlays": [],
    "Price Action Concepts": [],
    "Oscillator Matrix": []
}

MAX_WINDOW = timedelta(minutes=15)  # ربع ساعة

strong_signals = {
    "Signals & Overlays": [
        "{bullish_confirmation+}", "{bearish_confirmation+}", "{bullish_contrarian+}"
    ],
    "Price Action Concepts": [
        "{bullish_ibos}", "{bearish_ibos}", "{bullish_ichoch+}"
    ],
    "Oscillator Matrix": [
        "{strong_bullish_confluence}", "{strong_bearish_confluence}", "{regular_bullish_hyperwave_signal}"
    ]
}

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
    now = datetime.utcnow()
    for alert in alerts:
        indicator = alert.get("indicator", "")
        signal = alert.get("signal", "")

        if indicator in strong_signals and signal in strong_signals[indicator]:
            signal_tracker[indicator].append(now)
            signal_tracker[indicator] = [
                t for t in signal_tracker[indicator] if now - t <= MAX_WINDOW
            ]

    active_indicators = [k for k, v in signal_tracker.items() if v]
    if len(active_indicators) >= 2:
        indicators_list = " + ".join(active_indicators)
        telegram_message = f"🚀 Strong LuxAlgo Signals!\nIndicators: {indicators_list}"
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)
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
        # 📌 لو الرسالة مو JSON → نرسلها كتليجرام نص عادي
        print("⚠️ Invalid JSON received, sending as plain text:", e)
        send_telegram(f"⚠️ Alert: {raw_data}")
        return jsonify({"status": "sent_as_text"}), 200

# =========================
# 🔹 تشغيل التطبيق على Render
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
