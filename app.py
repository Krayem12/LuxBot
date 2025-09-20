from flask import Flask, request, jsonify
import datetime
import requests
import logging
import re

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== إعدادات الإرسال =====
TELEGRAM_TOKEN = None  # عطلنا التليجرام مؤقتاً
TELEGRAM_CHAT_ID = None
EXTERNAL_URL = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"

# القيم الممكنة: both / telegram / external / none
SEND_MODE = "both"

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def get_sa_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info(f"[{get_sa_time()}] ⏸️ إرسال للتليجرام معطل")
        return

def send_external(message: str):
    try:
        resp = requests.post(
            EXTERNAL_URL,
            data=message.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            timeout=10
        )
        if resp.status_code != 200:
            logger.error(f"[{get_sa_time()}] ❌ External send failed {resp.status_code}: {resp.text}")
        else:
            logger.info(f"[{get_sa_time()}] ✅ أُرسل للخادم الخارجي")
    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في إرسال للخادم الخارجي: {e}")

def send_message(message: str):
    if SEND_MODE == "telegram":
        send_telegram(message)
    elif SEND_MODE == "external":
        send_external(message)
    elif SEND_MODE == "both":
        send_telegram(message)
        send_external(message)
    else:
        logger.info(f"[{get_sa_time()}] ⏸️ جميع الإرسالات معطلة (SEND_MODE={SEND_MODE})")

# ===== معالجة الرمز =====
SYMBOL_PATTERN = re.compile(r"^(?P<head>.*?)(?:\s*-\s*)(?P<sym>[A-Za-z0-9_:+.\-]+)\s*$")

def apply_symbol(raw_message: str, symbol: str | None) -> str:
    if not symbol:
        return raw_message

    m = SYMBOL_PATTERN.match(raw_message)
    if m:
        head = m.group("head").rstrip()
        return f"{head} - {symbol}"
    else:
        return f"{raw_message.strip()} - {symbol}"

# ===== Webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # الرمز من Query
        symbol_from_query = request.args.get("symbol", "").strip() or None

        # الرسالة + الرمز من JSON
        data = request.get_json(silent=True)
        raw_message = None
        symbol_from_json = None

        if data and isinstance(data, dict):
            if "message" in data and isinstance(data["message"], str):
                raw_message = data["message"].strip()
            if "symbol" in data and isinstance(data["symbol"], str):
                symbol_from_json = data["symbol"].strip()

            if not raw_message:
                for v in data.values():
                    if isinstance(v, str) and v.strip():
                        raw_message = v.strip()
                        break

        if not raw_message:
            raw_message = request.data.decode("utf-8").strip()

        if not raw_message:
            return jsonify({"status": "خطأ", "reason": "لم يتم العثور على رسالة"}), 400

        # أولوية الرمز: JSON > Query
        symbol_to_apply = symbol_from_json or symbol_from_query or None
        msg_with_symbol = apply_symbol(raw_message, symbol_to_apply)

        sa_time = get_sa_time()
        logger.info(f"[{sa_time}] 🌐 طلب وارد: {raw_message} | بعد التعديل: {msg_with_symbol}")

        final_message = f"{msg_with_symbol}\n⏰ {sa_time}"
        send_message(final_message)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في المعالجة: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
