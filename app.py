from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import hashlib
import logging

app = Flask(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3

# 🔹 عدد الإشارات المطلوبة
REQUIRED_SIGNALS = 2

# 🔹 بيانات التليجرام
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 وقت التكرار المسموح به (5 دقائق)
DUPLICATE_TIMEFRAME = 300

# 🔹 المؤشرات والفلاتر
KNOWN_INDICATORS = [
    "Internal High", "Internal Low", "Swing High", "Swing Low",
    "Premium", "Equilibrium Average", "Discount", "Bullish I-CHoCH",
    "Bearish I-CHoCH", "Bullish I-BOS", "Bearish I-BOS", "Highest OB Top",
    "Lowest OB Bottom", "Imbalance Top", "Imbalance Bottom", "Imbalance Average",
    "Previous Day High", "Previous Day Low", "Previous Week High",
    "Previous Week Low", "Previous Month High", "Previous Month Low",
    "Discount Zone", "HGH5 & LOWS MTF", "Daily", "Monday's", "Weekly",
    "Monthly", "Fibonacci Retracements", "Fibonacci Top", "Fibonacci Bottom",
    "0.786", "0.618", "0.5", "0.382", "0.236", "Show Top/Bottom Levels",
    "Anchor To Origin", "LuxAlgo", "Fibonacci", "Retracement"
]

# 🔹 مستويات فيبوناتشي
FIBONACCI_LEVELS = {
    "0.786": "مستوى فيبوناتشي 0.786",
    "0.618": "مستوى فيبوناتشي 0.618",
    "0.5": "مستوى فيبوناتشي 0.5",
    "0.382": "مستوى فيبوناتشي 0.382",
    "0.236": "مستوى فيبوناتشي 0.236"
}

# 🔹 Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# 🔹 التوقيت السعودي
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# 🔹 إزالة HTML
def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# 🔹 بصمة فريدة
def create_signal_fingerprint(symbol, direction, signal_type):
    content = f"{symbol}_{direction}_{signal_type.lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()

# 🔹 إرسال تليجرام
def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
        return False

# 🔹 تحميل قائمة الأسهم
def load_stocks():
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
            if stocks:
                return stocks
    except FileNotFoundError:
        logging.warning("stocks.txt not found, using default list")
    return ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]

STOCK_LIST = load_stocks()
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": [], "last_signals": {}})

# 🔹 إرسال POST خارجي
def send_post_request(message, indicators, signal_type=None):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    clean_message = remove_html_tags(message)
    payload = {"text": clean_message, "extras": {"indicators": indicators, "timestamp": datetime.utcnow().isoformat(), "source": "tradingview-bot", "original_signal_type": signal_type}}
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"External send error: {e}")
        return False

# 🔹 تنظيف الإشارات القديمة
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(seconds=DUPLICATE_TIMEFRAME)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [(sig, ts, fp) for sig, ts, fp in signal_memory[symbol][direction] if ts > cutoff]
        current_time = datetime.utcnow()
        signal_memory[symbol]["last_signals"] = {fp: ts for fp, ts in signal_memory[symbol]["last_signals"].items() if (current_time - ts).total_seconds() < DUPLICATE_TIMEFRAME}
        if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish'] and not signal_memory[symbol]['last_signals']:
            del signal_memory[symbol]

# 🔹 التحقق من التكرار
def is_duplicate_signal(symbol, signal_fingerprint):
    last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
    if last_seen and (datetime.utcnow() - last_seen).total_seconds() < DUPLICATE_TIMEFRAME:
        return True
    return False

# 🔹 استخراج رمز السهم
def extract_symbol(message):
    cleaned_message = re.sub(r'[^A-Z0-9]+', ' ', message.upper())
    for symbol in sorted(STOCK_LIST, key=len, reverse=True):
        if re.search(rf'\b{symbol}\b', cleaned_message):
            return symbol
    if "SPX" in cleaned_message or "500" in cleaned_message:
        return "SPX500"
    if "BTC" in cleaned_message:
        return "BTCUSDT"
    if "ETH" in cleaned_message:
        return "ETHUSDT"
    if "NASDAQ" in cleaned_message or "100" in cleaned_message:
        return "NASDAQ100"
    if "DOW" in cleaned_message or "US30" in cleaned_message or "30" in cleaned_message:
        return "US30"
    return "UNKNOWN"

# 🔹 استخراج اسم الإشارة بدقة
def extract_signal_name(raw_signal):
    signal_lower = raw_signal.lower()
    for fib_level, fib_name in FIBONACCI_LEVELS.items():
        if fib_level in signal_lower:
            return fib_name
    for ind in KNOWN_INDICATORS:
        if ind.lower() in signal_lower:
            return ind
    if "bullish" in signal_lower and "bos" in signal_lower:
        return "كسر هيكل صعودي"
    elif "bearish" in signal_lower and "bos" in signal_lower:
        return "كسر هيكل هبوطي"
    return "إشارة تداول"

# 🔹 استخراج نوع الإشارة الأساسي
def extract_signal_type(signal_text):
    signal_lower = signal_text.lower()
    for fib_level in FIBONACCI_LEVELS.keys():
        if fib_level in signal_lower:
            return f"fib_{fib_level}"
    if "bos" in signal_lower:
        return "bos"
    if "choch" in signal_lower:
        return "choch"
    if "confirmation" in signal_lower:
        return "confirmation"
    if "bullish" in signal_lower:
        return "bullish"
    if "bearish" in signal_lower:
        return "bearish"
    return "unknown"

# 🔹 تنظيف اسم الإشارة
def clean_signal_name(signal_text):
    cleaned = re.sub(r'_.*$', '', signal_text)
    cleaned = re.sub(r'\s+\d+$', '', cleaned)
    return cleaned.strip()

# 🔹 معالجة التنبيهات
def process_alerts(alerts):
    now = datetime.utcnow()
    for alert in alerts:
        raw_signal = alert.get("signal", "").strip()
        ticker = alert.get("ticker", "")
        direction = "bearish" if any(w in raw_signal.lower() for w in ["bearish", "down", "put", "short"]) else "bullish"
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(raw_signal)
        if ticker == "UNKNOWN":
            continue

        # ✅ استخراج اسم الإشارة بدقة
        signal_name = extract_signal_name(raw_signal)
        signal_type = extract_signal_type(raw_signal)
        signal_fingerprint = create_signal_fingerprint(ticker, direction, signal_type)

        if is_duplicate_signal(ticker, signal_fingerprint):
            continue

        signal_memory[ticker]["last_signals"][signal_fingerprint] = now
        unique_key = f"{signal_name}_{now.timestamp()}"
        signal_memory[ticker][direction].append((unique_key, now, signal_fingerprint))

    cleanup_signals()

    for symbol, signals in signal_memory.items():
        for
