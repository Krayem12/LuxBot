from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict

app = Flask(__name__)

# 🔹 بيانات التليجرام لمتعدد المستلمين
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9c"
CHAT_IDS = [
    "624881400",          # Chat ID الأول
    "-1001234567890",     # Chat ID الثاني (لمجموعة)
    "-1009876543210"      # Chat ID الثالث (لقناة)
]

# 🔹 إرسال رسالة لجميع الدردشات
def send_telegram_to_all(message):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"  # لدعم التنسيق
        }
        try:
            response = requests.post(url, json=payload)
            print(f"تم الإرسال إلى {chat_id}: {response.status_code}")
        except Exception as e:
            print(f"خطأ أثناء الإرسال إلى {chat_id}: {e}")

# 🔹 تحميل قائمة الأسهم من ملف
def load_stocks():
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        print("⚠️  ملف stocks.txt غير موجود. سيتم استخدام قائمة افتراضية.")
        stocks = ["BTCUSDT", "ETHUSDT"]  # قائمة افتراضية
    return stocks

# قائمة الأسهم
STOCK_LIST = load_stocks()

# 🔹 ذاكرة مؤقتة لتخزين الإشارات لكل سهم
signal_memory = defaultdict(lambda: {
    "bullish": [],
    "bearish": []
})

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
    for symbol in STOCK_LIST:
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts) for sig, ts in signal_memory[symbol][direction] 
                if ts > cutoff
            ]

# ✅ تحويل النص الخام إلى صياغة مرتبة
def format_signal(signal_text, direction):
    if "upward" in signal_text.lower():
        return f"Hyper Wave oscillator upward signal 🚀"
    elif "downward" in signal_text.lower():
        return f"Hyper Wave oscillator downward signal 📉"
    else:
        symbol = "🚀" if direction == "bullish" else "📉"
        return f"{signal_text} {symbol}"

# ✅ استخراج اسم السهم من الرسالة
def extract_symbol(message):
    message_upper = message.upper()
    for symbol in STOCK_LIST:
        if symbol in message_upper:
            return symbol
    return "UNKNOWN"  # إذا لم يتم العثور على أي سهم معروف

# ✅ معالجة التنبيهات مع شرط اجتماع إشارتين على الأقل
def process_alerts(alerts):
    now = datetime.utcnow()

    for alert in alerts:
        signal = alert.get("signal", "").strip()
        direction = alert.get("direction", "bullish").strip()
        indicator = alert.get("indicator", "Raw Text").strip()
        
        # استخراج السهم من الرسالة
        symbol = extract_symbol(signal)
        if symbol == "UNKNOWN":
            continue  # تخطي إذا لم يتعرف على السهم

        # صياغة الإشارة
        formatted_signal = format_signal(signal, direction)

        # مفتاح فريد يجمع formatted_signal + indicator + direction
        unique_key = f"{formatted_signal}_{indicator}_{direction}"

        # تخزين الإشارة للسم المحدد
        if unique_key not in [s for s, _ in signal_memory[symbol][direction]]:
            signal_memory[symbol][direction].append((unique_key, now))

    # تنظيف الإشارات القديمة
    cleanup_signals()

    # التحقق من إشارات كل سهم
    for symbol in STOCK_LIST:
        # تحقق من إشارات الصعود
        if len(signal_memory[symbol]["bullish"]) >= 2:
            signals = [s.split("_")[0] for s, _ in signal_memory[symbol]["bullish"]]
            telegram_message = f"{symbol} CALL 🚀 ({len(signals)} Signals in 15m)\n" + "\n".join(signals)
            send_post_request(telegram_message, " + ".join(signals))
            send_telegram_to_all(telegram_message)  # الإرسال للجميع

        # تحقق من إشارات الهبوط
        if len(signal_memory[symbol]["bearish"]) >= 2:
            signals = [s.split("_")[0] for s, _ in signal_memory[symbol]["bearish"]]
            telegram_message = f"{symbol} PUT 📉 ({len(signals)} Signals in 15m)\n" + "\n".join(signals)
            send_post_request(telegram_message, " + ".join(signals))
            send_telegram_to_all(telegram_message)  # الإرسال للجميع

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []

        if request.is_json:
            data = request.get_json(force=True)
            print("Received JSON webhook:", data)
            alerts = data.get("alerts", [])
        else:
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

# 🔹 تشغيل التطبيق
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Monitoring stocks: {', '.join(STOCK_LIST)}")
    print(f"🟢 Sending to {len(CHAT_IDS)} chat rooms")
    app.run(host="0.0.0.0", port=port)
