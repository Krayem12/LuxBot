from flask import Flask, request, jsonify
import datetime
import logging
import re

app = Flask(__name__)

# ===== Saudi time offset =====
TIMEZONE_OFFSET = 3  # +3 hours for Saudi time

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ===== Store last used symbol =====
last_symbol = None

def get_sa_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE_OFFSET)).strftime("%Y-%m-%d %H:%M:%S")

# ===== Symbol processing =====
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
    global last_symbol
    try:
        # Symbol from query string
        symbol_from_query = request.args.get("symbol", "").strip() or None

        # Message + symbol from JSON
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
            return jsonify({"status": "error", "reason": "No message found"}), 400

        # Priority: JSON > Query > last stored
        if symbol_from_json:
            last_symbol = symbol_from_json
        elif symbol_from_query:
            last_symbol = symbol_from_query

        msg_with_symbol = apply_symbol(raw_message, last_symbol)

        sa_time = get_sa_time()
        final_message = f"{msg_with_symbol}\n⏰ {sa_time}"

        # Disabled sending: only log
        logger.info(f"[{sa_time}] Received message (not sent): {final_message}")

        return jsonify({"status": "success", "message": final_message, "current_symbol": last_symbol}), 200

    except Exception as e:
        logger.error(f"[{get_sa_time()}] Error processing request: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
