from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# تخزين مؤقت للإشارات
signal_memory = {
    "bullish": [],
    "bearish": []
}
signal_expiry = timedelta(minutes=15)  # مدة صلاحية الإشارة (ربع ساعة)

# 🔹 إرسال رسالة للتليجرام
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال التليجرام:", e)

# 🔹 إرسال POST خارجي
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

# ✅ تنظيف الإشارات القديمة
def cleanup_signals():
    now = datetime.utcnow()
    for direction in ["bullish", "bearish"]:
        signal_memory[direction] = [
            (sig, ts) for sig, ts in signal_memory[direction] if now - ts < signal_expiry
        ]

# ✅ معالجة التنبيهات مع شرط اجتماع إشارتين على الأقل
def process_alerts(alerts):
    now = datetime.utcnow()

    for alert in alerts:
        signal = alert.get("signal", "")
        direction = alert.get("direction", "")

        if direction in signal_memory:
            signal_memory[direction].append((signal, now))

    # تنظيف القديم
    cleanup_signals()

    # تحقق من الصعود
    if len(signal_memory["bullish"]) >= 2:
        signals = [s for s, _ in signal_memory["bullish"]]
        telegram_message = f"CALL 🚀 ({len(signals)} Signals in 15m)"
        send_post_request(telegram_message, " + ".join(signals))
        send_telegram(telegram_message)

    # تحقق من الهبوط
    if len(signal_memory["bearish"]) >= 2:
        signals = [s for s, _ in signal_memory["bearish"]]
        telegram_message = f"PUT 📉 ({len(signals)} Signals in 15m)"
        send_post_request(telegram_message, " + ".join(signals))
        send_telegram(telegram_message)

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []

        # JSON
        if request.is_json:
            data = request.get_json(force=True)
            print("Received JSON webhook:", data)
            alerts = data.get("alerts", [])
        else:
            # نص خام
            raw = request.data.decode("utf-8").strip()
            print("Received raw webhook:", raw)
            if raw:
                alerts = [{"signal": raw, "indicator": "Raw Text", "message": raw, "direction": "bullish"}]

        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "alert_received"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

# 🔹 تشغيل التطبيق على Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
