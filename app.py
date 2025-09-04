from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

last_trigger_time = None
triggered_signals = []

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ أثناء إرسال التليجرام:", e)

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

def process_alerts(alerts):
    global last_trigger_time, triggered_signals
    now = datetime.utcnow()

    if last_trigger_time is None or (now - last_trigger_time) > timedelta(minutes=15):
        triggered_signals = []
        last_trigger_time = now

    strongest_signals = {
        "Signals & Overlays": ["bullish_confirmation+", "bearish_confirmation+", "bullish_contrarian+", "bearish_contrarian+"],
        "Price Action Concepts": ["bullish_ichoch+", "bearish_ichoch+", "bullish_ibos", "bearish_ibos", "bullish_ob", "bearish_ob"],
        "Oscillator Matrix": ["strong_bullish_confluence", "strong_bearish_confluence", "regular_bullish_hyperwave_signal", "regular_bearish_hyperwave_signal"]
    }

    signal_icons = {
        "Signals & Overlays": "🔵",
        "Price Action Concepts": "🟢",
        "Oscillator Matrix": "⚡"
    }

    new_signals = []

    for alert in alerts:
        indicator_type = alert.get("indicator", "")
        signal = alert.get("signal", "")

        if indicator_type in strongest_signals:
            for sig in strongest_signals[indicator_type]:
                if sig in signal:
                    new_signals.append(f"{signal_icons[indicator_type]} {indicator_type}: {sig}")

    triggered_signals += new_signals
    triggered_signals = list(set(triggered_signals))

    indicators_present = set(sig.split(":")[0].strip() for sig in triggered_signals)
    if len(indicators_present) >= 2:
        signals_list = "\n".join(triggered_signals)
        telegram_message = f"🚀 LuxAlgo Alert ({len(triggered_signals)} Confirmed Signals)\n📊 Signals:\n{signals_list}"
        send_post_request(telegram_message, signals_list)
        send_telegram(telegram_message)
        last_trigger_time = now
        triggered_signals = []
        return True

    return False

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
    app.run(host="0.0.0.0", port=5000)
