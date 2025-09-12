from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re

app = Flask(__name__)

# Saudi time settings (UTC+3)
TIMEZONE_OFFSET = 3  # +3 hours for Saudi time

# Number of required signals (changed from 1 to 2)
REQUIRED_SIGNALS = 3

# Telegram credentials
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# Get Saudi time
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# Remove HTML tags from text
def remove_html_tags(text):
    """Remove HTML tags from text"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# Send message to a single user
def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # Short timeout to avoid server freezing
        response = requests.post(url, json=payload, timeout=5)
        print(f"✅ Sent to {CHAT_ID}: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 Message sent successfully to Telegram!")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Telegram timeout: Timeout exceeded (5 seconds)")
        return False
    except requests.exceptions.ConnectionError:
        print("🔌 Telegram connection failed")
        return False
    except Exception as e:
        print(f"❌ Telegram sending error: {e}")
        return False

# Load stock list from file
def load_stocks():
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        print("⚠️  stocks.txt file not found. Using default list.")
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]  # Default list
    return stocks

# Stock list
STOCK_LIST = load_stocks()

# Temporary memory to store signals for each stock
signal_memory = defaultdict(lambda: {
    "bullish": [],
    "bearish": []
})

# Send external POST (modified to send message without HTML formatting)
def send_post_request(message, indicators, signal_type=None):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    
    # Remove HTML formatting from message
    clean_message = remove_html_tags(message)
    
    # Send message without HTML formatting to external server
    payload = {
        "text": clean_message,  # Message without HTML formatting
        "extras": {
            "indicators": indicators,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "tradingview-bot",
            "original_signal_type": signal_type
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"✅ External request sent: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 Data sent successfully to external server!")
            return True
        else:
            print(f"❌ External sending failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ External sending timeout: Timeout exceeded")
        return False
    except requests.exceptions.ConnectionError:
        print("🔌 Connection to external server failed")
        return False
    except Exception as e:
        print(f"❌ External sending error: {e}")
        return False

# Clean up old signals (older than 15 minutes)
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts) for sig, ts in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
        # Clean memory from empty stocks
        if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
            del signal_memory[symbol]

# Extract stock name from message (modified)
def extract_symbol(message):
    message_upper = message.upper()
    
    # Search for any stock symbol in the list (in reverse order by length to avoid partial matches)
    sorted_stocks = sorted(STOCK_LIST, key=len, reverse=True)
    for symbol in sorted_stocks:
        if symbol in message_upper:
            return symbol
    
    # If not found, search for known patterns
    if "SPX" in message_upper or "500" in message_upper:
        return "SPX500"
    elif "BTC" in message_upper:
        return "BTCUSDT" 
    elif "ETH" in message_upper:
        return "ETHUSDT"
    elif "NASDAQ" in message_upper or "100" in message_upper:
        return "NASDAQ100"
    elif "DOW" in message_upper or "US30" in message_upper or "30" in message_upper:
        return "US30"
    
    return "SPX500"  # Default

# Extract clean signal name without timestamps/numbers
def extract_clean_signal_name(raw_signal):
    """Remove timestamps and numbers from signal name"""
    # Remove timestamp patterns like _1757666714.691848
    clean_signal = re.sub(r'_\d+\.\d+', '', raw_signal)
    # Remove any standalone numbers
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    # Remove extra spaces and trim
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    return clean_signal if clean_signal else raw_signal

# Check if signals are different (unique signal types)
def are_signals_different(signals_list):
    """Check if all signals in the list are different"""
    if len(signals_list) < 2:
        return True
    
    # Extract clean signal names
    clean_signals = [extract_clean_signal_name(sig) for sig, ts in signals_list]
    
    # Check if all signals are different
    return len(set(clean_signals)) == len(clean_signals)

# Process alerts with condition of at least three different signals
def process_alerts(alerts):
    now = datetime.utcnow()
    print(f"🔍 Processing {len(alerts)} alerts")

    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            direction = alert.get("direction", "bullish").strip().lower()
            ticker = alert.get("ticker", "")
        else:
            signal = str(alert).strip()
            direction = "bullish"
            ticker = ""

        # Extract stock if not available
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            print(f"⚠️ Could not extract symbol from: {signal}")
            continue

        # Automatically determine direction from signal
        signal_lower = signal.lower()
        if "bearish" in signal_lower or "down" in signal_lower or "put" in signal_lower or "short" in signal_lower:
            direction = "bearish"
        else:
            direction = "bullish"

        # Store signal
        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": []}

        unique_key = f"{signal}_{now.timestamp()}"
        signal_memory[ticker][direction].append((unique_key, now))
        print(f"✅ Stored {direction} signal for {ticker}: {signal}")

    # Clean up old signals (reset counter if no signals within 15 minutes)
    cleanup_signals()

    # Check signals for each stock - at least three different signals
    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:  # At least three signals
                # Check if all signals are different
                if are_signals_different(signals[direction]):
                    signal_count = len(signals[direction])
                    
                    # Get all signal names (clean without timestamps/numbers)
                    all_signals = []
                    for sig, ts in signals[direction]:
                        clean_signal = extract_clean_signal_name(sig)
                        all_signals.append(clean_signal)
                    
                    # Get Saudi time
                    saudi_time = get_saudi_time()
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية قوية</b>

📊 <b>الإشارات المجمعة:</b>
{chr(10).join([f'• {signal}' for signal in all_signals])}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد صعودي قوي من إشارات متعددة - متوقع حركة صعودية</code>"""
                        signal_type = "BULLISH_CONFIRMATION"
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية قوية</b>

