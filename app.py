from flask import Flask, request, jsonify
import datetime
import requests
import hashlib
from collections import defaultdict
import re

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== إعدادات التليجرام =====
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ===== إعداد تخزين الإشارات =====
signals_store = defaultdict(lambda: {"bullish": {}, "bearish": {}})
general_trend = {}  # الاتجاه العام لكل رمز

# ===== تحميل قائمة الأسهم المسموح بها من ملف =====
def load_allowed_stocks(file_path="stocks.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip().upper() for line in f if line.strip())
    except FileNotFoundError:
        print(f"⚠️ ملف الأسهم {file_path} غير موجود!")
        return set()

ALLOWED_STOCKS = load_allowed_stocks()

# ===== دالة ارسال POST خارجي بنفس الرسالة =====
def send_post_request(message: str):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    payload = {"text": message}  # نفس الرسالة بالضبط
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ أرسلنا POST خارجي")
        else:
            print(f"⚠️ فشل ارسال POST خارجي ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء ارسال POST خارجي: {e}")

# ===== دالة ارسال رسالة للتليجرام + POST خارجي =====
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ أرسلنا للتليجرام")
        else:
            print(f"⚠️ فشل ارسال التليجرام ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء ارسال التليجرام: {e}")

    # 🔹 إرسال نفس الرسالة للـ endpoint الخارجي
    send_post_request(message)

# ===== دالة إنشاء هاش فريد للإشارة =====
def hash_signal(signal_text: str):
    return hashlib.sha256(signal_text.encode()).hexdigest()

# ===== دالة استخراج الرمز مع التحقق من الأسهم المسموح بها =====
def extract_symbol(text: str) -> str:
    match = re.search(r"\b([A-Z]{2,10}\d{0,3})(USDT)?\b", text)
    if match:
        symbol = match.group(0).upper()
        if symbol in ALLOWED_STOCKS:
            return symbol
    return "UNKNOWN"

# ===== دالة معالجة الإشارة =====
def process_signal(signal_text: str):
    signal_text = signal_text.replace("\n", " ").strip()
    symbol = extract_symbol(signal_text)

    sa_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

    if symbol == "UNKNOWN":
        print(f"⏭️ تجاهل إشارة لأن الرمز غير موجود في ملف الأسهم ⏰ {sa_time}: {signal_text}")
        return

    # ===== تحديد الاتجاه العام Trend Catcher =====
    trend_catcher = None
    if "Trend Catcher Bullish" in signal_text or "Trend Tracer Bullish" in signal_text:
        trend_catcher = "bullish"
    elif "Trend Catcher Bearish" in signal_text or "Trend Tracer Bearish" in signal_text:
        trend_catcher = "bearish"

    if trend_catcher:  # إذا كانت إشارة اتجاه
        prev_trend = general_trend.get(symbol)
        if prev_trend != trend_catcher:
            general_trend[symbol] = trend_catcher
            # مسح إشارات الدخول القديمة عند تغير الاتجاه
            signals_store[symbol] = {"bullish": {}, "bearish": {}}

            emoji = "🟢📈" if trend_catcher == "bullish" else "🔴📉"
            trend_text = "صاعد (Bullish)" if trend_catcher == "bullish" else "هابط (Bearish)"
            message = (
                f"📢 تحديث الاتجاه العام\n"
                f"{emoji} الرمز: {symbol}\n"
                f"📊 الاتجاه الحالي: {trend_text}\n"
                f"⏰ الوقت: {sa_time}\n"
                f"⚠️ أي إشارات دخول سابقة تم مسحها تلقائيًا"
            )
            send_telegram(message)
            print(f"⚠️ {symbol}: تغير الاتجاه العام {prev_trend} → {trend_catcher}")
        return  # لا نخزن إشارة الاتجاه كإشارة دخول

    # ===== إذا لم يصل اتجاه بعد، لا نخزن إشارات الدخول =====
    if symbol not in general_trend:
        print(f"⏭️ تجاهل إشارة دخول {signal_text} لـ {symbol} لأنه لم يصل بعد اتجاه عام")
        return

    # ===== تحديد اتجاه الإشارة العادية =====
    direction = None
    if "bullish" in signal_text.lower():
        direction = "bullish"
    elif "bearish" in signal_text.lower():
        direction = "bearish"

    # دعم Hyper Wave
    if "Overbought Hyper Wave" in signal_text:
        direction = "bearish"
    elif "Oversold Hyper Wave" in signal_text:
        direction = "bullish"
    elif "Hyper Wave oscillator upward signal" in signal_text:
        direction = "bullish"
    elif "Hyper Wave oscillator downward signal" in signal_text:
        direction = "bearish"

    if not direction:
        print(f"ℹ️ إشارة غير مصنفة ⏰ {sa_time}: {signal_text}")
        return

    # ===== التحقق من توافق الاتجاه مع Trend Catcher =====
    if direction != general_trend[symbol]:
        print(f"⏭️ تجاهل إشارة {signal_text} لـ {symbol} لأنها لا تتوافق مع الاتجاه العام {general_trend[symbol]} ⏰ {sa_time}")
        return

    # ===== هاش فريد للإشارة =====
    signal_hash = hash_signal(signal_text)

    # ===== تحقق من التكرار =====
    if signal_hash in signals_store[symbol][direction]:
        print(f"⏭️ إشارة مكررة تجاهل ⏰ {sa_time}: {signal_text} لـ {symbol}")
        return

    # ===== إضافة الإشارة لمخزن الإشارات =====
    signals_store[symbol][direction][signal_hash] = signal_text
    print(f"✅ خزّننا إشارة {direction} لـ {symbol} ⏰ {sa_time}: {signal_text}")

    # ===== تحقق من عدد الإشارات المختلفة بنفس الاتجاه =====
    if len(signals_store[symbol][direction]) >= 2:  # عدد إشارات الدخول المطلوبة = 2
        signals_list = list(signals_store[symbol][direction].values())
        total_signals = len(signals_list)
        color_emoji = "🔵" if direction == "bullish" else "🔴"
        arrow_emoji = "📈" if direction == "bullish" else "📉"

        message = f"{arrow_emoji} {symbol} - {color_emoji} تأكيد إشارة قوية {direction}\n\n"
        message += "📊 الإشارات المختلفة:\n"
        for sig in signals_list:
            message += f"• {sig}\n"
        message += f"\n🔢 عدد الإشارات الكلي: {total_signals}\n"
        message += f"⏰ {sa_time}\n\n"
        message += f"{color_emoji} متوقع حركة {direction} من {total_signals} إشارات مختلفة"

        send_telegram(message)
        # مسح الإشارات بعد الإرسال
        signals_store[symbol][direction] = {}

# ===== مسار webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    signal_text = request.get_data(as_text=True)
    sa_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"🌐 طلب وارد: POST /webhook")
    print(f"⏰ وقت الاستلام (السعودي): {sa_time}")
    print(f"📨 بيانات webhook ({len(signal_text)} chars): {signal_text}")
    process_signal(signal_text)
    return jsonify({"status": "ok"}), 200

# ===== تشغيل السيرفر =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
