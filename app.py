from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import hashlib
from difflib import SequenceMatcher

app = Flask(__name__)

# TIMEZONE_OFFSET = 3  # +3 hours for Saudi time
TIMEZONE_OFFSET = 3

# REQUIRED_SIGNALS = 2
REQUIRED_SIGNALS = 2

# TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# DUPLICATE_TIMEFRAME = 300  # 300 seconds = 5 minutes
DUPLICATE_TIMEFRAME = 300

# List of known indicators and filters
KNOWN_INDICATORS = [
    "Internal High", "Internal Low", "Swing High", "Swing Low",
    "Premium", "Equilibrium Average", "Discount", "Bullish I-CHoCH",
    "Bearish I-CHoCH", "Bullish I-BOS", "Bearish I-BOS", "Highest OB Top",
    "Lowest OB Bottom", "Imbalance Top", "Imbalance Bottom", "Imbalance Average",
    "Previous Day High", "Previous Day Low", "Previous Week High",
    "Previous Week Low", "Previous Month High", "Previous Month Low",
    "Discount Zone", "HGH5 & LOWS MTF", "Daily", "Monday's", "Weekly",
    "Monthly"
]

def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

def remove_html_tags(text):
    """Remove HTML tags from text"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def create_signal_fingerprint(signal_text, symbol, signal_type):
    """Create unique fingerprint for signal based on content and type"""
    content = f"{symbol}_{signal_type}_{signal_text.lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()

def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=5)
        print(f"Sent to {CHAT_ID}: {response.status_code}")
        
        if response.status_code == 200:
            print("Message sent successfully to Telegram!")
            return True
        else:
            print(f"Failed to send message: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("Telegram timeout: Timeout exceeded (5 seconds)")
        return False
    except requests.exceptions.ConnectionError:
        print("Failed to connect to Telegram")
        return False
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def load_stocks():
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        print("stocks.txt file not found. Using default list.")
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]
    return stocks

STOCK_LIST = load_stocks()

signal_memory = defaultdict(lambda: {
    "bullish": [],
    "bearish": [],
    "last_signals": {}
})

def send_post_request(message, indicators, signal_type=None):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    
    clean_message = remove_html_tags(message)
    
    payload = {
        "text": clean_message,
        "extras": {
            "indicators": indicators,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "tradingview-bot",
            "original_signal_type": signal_type
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"External request sent: {response.status_code}")
        
        if response.status_code == 200:
            print("Data sent successfully to external server!")
            return True
        else:
            print(f"External send failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("External timeout: Timeout exceeded")
        return False
    except requests.exceptions.ConnectionError:
        print("Failed to connect to external server")
        return False
    except Exception as e:
        print(f"External error: {e}")
        return False

def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts, fp) for sig, ts, fp in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
        
        current_time = datetime.utcnow()
        signal_memory[symbol]["last_signals"] = {
            fp: ts for fp, ts in signal_memory[symbol]["last_signals"].items()
            if (current_time - ts).total_seconds() < DUPLICATE_TIMEFRAME
        }
        
        if (not signal_memory[symbol]['bullish'] and 
            not signal_memory[symbol]['bearish'] and 
            not signal_memory[symbol]['last_signals']):
            del signal_memory[symbol]

def is_duplicate_signal(symbol, signal_text, signal_fingerprint):
    """Check if signal is duplicate within the specified timeframe"""
    if symbol in signal_memory:
        last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
        if last_seen:
            time_diff = (datetime.utcnow() - last_seen).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"Duplicate signal for {symbol} ignored (fingerprint, diff: {time_diff:.1f}s)")
                return True
        
        current_signal = signal_text.strip()
        current_clean = re.sub(r'[^\w\s]', '', current_signal.lower())
        current_clean = re.sub(r'\s+', ' ', current_clean).strip()
        
        current_without_symbol = re.sub(r'\b' + re.escape(symbol) + r'\b', '', current_clean).strip()
        
        for existing_signal, ts, fp in signal_memory[symbol]["bullish"] + signal_memory[symbol]["bearish"]:
            existing_clean = re.sub(r'[^\w\s]', '', existing_signal.split('_')[0].lower())
            existing_clean = re.sub(r'\s+', ' ', existing_clean).strip()
            
            existing_without_symbol = re.sub(r'\b' + re.escape(symbol) + r'\b', '', existing_clean).strip()
            
            if current_without_symbol == existing_without_symbol and current_without_symbol != "":
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"Duplicate signal for {symbol} ignored (same content without symbol, diff: {time_diff:.1f}s)")
                    print(f"   Current: {current_signal}")
                    print(f"   Previous: {existing_signal.split('_')[0]}")
                    return True
            
            if current_clean == existing_clean:
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"Duplicate signal for {symbol} ignored (same full content, diff: {time_diff:.1f}s)")
                    return True
            
            current_words = set(current_clean.split())
            existing_words = set(existing_clean.split())
            
            common_words = current_words.intersection(existing_words)
            similarity_ratio = len(common_words) / max(len(current_words), len(existing_words))
            
            if similarity_ratio >= 0.8 and len(common_words) >= 2:
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"Similar signal for {symbol} ignored (similarity {similarity_ratio:.0%}, diff: {time_diff:.1f}s)")
                    print(f"   Common words: {common_words}")
                    return True
    
    return False

def extract_symbol(message):
    cleaned_message = re.sub(r'[^\x00-\x7F]+', ' ', message).upper()
    
    sorted_stocks = sorted(STOCK_LIST, key=len, reverse=True)
    for symbol in sorted_stocks:
        if symbol in cleaned_message:
            return symbol
    
    if "SPX" in cleaned_message or "500" in cleaned_message:
        return "SPX500"
    elif "BTC" in cleaned_message:
        return "BTCUSDT" 
    elif "ETH" in cleaned_message:
        return "ETHUSDT"
    elif "NASDAQ" in cleaned_message or "100" in cleaned_message:
        return "NASDAQ100"
    elif "DOW" in cleaned_message or "US30" in cleaned_message or "30" in cleaned_message:
        return "US30"
    
    return "UNKNOWN"

def extract_signal_name(raw_signal):
    signal_lower = raw_signal.lower()
    
    if "bullish" in signal_lower and "bos" in signal_lower:
        return "BOS Breakout"
    elif "bearish" in signal_lower and "bos" in signal_lower:
        return "BOS Breakdown"
    elif "bullish" in signal_lower and "choch" in signal_lower:
        return "CHOCH Change"
    elif "bearish" in signal_lower and "choch" in signal_lower:
        return "CHOCH Change"
    elif "bullish" in signal_lower and "confluence" in signal_lower:
        return "Strong Confluence"
    elif "bearish" in signal_lower and "confluence" in signal_lower:
        return "Strong Confluence"
    elif "bullish" in signal_lower and "confirmation" in signal_lower:
        return "Bullish Confirmation"
    elif "bearish" in signal_lower and "confirmation" in signal_lower:
        return "Bearish Confirmation"
    elif "bullish" in signal_lower:
        return "Bullish Signal"
    elif "bearish" in signal_lower:
        return "Bearish Signal"
    elif "overbought" in signal_lower and "downward" in signal_lower:
        return "Overbought Reversal"
    elif "oversold" in signal_lower and "upward" in signal_lower:
        return "Oversold Reversal"
    else:
        return "Trading Signal"

def extract_signal_type(signal_text):
    signal_lower = signal_text.lower()
    
    if "confluence" in signal_lower:
        return "confluence"
    elif "bos" in signal_lower:
        return "bos"
    elif "choch" in signal_lower:
        return "choch"
    elif "confirmation" in signal_lower:
        return "confirmation"
    elif "overbought" in signal_lower:
        return "overbought"
    elif "oversold" in signal_lower:
        return "oversold"
    elif "bullish" in signal_lower:
        return "bullish"
    elif "bearish" in signal_lower:
        return "bearish"
    else:
        return "unknown"

def clean_signal_name(signal_text):
    cleaned = re.sub(r'_.*$', '', signal_text)
    cleaned = re.sub(r'\s+\d+$', '', cleaned)
    return cleaned.strip()

def process_alerts(alerts):
    now = datetime.utcnow()
    print(f"Processing {len(alerts)} alerts")

    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            direction = alert.get("direction", "bullish").strip().lower()
            ticker = alert.get("ticker", "")
        else:
            signal = str(alert).strip()
            direction = "bullish"
            ticker = ""

        signal = re.sub(r'[^\x00-\x7F]+', ' ', signal).strip()
        
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            print(f"Could not extract symbol from: {signal}")
            continue

        signal_lower = signal.lower()
        if ("bearish" in signal_lower or "down" in signal_lower or 
            "put" in signal_lower or "short" in signal_lower or
            "downward" in signal_lower or "overbought" in signal_lower):
            direction = "bearish"
        else:
            direction = "bullish"

        signal_type = extract_signal_type(signal)
        signal_fingerprint = create_signal_fingerprint(signal_type, ticker, direction)
        
        if is_duplicate_signal(ticker, signal, signal_fingerprint):
            continue

        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": [], "last_signals": {}}

        signal_memory[ticker]["last_signals"][signal_fingerprint] = now
        
        unique_key = f"{signal}_{now.timestamp()}"
        signal_memory[ticker][direction].append((unique_key, now, signal_fingerprint))
        print(f"Stored {direction} signal for {ticker}: {signal}")

    cleanup_signals()

    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:
                signal_count = len(signals[direction])
                
                saudi_time = get_saudi_time()
                
                signals_list = "\n".join([f"{i+1}. {clean_signal_name(sig[0])}" for i, sig in enumerate(signals[direction])])
                
                if direction == "bullish":
                    message = f"""🚀 <b>{symbol} - Bullish Signal Confirmation</b>

