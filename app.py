from flask import Flask, request, jsonify
import requests

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

# ✅ معالجة التنبيهات JSON
def process_alerts(alerts):
    indicators_triggered = []

    for alert in alerts:
        indicator = alert.get("indicator", "")
        message = alert.get("message", "")

        if message == "CALL":
            indicators_triggered.append(indicator)

    if len(indicators_triggered) >= 2:
        indicators_list = " + ".join(indicators_triggered)
        telegram_message = f"CALL 🚀 ({len(indicators_triggered)} Confirmed Signals)\n📊 Indicators: {indicators_list}"
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)
        return True
    return False

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # نحاول فك JSON أولاً
        data = request.get_json(force=True, silent=True)

        if not data:  
            # رسالة نصية خام
            raw = request.data.decode("utf-8").strip()
            print("⚠️ Received raw webhook:", raw)

            # إرسال للتليجرام مباشرة
            send_telegram(f"📢 Alert: {raw}")

            return jsonify({"status": "raw_alert_sent", "message": raw}), 200

        # إذا JSON
        print("✅ Received webhook JSON:", data)

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
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
