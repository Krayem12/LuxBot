from flask import Flask, request, jsonify
import datetime
import requests
import logging
import os  # لإدارة متغيرات البيئة

app = Flask(__name__)

# ===== إعداد التوقيت السعودي =====
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# ===== بيانات التليجرام (من Environment Variables) =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ===== رابط الخادم الخارجي =====
EXTERNAL_URL = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"

# ===== متغير تحكم (إرسال أو تعطيل) =====
# القيم الممكنة: "both" / "telegram" / "external" / "none"
SEND_MODE = os.getenv("SEND_MODE", "none").lower()

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ===== دالة ترجع الوقت السعودي =====
def get_sa_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

# ===== إرسال رسالة للتليجرام =====
def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"[{get_sa_time()}] ⚠️ لم يتم ضبط بيانات التليجرام")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"[{get_sa_time()}] ❌ Telegram send failed {resp.status_code}: {resp.text}")
        else:
            logger.info(f"[{get_sa_time()}] ✅ أُرسل للتليجرام")
    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في إرسال التليجرام: {e}")

# ===== إرسال للخادم الخارجي =====
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

# ===== دالة إرسال حسب متغير SEND_MODE =====
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

# ===== Webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        raw_message = None

        if data:
            if "message" in data:
                raw_message = data["message"].strip()
            else:
                for v in data.values():
                    if isinstance(v, str) and v.strip():
                        raw_message = v.strip()
                        break

        if not raw_message:
            raw_message = request.data.decode("utf-8").strip()

        if not raw_message:
            return jsonify({"status": "خطأ", "reason": "لم يتم العثور على رسالة"}), 400

        sa_time = get_sa_time()
        logger.info(f"[{sa_time}] 🌐 طلب وارد: {raw_message}")

        final_message = f"{raw_message}\n⏰ {sa_time}"

        send_message(final_message)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"[{get_sa_time()}] ❌ خطأ في المعالجة: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