📊 <b>Received Signals:</b>
{signals_list}

🔢 <b>Signals Count:</b> {signal_count}
⏰ <b>Saudi Time:</b> {saudi_time}

⚠️ <i>Warning: This is not financial advice, manage your own risks</i>"""
                    signal_type = "BULLISH_CONFIRMATION"
                else:
                    message = f"""📉 <b>{symbol} - Bearish Signal Confirmation</b>

📊 <b>Received Signals:</b>
{signals_list}

🔢 <b>Signals Count:</b> {signal_count}
⏰ <b>Saudi Time:</b> {saudi_time}

⚠️ <i>Warning: This is not financial advice, manage your own risks</i>"""
                    signal_type = "BEARISH_CONFIRMATION"
                
                telegram_success = send_telegram_to_all(message)
                
                external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)
                
                if telegram_success and external_success:
                    print(f"Alert sent successfully for {symbol}")
                elif telegram_success and not external_success:
                    print(f"Telegram sent but external server failed for {symbol}")
                else:
                    print(f"Complete send failure for {symbol}")
                
                signal_memory[symbol][direction] = []
                print(f"Sent alert for {symbol} ({direction})")

@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\nIncoming request: {request.method} {request.path}")
        print(f"Content-Type: {request.content_type}")
        print(f"Headers: { {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']} }")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        raw_data = None

        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"Received raw webhook data: '{raw_data}'")
            
            raw_data = re.sub(r'[^\x00-\x7F]+', ' ', raw_data).strip()
            
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    print(f"Parsed JSON data: {data}")
                    
                    if isinstance(data, dict):
                        if "alerts" in data:
                            alerts = data["alerts"]
                        else:
                            alerts = [data]
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                    
            elif raw_data:
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
                
        except Exception as parse_error:
            print(f"Raw data parse error: {parse_error}")

        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                print(f"Received JSON webhook: {data}")
                alerts = data.get("alerts", [])
                if not alerts and data:
                    alerts = [data]
            except Exception as json_error:
                print(f"JSON parse error: {json_error}")

        if not alerts and raw_data:
            alerts = [{"signal": raw_data, "raw_data": raw_data}]

        print(f"Processing {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({
                "status": "alert_processed", 
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        else:
            print("No valid alerts found in webhook")
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver is active",
        "monitored_stocks": STOCK_LIST,
        "active_signals": {k: {ky: len(v) if ky in ["bullish", "bearish"] else v for ky, v in val.items()} for k, val in signal_memory.items()},
        "duplicate_timeframe": f"{DUPLICATE_TIMEFRAME} seconds",
        "required_signals": REQUIRED_SIGNALS,
        "timestamp": datetime.utcnow().isoformat()
    })

def test_services():
    print("Testing services...")
    
    telegram_result = send_telegram_to_all("Test message from bot - System is working!")
    print(f"Telegram test result: {telegram_result}")
    
    external_result = send_post_request("Test message", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    print(f"External API test result: {external_result}")
    
    return telegram_result and external_result

if __name__ == "__main__":
    test_services()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"Server started on port {port}")
    print(f"Telegram receiver: {CHAT_ID}")
    print(f"Monitoring stocks: {', '.join(STOCK_LIST)}")
    print(f"Saudi Timezone: UTC+{TIMEZONE_OFFSET}")
    print(f"Required signals: {REQUIRED_SIGNALS}")
    print(f"Duplicate prevention: {DUPLICATE_TIMEFRAME} seconds")
    print(f"External API: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    print("Waiting for TradingView webhooks...")
    app.run(host="0.0.0.0", port=port)

application = app
