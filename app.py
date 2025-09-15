from flask import Flask, request, jsonify
import datetime
import requests
import re

app = Flask(__name__)

# 🔹 ملف تخزين السجلات
LOG_FILE = "signals.log"

# 🔹 إعداد التليجرام
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# 🔹 متغير لتخزين الاتجاه الحالي لكل رمز
current_trends = {}

def log_signal(text: str):
    """تخزين الإشارة في ملف مع التوقيت"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {text}\n")

def send_telegram_message(message: str):
    """إرسال رسالة للتليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload)
    except Exception as e:
        print("❌ Telegram error:", e)

def extract_symbol(text: str) -> str:
    """استخراج الرمز من النص (مثال: BTCUSDT)"""
    match = re.search(r"\b[A-Z]{3,10}USDT\b", text)
    return match.group(0) if match else "UNKNOWN"

@app.route('/webhook', methods=['POST'])
def webhook():
    global current_trends
    try:
        # 🔹 جلب البيانات الخام
        raw_data = request.get_data(as_text=True)
        print("📩 Raw data received:", raw_data)

        signal_text = ""

        # 🔹 لو JSON
        if request.is_json:
            payload = request.json
            print("📦 JSON payload:", payload)
            signal_text = (
                payload.get("message")
                or payload.get("alert")
                or payload.get("signal")
                or str(payload)
            )
        else:
            signal_text = raw_data

        # 🔹 استخراج الرمز
        symbol = extract_symbol(signal_text)

        # 🔹 تحديد الاتجاه
        if "Bullish" in signal_text:
            trend = "Bullish"
            print("✅ إشارة اتجاه صاعد 📈:", signal_text)
        elif "Bearish" in signal_text:
            trend = "Bearish"
            print("✅ إشارة اتجاه هابط 📉:", signal_text)
        else:
            trend = None
            print("ℹ️ إشارة غير مصنفة:", signal_text)

        # 🔹 تخزين الإشارة
        log_signal(signal_text)

        # 🔹 إذا الاتجاه اتغير
        if trend:
            prev_trend = current_trends.get(symbol)
            if prev_trend != trend:
                print(f"⚠️ {symbol}: تغير الاتجاه {prev_trend} → {trend}")
                send_telegram_message(f"📊 {symbol}: الاتجاه تغير من {prev_trend or 'N/A'} → {trend}")
                current_trends[symbol] = trend

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
