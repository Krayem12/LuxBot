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

# ✅ معالجة التنبيهات
def process_alerts(alerts):
    indicators_triggered = []

    for alert in alerts:
        indicator = alert.get("indicator", "Unknown")
        message = alert.get("message", alert.get("signal", "Raw Signal"))

        indicators_triggered.append(indicator)

    if indicators_triggered:
        indicators_list = " + ".join(indicators_triggered)
        telegram_message = f"Alert 🚀 ({len(indicators_triggered)} Signals)\n📊 Indicators: {indicators_list}\n💬 Messages: {', '.join([a.get('message', a.get('signal', '')) for a in alerts])}"
        send_post_request(telegram_message, indicators_list)
        send_telegram(telegram_message)
        return True
    return False

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
                alerts = [{"signal": raw, "indicator": "Raw Text", "message": raw}]

        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "alert_sent"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
