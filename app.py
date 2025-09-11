from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import logging
from typing import List, Dict, Any, Optional

app = Flask(__name__)

# 🔹 إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 3
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
MAX_MEMORY_SYMBOLS = 100  # حد أقصى للرموز في الذاكرة

# 🔹 الحصول على التوقيت السعودي
def get_saudi_time() -> str:
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

def remove_html_tags(text: str) -> str:
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def send_telegram_to_all(message: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            logger.info(f"✅ Telegram attempt {attempt + 1}: {response.status_code}")
            
            if response.status_code == 200:
                return True
                
        except Exception as e:
            logger.error(f"❌ Telegram error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
    
    return False

def send_post_request(message: str, indicators: str, signal_type: Optional[str] = None, max_retries: int = 2) -> bool:
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
    
    for attempt in range(max_retries):
        try:
            url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
            response = requests.post(url, json=payload, timeout=5)
            logger.info(f"✅ External API attempt {attempt + 1}: {response.status_code}")
            
            if response.status_code == 200:
                return True
                
        except requests.exceptions.Timeout:
            logger.warning(f"⏰ External API timeout attempt {attempt + 1}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"🔌 External API connection error attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"❌ External API error attempt {attempt + 1}: {e}")
            
        if attempt < max_retries - 1:
            import time
            time.sleep(1)
    
    return False

def load_stocks() -> List[str]:
    try:
        with open('stocks.txt', 'r', encoding='utf-8') as f:
            return [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        return ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30", "XAUUSD", "XAGUSD", "OIL"]

STOCK_LIST = load_stocks()

# استخدام dict عادي بدلاً من defaultdict لتجنب Memory Leak
signal_memory: Dict[str, Dict[str, List[Dict]]] = {}

def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    symbols_to_remove = []
    
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            if direction in signals:
                signal_memory[symbol][direction] = [
                    sig_data for sig_data in signal_memory[symbol][direction] 
                    if sig_data['timestamp'] > cutoff
                ]
        
        # حذف الرمز إذا كان فارغاً أو تجاوز الحد
        if (not signal_memory[symbol].get('bullish') and 
            not signal_memory[symbol].get('bearish')):
            symbols_to_remove.append(symbol)
    
    # حذف الرموز الفارغة
    for symbol in symbols_to_remove:
        if symbol in signal_memory:
            del signal_memory[symbol]
    
    # تطبيق حد الذاكرة
    if len(signal_memory) > MAX_MEMORY_SYMBOLS:
        oldest_symbols = sorted(signal_memory.keys(), 
                              key=lambda x: min([sig['timestamp'] for sig in 
                                              signal_memory[x].get('bullish', []) + 
                                              signal_memory[x].get('bearish', []) 
                                              if sig['timestamp'] > datetime.min],
                                              default=datetime.min))
        for symbol in oldest_symbols[:len(signal_memory) - MAX_MEMORY_SYMBOLS]:
            if symbol in signal_memory:
                del signal_memory[symbol]

def extract_symbol(message: str, original_ticker: str = "") -> str:
    message_upper = message.upper()
    
    if original_ticker and original_ticker != "UNKNOWN":
        clean_ticker = re.sub(r'[^A-Z0-9]', '', original_ticker.upper())
        if clean_ticker in STOCK_LIST:
            return clean_ticker
    
    # البحث بالترتيب من الأطول إلى الأقصر
    for symbol in sorted(STOCK_LIST, key=len, reverse=True):
        symbol_pattern = r'\b' + re.escape(symbol) + r'\b'
        if re.search(symbol_pattern, message_upper):
            return symbol
    
    # الأنماط الخاصة (مرتبة من الأكثر تحديداً إلى الأقل)
    patterns = [
        (r'\bSPX\b.*\b500\b|\b500\b.*\bSPX\b', "SPX500"),
        (r'\bNASDAQ\b.*\b100\b|\b100\b.*\bNASDAQ\b', "NASDAQ100"),
        (r'\bXAUUSD\b|\bGOLD\b', "XAUUSD"),
        (r'\bXAGUSD\b|\bSILVER\b', "XAGUSD"),
        (r'\bBTCUSDT\b|\bBTC\b.*\bUSDT\b', "BTCUSDT"),
        (r'\bBTC\b', "BTCUSDT"),
        (r'\bETHUSDT\b|\bETH\b.*\bUSDT\b', "ETHUSDT"),
        (r'\bETH\b', "ETHUSDT"),
        (r'\bDOW\b|\bUS30\b|\b30\b', "US30"),
        (r'\bOIL\b|\bCRUDE\b', "OIL"),
    ]
    
    for pattern, symbol in patterns:
        if re.search(pattern, message_upper, re.IGNORECASE):
            return symbol
    
    return "UNKNOWN"

def determine_signal_direction(signal_text: str, original_direction: str = "") -> str:
    signal_lower = signal_text.lower()
    
    if original_direction:
        original_lower = original_direction.lower()
        bearish_terms = ["bearish", "short", "sell", "هبوطي", "بيع", "هابط", "put", "down"]
        bullish_terms = ["bullish", "long", "buy", "صعودي", "شراء", "صاعد", "call", "up"]
        
        if any(term in original_lower for term in bearish_terms):
            return "bearish"
        elif any(term in original_lower for term in bullish_terms):
            return "bullish"
    
    bearish_indicators = [
        "bearish", "bear", "short", "sell", "put", "down", "downside", "drop", 
        "decline", "fall", "dump", "crash", "breakdown", "resistance", "rejection",
        "هبوطي", "بيع", "هابط", "نزول", "هبوط", "تراجع", "انخفاض", "سقوط", "مقاومة",
        "📉", "🔻", "🔽", "⏬", "🔴", "🟥",
        "fibonacci resistance", "fib 0.618", "fib 0.786", "fibonacci top",
        "order block sell", "ob sell", "bearish ob", "sellside ob",
        "imbalance top", "imb top", "fair value gap sell", "fvg sell",
        "liquidity pool", "liquidity grab", "market maker sell", "mm sell",
        "swing high", "internal high", "premium zone", "discount rejection",
        "previous day high", "previous week high", "previous month high",
        "bearish i-choch", "bearish i-bos", "bos bearish"
    ]
    
    bullish_indicators = [
        "bullish", "bull", "long", "buy", "call", "up", "upside", "rise",
        "rally", "jump", "pump", "breakout", "recovery", "support", "bounce",
        "صعودي", "شراء", "صاعد", "صعود", "ارتفاع", "تحسن", "قفزة", "دعم",
        "📈", "🔺", "🔼", "⏫", "🟢", "🟩",
        "fibonacci support", "fib 0.236", "fib 0.382", "fib 0.5", "fibonacci bottom",
        "order block buy", "ob buy", "bullish ob", "buyside ob",
        "imbalance bottom", "imb bottom", "fair value gap buy", "fvg buy",
        "liquidity sweep", "liquidity take", "market maker buy", "mm buy",
        "swing low", "internal low", "discount zone", "premium bounce",
        "previous day low", "previous week low", "previous month low",
        "bullish i-choch", "bullish i-bos", "bos bullish"
    ]
    
    bearish_count = sum(1 for term in bearish_indicators if term in signal_lower)
    bullish_count = sum(1 for term in bullish_indicators if term in signal_lower)
    
    logger.info(f"📊 {signal_text[:30]}... - Bearish: {bearish_count}, Bullish: {bullish_count}")
    
    if bearish_count > 0 and bearish_count > bullish_count:
        return "bearish"
    elif bullish_count > 0 and bullish_count > bearish_count:
        return "bullish"
    
    luxalgo_patterns = [
        (r'hyperth.*bearish', "bearish"),
        (r'hyperth.*short', "bearish"),
        (r'hyperth.*sell', "bearish"),
        (r'هايبيرث.*هبوطي', "bearish"),
        (r'هايبيرث.*بيع', "bearish"),
        (r'vip.*bearish', "bearish"),
        (r'vip.*short', "bearish"),
        (r'premium.*bearish', "bearish"),
        (r'premium.*short', "bearish"),
        (r'sell.*signal', "bearish"),
        (r'short.*signal', "bearish"),
        (r'hyperth.*bullish', "bullish"),
        (r'hyperth.*long', "bullish"),
        (r'hyperth.*buy', "bullish"),
        (r'هايبيرث.*صعودي', "bullish"),
        (r'هايبيرث.*شراء', "bullish"),
        (r'vip.*bullish', "bullish"),
        (r'vip.*long', "bullish"),
        (r'premium.*bullish', "bullish"),
        (r'premium.*long', "bullish"),
        (r'buy.*signal', "bullish"),
        (r'long.*signal', "bullish")
    ]
    
    for pattern, direction in luxalgo_patterns:
        if re.search(pattern, signal_lower, re.IGNORECASE):
            return direction
    
    logger.warning("⚠️  Could not determine clear direction, ignoring signal")
    return "unknown"

def normalize_text_for_comparison(text: str) -> str:
    """تطبيع النص للمقارنة مع إزالة العناصر غير المهمة"""
    # إزالة الرموز والمسافات الزائدة
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    
    # إزالة الكلمات الشائعة غير المهمة
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                   'of', 'with', 'by', 'is', 'are', 'was', 'were', 'this', 'that', 'it'}
    words = [word for word in text.split() if word not in common_words]
    
    return ' '.join(sorted(set(words)))[:100]  # حد أقصى للطول

def process_alerts(alerts: List[Any]):
    for alert in alerts:
        try:
            current_time = datetime.utcnow()  # وقت مختلف لكل إشارة
            
            if isinstance(alert, dict):
                signal_text = alert.get("signal", alert.get("message", "")).strip()
                original_direction = alert.get("direction", "").strip()
                ticker = alert.get("ticker", "").strip().upper()
            else:
                signal_text = str(alert).strip()
                original_direction = ""
                ticker = ""
            
            if not signal_text:
                continue
                
            extracted_ticker = extract_symbol(signal_text, ticker)
            if extracted_ticker == "UNKNOWN":
                logger.warning(f"⚠️  Could not extract symbol from: {signal_text[:50]}...")
                continue
            
            direction = determine_signal_direction(signal_text, original_direction)
            
            if direction == "unknown":
                logger.warning(f"⚠️  Ignoring signal with unclear direction: {signal_text[:50]}...")
                continue
            
            logger.info(f"🎯 Symbol: {extracted_ticker}, Direction: {direction}")
            
            # تهيئة الذاكرة للرمز إذا لم يكن موجوداً
            if extracted_ticker not in signal_memory:
                signal_memory[extracted_ticker] = {"bullish": [], "bearish": []}
            
            signal_data = {
                'text': signal_text,
                'timestamp': current_time,
                'direction': direction,
                'original_text': signal_text,
                'normalized_text': normalize_text_for_comparison(signal_text)
            }
            
            # التحقق من التكرار
            cutoff = current_time - timedelta(minutes=15)
            existing_signals = [
                sig for sig in signal_memory[extracted_ticker][direction] 
                if sig['timestamp'] > cutoff
            ]
            
            is_duplicate = False
            new_normalized = signal_data['normalized_text']
            
            for sig in existing_signals:
                if 'normalized_text' in sig and sig['normalized_text'] == new_normalized:
                    logger.info(f"⚠️  Ignored duplicate signal for {extracted_ticker}")
                    is_duplicate = True
                    break
            
            if is_duplicate:
                continue
            
            # إضافة الإشارة
            signal_memory[extracted_ticker][direction].append(signal_data)
            logger.info(f"✅ Stored {direction} signal for {extracted_ticker}")
            
        except Exception as e:
            logger.error(f"❌ Error processing alert: {e}", exc_info=True)
            continue
    
    cleanup_signals()
    
    # معالجة الإشارات المجمعة
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_list = signals.get(direction, [])
            if len(signal_list) >= REQUIRED_SIGNALS:
                try:
                    signal_count = len(signal_list)
                    signal_details = []
                    
                    for i, sig in enumerate(signal_list, 1):
                        display_text = sig['original_text']
                        signal_details.append(f"{i}. {display_text}")
                    
                    saudi_time = get_saudi_time()
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية</b>

📊 <b>الإشارات المستلمة:</b>
{chr(10).join(signal_details)}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

🎯 <b>ملاحظة:</b> يمكن استخدام مستويات فيبوناتشي (0.382, 0.618) ومستويات SMC للأهداف

⚠️ <b>تنبيه:</b> هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك"""
                        signal_type = "BULLISH_CONFIRMATION"
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية</b>

📊 <b>الإشارات المستلمة:</b>
{chr(10).join(signal_details)}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

🎯 <b>ملاحظة:</b> يمكن استخدام مستويات فيبوناتشي (0.382, 0.618) ومستويات SMC للأهداف

⚠️ <b>تنبيه:</b> هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك"""
                        signal_type = "BEARISH_CONFIRMATION"
                    
                    # إرسال مع retry logic
                    telegram_success = send_telegram_to_all(message)
                    external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)
                    
                    # مسح فقط إذا نجح كلا الإرسالين
                    if telegram_success and external_success:
                        logger.info(f"🎉 تم إرسال تنبيه {direction} لـ {symbol}")
                        signal_memory[symbol][direction] = []
                    else:
                        logger.warning(f"⚠️  إرسال جزئي لـ {symbol} - سيتم المحاولة لاحقاً")
                        
                except Exception as e:
                    logger.error(f"❌ Error sending alerts for {symbol}: {e}", exc_info=True)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        
        if request.is_json:
            try:
                data = request.get_json(force=True)
                if isinstance(data, list):
                    alerts = data
                elif isinstance(data, dict):
                    if "alerts" in data:
                        alerts = data["alerts"]
                    else:
                        alerts = [data]
            except Exception as e:
                logger.error(f"❌ JSON parsing error: {e}")
                # محاولة parsing كـ raw text
                try:
                    raw_data = request.get_data(as_text=True).strip()
                    if raw_data:
                        alerts = [{"signal": raw_data}]
                except:
                    pass
        
        if not alerts:
            raw_data = request.get_data(as_text=True).strip()
            if raw_data:
                alerts = [{"signal": raw_data}]
        
        logger.info(f"📨 Received {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "processed", "count": len(alerts)}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200
            
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "active",
        "time": get_saudi_time(),
        "required_signals": REQUIRED_SIGNALS,
        "stocks": STOCK_LIST,
        "memory_stats": {
            symbol: {
                "bullish": len(signals.get("bullish", [])),
                "bearish": len(signals.get("bearish", []))
            } for symbol, signals in signal_memory.items()
        },
        "memory_usage": f"{len(signal_memory)}/{MAX_MEMORY_SYMBOLS} symbols"
    })

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "memory_usage": len(signal_memory),
        "active_symbols": list(signal_memory.keys())[:10]  # أول 10 رموز فقط
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🟢 Server started on port {port}")
    logger.info(f"🔒 Monitoring signals with high accuracy")
    logger.info(f"📊 Required signals: {REQUIRED_SIGNALS}")
    logger.info(f"📦 Memory limit: {MAX_MEMORY_SYMBOLS} symbols")
    logger.info(f"🌐 External API: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    logger.info(f"🎯 Added Fibonacci & SMC levels for better target identification")
    
    app.run(host="0.0.0.0", port=port, debug=False)
