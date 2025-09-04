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

# إرسال POST خارجي
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


# ✅ معالجة التنبيهات
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
        send_post_request(telegram_message, indicators_list)  # صححت هنا
        send_telegram(telegram_message)
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
    port = int(os.environ.get("PORT", 5000))  # يستخدم المنفذ من Render أو 5000 محلياً
    app.run(host="0.0.0.0", port=port)
