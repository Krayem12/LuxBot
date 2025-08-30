import time
from datetime import datetime, timedelta
from flask import Flask, request
import requests

app = Flask(__name__)

# ✅ بيانات التوكن والـ ID للتليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# مدة الاحتفاظ بالإشارات مؤقتاً (15 دقيقة)
TIME_LIMIT = timedelta(minutes=15)
signals_buffer = []

# جميع الإشارات المهمة من آخر تحديث LuxAlgo
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
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("خطأ في إرسال الرسالة:", e)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or "signal" not in data or "indicator" not in data:
        return {"status": "error", "msg": "بيانات غير صحيحة"}, 400

    signal_name = data["signal"]
    indicator_name = data["indicator"]
    strength = data.get("strength", 0)  # في حال توفر قوة الإشارة
    timestamp = datetime.utcnow()

    # تجاهل الإشارات غير المتابعة
    if signal_name not in TRACKED_SIGNALS:
        return {"status": "ignored"}

    # حفظ الإشارة مؤقتاً
    signals_buffer.append((timestamp, signal_name, indicator_name, strength))

    # تنظيف الإشارات القديمة
    cutoff = datetime.utcnow() - TIME_LIMIT
    signals_buffer[:] = [s for s in signals_buffer if s[0] > cutoff]

    # إعداد رسالة التليجرام فورياً عند أي إشارة
    message = f"🚨 LuxAlgo Alert:\n📊 المؤشر: {indicator_name}\n⚡ الإشارة: {signal_name}\n💪 القوة: {strength}"
    send_telegram_alert(message)

    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
