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
# نخزن النصوص مع الهاش للتحقق من التكرار
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})

# ===== دالة ارسال رسالة للتليجرام =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ أرسلنا للتليجرام")
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
    signals_store[symbol][direction][signal_hash] = signal_name
    print(f"✅ خزّننا إشارة {direction} لـ {symbol}: {signal_name}")

    # ===== تحقق من عدد الإشارات المختلفة بنفس الاتجاه =====
    if len(signals_store[symbol][direction]) >= 2:
        # جمع الإشارات المختلفة
        signals_list = list(signals_store[symbol][direction].values())
        total_signals = len(signals_list)

        # توقيت سعودي
        sa_time = (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime("%H:%M:%S")

        # نص الرسالة النهائي
        main_direction_text = "صعودي" if direction == "bullish" else "هبوطي"
        emoji = "📈" if direction == "bullish" else "📉"

        message = f"{emoji} {symbol} - تأكيد إشارة {main_direction_text} قوية\n\n"
        message += "📊 الإشارات المختلفة:\n"
        for sig in signals_list:
            message += f"• {sig}\n"
        message += f"\n🔢 عدد الإشارات الكلي: {total_signals}\n"
        message += f"⏰ التوقيت السعودي: {sa_time}\n\n"
        message += f"تأكيد {main_direction_text} قوي من {total_signals} إشارات مختلفة - متوقع حركة {main_direction_text}"

        # ارسال للتليجرام
        send_telegram(message)

        # إعادة ضبط الإشارات بعد الإرسال
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
