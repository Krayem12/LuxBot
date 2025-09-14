from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import hashlib
from collections import defaultdict

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== إعدادات التليجرام =====
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ===== إعداد تخزين الإشارات =====
# signals_store: لتخزين جميع الإشارات الفريدة لكل زوج حسب الاتجاه
signals_store = defaultdict(lambda: {"bullish": set(), "bearish": set()})

# ===== دالة ارسال رسالة للتليجرام =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ أرسلنا للتليجرام: {message}")
        else:
            print(f"⚠️ فشل ارسال التليجرام ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء ارسال التليجرام: {e}")

# ===== دالة إنشاء هاش فريد للإشارة =====
def hash_signal(signal_text: str):
    return hashlib.sha256(signal_text.encode()).hexdigest()

# ===== دالة معالجة الإشارة =====
def process_signal(signal_text: str):
    """
    الإشارات المتوقعة من webhook تكون على شكل:
    "Bullish reversal +\nBTCUSDT"
    """
    lines = signal_text.strip().split("\n")
    if len(lines) < 2:
        print("⚠️ الإشارة غير صالحة:", signal_text)
        return

    signal_name = lines[0].strip()
    symbol = lines[1].strip()

    # تحديد الاتجاه
    direction = "bullish" if "bullish" in signal_name.lower() else "bearish"

    # هاش فريد للإشارة
    signal_hash = hash_signal(signal_name)

    # تحقق من التكرار
    if signal_hash in signals_store[symbol][direction]:
        print(f"⏭️ إشارة مكررة تجاهل: {signal_name} لـ {symbol}")
        return

    # إضافة الإشارة لمخزن الإشارات
    signals_store[symbol][direction].add(signal_hash)
    print(f"✅ خزّننا إشارة {direction} لـ {symbol}: {signal_name}")

    # ===== تحقق من عدد الإشارات المختلفة بنفس الاتجاه =====
    if len(signals_store[symbol][direction]) >= 2:
        # جمع الإشارتين المختلفتين بنفس الاتجاه
        combined_signals = "\n".join(
            [s for s_hash in signals_store[symbol][direction] for s in [signal_name]]
        )
        message = f"⚡️ إشارات {direction.upper()} مجمعة لـ {symbol}:\n" + \
                  "\n".join([s for s_hash in signals_store[symbol][direction] for s in [s_hash]])
        
        # ارسال للتليجرام
        send_telegram(message)

        # إعادة ضبط الإشارات بعد الإرسال لتفادي التكرار
        signals_store[symbol][direction].clear()

# ===== مسار webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    signal_text = request.get_data(as_text=True)
    print(f"🌐 طلب وارد: POST /webhook")
    print(f"📨 بيانات webhook ({len(signal_text)} chars): {signal_text}")
    process_signal(signal_text)
    return jsonify({"status": "ok"}), 200

# ===== تشغيل السيرفر =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
