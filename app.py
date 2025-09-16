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
MIN_SIGNALS_TO_CONFIRM = 2  # عدد إشارات الدخول المطلوبة للتأكيد

# ===== تحميل قائمة الأسهم المسموح بها من ملف =====
def load_allowed_stocks(file_path="stocks.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip().upper() for line in f if line.strip())
    except FileNotFoundError:
        print(f"⚠️ ملف الأسهم {file_path} غير موجود!")
        return set()

ALLOWED_STOCKS = load_allowed_stocks()

# ===== دالة ارسال رسالة للتليجرام =====
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

    # 🕒 التوقيت السعودي
    sa_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

    if symbol == "UNKNOWN":
        print(f"⏭️ تجاهل إشارة لأن الرمز غير موجود في ملف الأسهم ⏰ {sa_time}: {signal_text}")
        return

    # ===== تحديد الاتجاه العام Trend Catcher =====
    if "Trend Catcher Bullish" in signal_text:
        trend_catcher = "bullish"
    elif "Trend Catcher Bearish" in signal_text:
        trend_catcher = "bearish"
    else:
        trend_catcher = None

    if trend_catcher:
        prev_trend = general_trend.get(symbol)
        if prev_trend != trend_catcher:
            general_trend[symbol] = trend_catcher
            signals_store[symbol].clear()  # مسح الإشارات القديمة

            emoji = "🟢📈" if trend_catcher == "bullish" else "🔴📉"
            # إشعار تغيير الاتجاه
            message_trend = f"{emoji} {symbol}\n📊 الاتجاه العام تغير من {prev_trend or 'N/A'} → {trend_catcher}\n⏰ {sa_time}"
            send_telegram(message_trend)

            # إشعار مسح الإشارات السابقة
            message_clear = f"🧹 {symbol} - تم مسح إشارات الدخول السابقة وإعادة التصفير بعد تغير الاتجاه.\n⏰ {sa_time}"
            send_telegram(message_clear)
        return  # الاتجاه العام فقط، ليس إشارة دخول

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
    if symbol in general_trend and direction != general_trend[symbol]:
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
    if len(signals_store[symbol][direction]) >= MIN_SIGNALS_TO_CONFIRM:
        signals_list = list(signals_store[symbol][direction].values())
        total_signals = len(signals_list)
        color_emoji = "🔵" if direction == "bullish" else "🔴"
        arrow_emoji = "📈" if direction == "bullish" else "📉"

        # تضمين الاتجاه العام الحالي في الرسالة
        current_trend = general_trend.get(symbol, "N/A")

        message = f"{arrow_emoji} {symbol} - {color_emoji} تأكيد إشارة قوية {direction}\n"
        message += f"📊 الاتجاه العام الحالي: {current_trend}\n\n"
        message += "📌 الإشارات المجمعة:\n"
        for sig in signals_list:
            message += f"• {sig}\n"
        message += f"\n🔢 عدد الإشارات: {total_signals}\n"
        message += f"⏰ {sa_time}\n"
        message += f"{color_emoji} متوقع حركة {direction} بناءً على {total_signals} إشارات مختلفة"

        send_telegram(message)
        signals_store[symbol][direction].clear()

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
