import time
from datetime import datetime, timedelta
from flask import Flask, request
import threading
import requests

app = Flask(__name__)

# ✅ بيانات التوكن والـ ID للتليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

signals_buffer = []
TIME_LIMIT = timedelta(minutes=15)

TRACKED_SIGNALS = [
    "bullish_confirmation", "bullish_confirmation+", "bullish_confirmation_any", "bullish_confirmation_turn+",
    "bearish_confirmation", "bearish_confirmation+", "bearish_confirmation_any", "bearish_confirmation_turn+",
    "bullish_contrarian", "bullish_contrarian+", "bullish_contrarian_any",
    "bearish_contrarian", "bearish_contrarian+", "bearish_contrarian_any",
    "regular_bullish_hyperwave_signal", "oversold_bullish_hyperwave_signal",
    "regular_bearish_hyperwave_signal", "overbought_bearish_hyperwave_signal",
    "strong_bullish_confluence", "strong_bearish_confluence",
    "weak_bullish_confluence", "weak_bearish_confluence",
    "bullish_ob", "bearish_ob",
    "bullish_bb", "bearish_bb",
    "bullish_ibos", "bearish_ibos",
    "bullish_sbos", "bearish_sbos"
]

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}  # بدون HTML
    try:
        response = requests.post(url, json=payload)
        if not response.ok:
            print("خطأ في إرسال الرسالة:", response.text)
    except Exception as e:
        print("خطأ في إرسال الرسالة:", e)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or "signal" not in data or "indicator" not in data:
        return {"status": "error", "msg": "بيانات غير صحيحة"}, 400

    signal_name = data["signal"]
    indicator_name = data["indicator"]
    strength = data.get("strength", 0)
    timestamp = datetime.utcnow()

    if signal_name not in TRACKED_SIGNALS:
        return {"status": "ignored"}

    signals_buffer.append((timestamp, signal_name, indicator_name, strength))

    cutoff = datetime.utcnow() - TIME_LIMIT
    signals_buffer[:] = [s for s in signals_buffer if s[0] > cutoff]

    # رسالة فورية لكل إشارة
    immediate_message = f"🚨 LuxAlgo Alert فوراً:\nالمؤشر: {indicator_name}\nالإشارة: {signal_name}\nالقوة: {strength}\nالوقت: {timestamp.strftime('%H:%M:%S')}"
    send_telegram_alert(immediate_message)

    return {"status": "ok"}

def periodic_report():
    while True:
        time.sleep(900)  # كل 15 دقيقة
        if not signals_buffer:
            continue

        cutoff = datetime.utcnow() - TIME_LIMIT
        signals_buffer[:] = [s for s in signals_buffer if s[0] > cutoff]

        if not signals_buffer:
            continue

        grouped = {}
        for t, signal, indicator, strength in signals_buffer:
            grouped.setdefault(indicator, []).append((signal, strength, t))

        message_lines = ["🚨 LuxAlgo Strongest Signals Report (آخر 15 دقيقة)\n"]
        for indicator, sigs in grouped.items():
            sigs_sorted = sorted(sigs, key=lambda x: x[1], reverse=True)[:5]
            message_lines.append(f"\nالمؤشر: {indicator}")
            for signal, strength, t in sigs_sorted:
                message_lines.append(f" • {signal} (القوة: {strength}) الوقت: {t.strftime('%H:%M:%S')}")

        send_telegram_alert("\n".join(message_lines))

if __name__ == '__main__':
    report_thread = threading.Thread(target=periodic_report, daemon=True)
    report_thread.start()
    app.run(host="0.0.0.0", port=5000)
