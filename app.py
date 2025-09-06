from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

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

# ✅ معالجة التنبيهات مع شرط اجتماع إشارتين على الأقل
def process_alerts(alerts):
    bullish_signals = []
    bearish_signals = []

    for alert in alerts:
        signal = alert.get("signal", "")
        direction = alert.get("direction", "")

        if direction == "bullish":
            bullish_signals.append(signal)
        elif direction == "bearish":
            bearish_signals.append(signal)

    # إرسال CALL إذا تحقق إشارتان صاعدتان أو أكثر
    if len(bullish_signals) >= 2:
        telegram_message = f"CALL 🚀 ({len(bullish_signals)} Signals Confirmed)"
        send_post_request(telegram_message, " + ".join(bullish_signals))
        send_telegram(telegram_message)

    # إرسال PUT إذا تحقق إشارتان هابطتان أو أكثر
    if len(bearish_signals) >= 2:
        telegram_message = f"PUT 📉 ({len(bearish_signals)} Signals Confirmed)"
        send_post_request(telegram_message, " + ".join(bearish_signals))
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
            return jsonify({"status": "alert_sent"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

# 🔹 تشغيل التطبيق على Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