📊 <b>الإشارات المجمعة:</b>
{chr(10).join([f'• {signal}' for signal in all_signals])}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد هبوطي قوي من إشارات متعددة - متوقع حركة هبوطية</code>"""
                        signal_type = "BEARISH_CONFIRMATION"
                    
                    # Send to Telegram (with HTML formatting)
                    telegram_success = send_telegram_to_all(message)
                    
                    # Send to external server (without HTML formatting)
                    external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)
                    
                    if telegram_success and external_success:
                        print(f"🎉 Alert sent successfully for {symbol}")
                    elif telegram_success and not external_success:
                        print(f"⚠️ Sent to Telegram but external server failed for {symbol}")
                    else:
                        print(f"❌ Complete sending failed for {symbol}")
                    
                    # Clear signals after sending
                    signal_memory[symbol][direction] = []
                    print(f"📤 Sent alert for {symbol} ({direction}) - Different signals confirmed")
                else:
                    print(f"⏳ Waiting for different signals for {symbol} ({direction}) - Current: {len(signals[direction])} signals")

# Log incoming request information (for debugging)
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\n🌐 Incoming request: {request.method} {request.path}")
        print(f"🌐 Content-Type: {request.content_type}")
        print(f"🌐 Headers: { {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']} }")

# Receive webhook (updated)
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        raw_data = None

        # Log raw data
        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"📨 Received raw webhook data: '{raw_data}'")
            
            # Try to parse JSON
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    print(f"📊 Parsed JSON data: {data}")
                    
                    if isinstance(data, dict):
                        if "alerts" in data:
                            alerts = data["alerts"]
                        else:
                            alerts = [data]  # Process as direct object
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    # Continue processing as plain text
                    
            elif raw_data:
                # Process as direct text message
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
                
        except Exception as parse_error:
            print(f"❌ Raw data parse error: {parse_error}")

        # Traditional JSON request method
        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                print(f"📊 Received JSON webhook: {data}")
                alerts = data.get("alerts", [])
                if not alerts and data:
                    alerts = [data]
            except Exception as json_error:
                print(f"❌ JSON parse error: {json_error}")

        # If no alerts, use raw data
        if not alerts and raw_data:
            alerts = [{"signal": raw_data, "raw_data": raw_data}]

        print(f"🔍 Processing {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({
                "status": "alert_processed", 
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        else:
            print("⚠️ No valid alerts found in webhook")
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print(f"❌ Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

# Home page for checking
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver is active",
        "monitored_stocks": STOCK_LIST,
        "active_signals": {k: v for k, v in signal_memory.items()},
        "timestamp": datetime.utcnow().isoformat()
    })

# Test Telegram and external server
def test_services():
    print("Testing services...")
    
    # Test Telegram
    telegram_result = send_telegram_to_all("🔧 Test message from bot - System is working!")
    print(f"Telegram test result: {telegram_result}")
    
    # Test external server
    external_result = send_post_request("Test message", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    print(f"External API test result: {external_result}")
    
    return telegram_result and external_result

# Run the application
if __name__ == "__main__":
    # Test services first
    test_services()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Server started on port {port}")
    print(f"🟢 Telegram receiver: {CHAT_ID}")
    print(f"🟢 Monitoring stocks: {', '.join(STOCK_LIST)}")
    print(f"🟢 Saudi Timezone: UTC+{TIMEZONE_OFFSET}")
    print(f"🟢 Required signals: {REQUIRED_SIGNALS}")
    print(f"🟢 External API: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    print("🟢 Waiting for TradingView webhooks...")
    app.run(host="0.0.0.0", port=port)
