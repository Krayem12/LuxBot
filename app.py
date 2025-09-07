from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 ذاكرة مؤقتة لتخزين الإشارات
signal_memory = {
    "bullish": [],
    "bearish": []
}

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

# 🔹 تنظيف الإشارات القديمة (أكثر من 15 دقيقة)
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for direction in signal_memory:
        signal_memory[direction] = [(sig, ts) for sig, ts in signal_memory[direction] if ts > cutoff]

# ✅ معالجة التنبيهات مع شرط اجتماع إشارتين على الأقل
def process_alerts(alerts):
    now = datetime.utcnow()

    for alert in alerts:
        signal = alert.get("signal", "").strip()
        direction = alert.get("direction", "").strip()
        indicator = alert.get("indicator", "").strip()

        # مفتاح فريد يجمع signal + indicator + direction
        unique_key = f"{signal}_{indicator}_{direction}"

        if direction in signal_memory:
            existing_signals = [s for s, _ in signal_memory[direction]]
            if unique_key not in existing_signals:
                signal_memory[direction].append((unique_key, now))

    # تنظيف القديم
    cleanup_signals()

    # تحقق من إشارات الصعود
    if len(signal_memory["bullish"]) >= 2:
        signals = [s for s, _ in signal_memory["bullish"]]
        telegram_message = f"CALL 🚀 ({len(signals)} Signals in 15m)\n{', '.join(signals)}"
        send_post_request(telegram_message, " + ".join(signals))
        send_telegram(telegram_message)

    # تحقق من إشارات الهبوط
    if len(signal_memory["bearish"]) >= 2:
        signals = [s for s, _ in signal_memory["bearish"]]
        telegram_message = f"PUT 📉 ({len(signals)} Signals in 15m)\n{', '.join(signals)}"
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
            return jsonify({"status": "alert_processed"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

# 🔹 تشغيل التطبيق على Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
