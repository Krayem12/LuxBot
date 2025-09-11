from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import logging
from typing import List, Dict, Any, Optional
import hashlib

app = Flask(__name__)

# 🔹 إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 2
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
MAX_MEMORY_SYMBOLS = 100

# 🔹 إعداد Webull
WEBULL_USERNAME = os.environ.get("WEBULL_USERNAME", "")
WEBULL_PASSWORD = os.environ.get("WEBULL_PASSWORD", "")
WEBULL_DEVICE_ID = os.environ.get("WEBULL_DEVICE_ID", "1234567890")
WEBULL_TOKEN = None
WEBULL_TOKEN_EXPIRY = None

# 🔹 الحصول على التوقيت السعودي
def get_saudi_time() -> str:
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

def remove_html_tags(text: str) -> str:
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# 🔹 مصادقة Webull
def webull_login() -> bool:
    global WEBULL_TOKEN, WEBULL_TOKEN_EXPIRY
    
    try:
        if WEBULL_TOKEN and WEBULL_TOKEN_EXPIRY and datetime.utcnow() < WEBULL_TOKEN_EXPIRY:
            return True
            
        login_url = "https://userapi.webull.com/api/passport/login/v2/account"
        payload = {
            "account": WEBULL_USERNAME,
            "password": WEBULL_PASSWORD,
            "deviceId": WEBULL_DEVICE_ID,
            "deviceName": "python-trading-bot",
            "grade": 1,
            "regionId": 1
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.post(login_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            WEBULL_TOKEN = data.get("accessToken")
            expires_in = data.get("expireIn", 86400)
            
            if WEBULL_TOKEN:
                WEBULL_TOKEN_EXPIRY = datetime.utcnow() + timedelta(seconds=expires_in - 300)
                logger.info("✅ Webull login successful")
                return True
        
        logger.error(f"❌ Webull login failed: {response.status_code} - {response.text}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Webull login error: {e}")
        return False

# 🔹 البحث عن عقود Options مناسبة
def find_suitable_options(symbol: str, direction: str) -> Dict[str, Any]:
    if not webull_login():
        return None
        
    try:
        # أولاً نحتاج إلى معرف رمز السهم في Webull
        search_url = f"https://quotes-gw.webullbroker.com/api/search/v5/tickers?keyword={symbol}&pageIndex=1&pageSize=20"
        
        headers = {
            "Authorization": f"Bearer {WEBULL_TOKEN}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        search_response = requests.get(search_url, headers=headers, timeout=10)
        
        if search_response.status_code != 200:
            logger.error(f"❌ Failed to search for {symbol}: {search_response.status_code}")
            return None
            
        search_data = search_response.json()
        if not search_data or "tickers" not in search_data or not search_data["tickers"]:
            logger.error(f"❌ No tickers found for {symbol}")
            return None
            
        # استخدام أول نتيجة بحث
        ticker_id = search_data["tickers"][0].get("tickerId")
        symbol_name = search_data["tickers"][0].get("symbol")
        
        if not ticker_id:
            logger.error(f"❌ No ticker ID found for {symbol}")
            return None
        
        # الحصول على سعر السهم الحالي
        quote_url = f"https://quoteapi.webull.com/api/quote/tickerRealTime/getQuote?tickerId={ticker_id}&includeSecu=1&includeQuote=1"
        
        response = requests.get(quote_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to get quote for {symbol}: {response.status_code}")
            return None
            
        quote_data = response.json()
        current_price = quote_data.get("close", 0)
        
        if current_price == 0:
            logger.error(f"❌ Could not get current price for {symbol}")
            return None
        
        # الحصول على قائمة عقود Options
        expiry_dates_url = f"https://quoteapi.webull.com/api/quote/option/queryExpirationDateList?tickerId={ticker_id}"
        expiry_response = requests.get(expiry_dates_url, headers=headers, timeout=10)
        
        if expiry_response.status_code != 200:
            logger.error(f"❌ Failed to get expiry dates for {symbol}: {expiry_response.status_code}")
            return None
            
        expiry_dates = expiry_response.json()
        if not expiry_dates:
            logger.error(f"❌ No expiry dates found for {symbol}")
            return None
            
        # استخدام أقرب تاريخ انتهاء
        nearest_expiry = expiry_dates[0].get("date", "")
        
        # الحصول على عقود Options للتاريخ المحدد
        options_url = f"https://quoteapi.webull.com/api/quote/option/queryOptionQuoteList?tickerId={ticker_id}&expireDate={nearest_expiry}"
        options_response = requests.get(options_url, headers=headers, timeout=10)
        
        if options_response.status_code != 200:
            logger.error(f"❌ Failed to get options for {symbol}: {options_response.status_code}")
            return None
            
        options_data = options_response.json()
        
        # تصفية العقود حسب النوع (Call/Put) والسعر
        option_type = "Call" if direction.lower() == "bullish" else "Put"
        suitable_options = []
        
        for option in options_data:
            if option.get("direction") == option_type:
                strike_price = option.get("strikePrice", 0)
                option_price = option.get("close", 0) or option.get("lastPrice", 0)
                
                # حساب قيمة العقد (سعر العقد * 100)
                contract_value = option_price * 100
                
                # التحقق إذا كانت القيمة ضمن النطاق المطلوب
                if 250 <= contract_value <= 350:
                    suitable_options.append({
                        "strike": strike_price,
                        "price": option_price,
                        "value": contract_value,
                        "expiry": nearest_expiry,
                        "symbol": option.get("symbol", ""),
                        "volume": option.get("volume", 0),
                        "openInterest": option.get("openInterest", 0)
                    })
        
        # ترتيب العقود حسب حجم التداول أو الفائدة المفتوحة
        if suitable_options:
            suitable_options.sort(key=lambda x: x.get("volume", 0) + x.get("openInterest", 0), reverse=True)
            return suitable_options[0]  # أفضل عقد
        
        logger.warning(f"⚠️ No suitable options found for {symbol} with value between $250-$350")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error finding options for {symbol}: {e}")
        return None

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
                time.sleep(2 ** attempt)
    
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
        return ["BTCUSDT", "ETHUSDT", "SPX", "SPX500", "NASDAQ", "NASDAQ100", "US30", "DOW", 
                "XAUUSD", "GOLD", "XAGUSD", "SILVER", "OIL", "CRUDE", "TSLA", "AAPL", "MSFT", 
                "NVDA", "AMZN", "GOOGL", "META", "NFLX", "ARKK", "QQQ", "SPY", "IWM", "DIA"]

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
        "bearish i-choch", "bearish i-bos", "bos bearish",
        "overbought", "hyper wave.*downward", "downward signal", "selling pressure",
        "strong bearish", "bearish confluence", "distribution zone", "supply zone",
        "reversal.*bearish", "bearish.*reversal", "top.*formation", "double.*top"
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
        "bullish i-choch", "bullish i-bos", "bos bullish",
        "oversold", "hyper wave.*upward", "upward signal", "buying pressure",
        "strong bullish", "bullish confluence", "accumulation zone", "demand zone",
        "reversal.*bullish", "bullish.*reversal", "bottom.*formation", "double.*bottom"
    ]
    
    bearish_count = sum(1 for term in bearish_indicators if re.search(term, signal_lower))
    bullish_count = sum(1 for term in bullish_indicators if re.search(term, signal_lower))
    
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

def extract_symbol(message: str, original_ticker: str = "") -> str:
    message_upper = message.upper()
    
    if original_ticker and original_ticker != "UNKNOWN":
        clean_ticker = re.sub(r'[^A-Z0-9]', '', original_ticker.upper())
        if clean_ticker in STOCK_LIST:
            return clean_ticker
    
    # البحث عن رموز الأسهم المعروفة
    for symbol in STOCK_LIST:
        # البحث عن الرمز ككلمة كاملة
        symbol_pattern = r'\b' + re.escape(symbol) + r'\b'
        if re.search(symbol_pattern, message_upper):
            return symbol
    
    # البحث عن أنماط خاصة
    patterns = [
        (r'\bSPX\b.*\b500\b|\b500\b.*\bSPX\b|\bSPX500\b', "SPX500"),
        (r'\bNASDAQ\b.*\b100\b|\b100\b.*\bNASDAQ\b|\bNASDAQ100\b', "NASDAQ100"),
        (r'\bXAUUSD\b|\bGOLD\b', "XAUUSD"),
        (r'\bXAGUSD\b|\bSILVER\b', "XAGUSD"),
        (r'\bBTCUSDT\b|\bBTC\b.*\bUSDT\b', "BTCUSDT"),
        (r'\bBTC\b', "BTCUSDT"),
        (r'\bETHUSDT\b|\bETH\b.*\bUSDT\b', "ETHUSDT"),
        (r'\bETH\b', "ETHUSDT"),
        (r'\bDOW\b|\bUS30\b|\b30\b', "US30"),
        (r'\bOIL\b|\bCRUDE\b', "OIL"),
        (r'\bTSLA\b', "TSLA"),
        (r'\bAAPL\b', "AAPL"),
        (r'\bMSFT\b', "MSFT"),
        (r'\bNVDA\b', "NVDA"),
        (r'\bAMZN\b', "AMZN"),
        (r'\bGOOGL\b|\bGOOGLE\b', "GOOGL"),
        (r'\bMETA\b|\bFACEBOOK\b', "META"),
        (r'\bNFLX\b|\bNETFLIX\b', "NFLX"),
        (r'\bARKK\b', "ARKK"),
        (r'\bQQQ\b', "QQQ"),
        (r'\bSPY\b', "SPY"),
        (r'\bIWM\b', "IWM"),
        (r'\bDIA\b', "DIA"),
    ]
    
    for pattern, symbol in patterns:
        if re.search(pattern, message_upper, re.IGNORECASE):
            return symbol
    
    # البحث عن أرقام قد تكون أسعار إضراب
    strike_price_match = re.search(r'\b(\d{3,5})\b', message_upper)
    if strike_price_match:
        strike_price = strike_price_match.group(1)
        logger.info(f"🔍 Found potential strike price: {strike_price}")
    
    # تحديد الاتجاه لاختيار الرمز الافتراضي المناسب
    direction = determine_signal_direction(message, "")
    if direction == "bullish":
        logger.warning(f"⚠️  Using default BULL symbol for: {message[:50]}...")
        return "GENERIC_BULL"
    elif direction == "bearish":
        logger.warning(f"⚠️  Using default BEAR symbol for: {message[:50]}...")
        return "GENERIC_BEAR"
    
    return "UNKNOWN"

def generate_signal_hash(signal_text: str, symbol: str) -> str:
    """إنشاء هاش فريد للإشارة للكشف عن التكرار"""
    normalized_text = re.sub(r'\s+', ' ', signal_text.lower().strip())
    content = f"{symbol}_{normalized_text}"
    return hashlib.md5(content.encode()).hexdigest()[:8]

def normalize_text_for_comparison(text: str) -> str:
    """تطبيع النص للمقارنة مع إزالة العناصر غير المهمة"""
    # إزالة الرموز والمسافات الزائدة
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text).strip()
    
    # إزالة الكلمات الشائعة غير المهمة
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                   'of', 'with', 'by', 'is', 'are', 'was', 'were', 'this', 'that', 'it'}
    words = [word for word in text.split() if word not in common_words]
    
    return ' '.join(sorted(set(words)))[:100]

def process_alerts(alerts: List[Any]):
    for alert in alerts:
        try:
            current_time = datetime.utcnow()
            
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
            
            # إنشاء هاش فريد للإشارة
            signal_hash = generate_signal_hash(signal_text, extracted_ticker)
            
            # تهيئة الذاكرة للرمز إذا لم يكن موجوداً
            if extracted_ticker not in signal_memory:
                signal_memory[extracted_ticker] = {"bullish": [], "bearish": []}
            
            signal_data = {
                'text': signal_text,
                'timestamp': current_time,
                'direction': direction,
                'original_text': signal_text,
                'normalized_text': normalize_text_for_comparison(signal_text),
                'hash': signal_hash
            }
            
            # التحقق من التكرار باستخدام الهاش
            cutoff = current_time - timedelta(minutes=15)
            existing_signals = [
                sig for sig in signal_memory[extracted_ticker][direction] 
                if sig['timestamp'] > cutoff
            ]
            
            is_duplicate = any(sig.get('hash') == signal_hash for sig in existing_signals)
            
            if is_duplicate:
                logger.info(f"⚠️  Ignored duplicate signal for {extracted_ticker} (Hash: {signal_hash})")
                continue
            
            # إضافة الإشارة
            signal_memory[extracted_ticker][direction].append(signal_data)
            logger.info(f"✅ Stored {direction} signal for {extracted_ticker} (Hash: {signal_hash})")
            
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
                        display_text = sig['original_text'][:100] + "..." if len(sig['original_text']) > 100 else sig['original_text']
                        signal_details.append(f"{i}. {display_text}")
                    
                    saudi_time = get_saudi_time()
                    
                    # البحث عن عقد مناسب من Webull
                    option_info = None
                    if symbol not in ["GENERIC_BULL", "GENERIC_BEAR"]:
                        option_info = find_suitable_options(symbol, direction)
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية</b>

📊 <b>الإشارات المستلمة:</b>
{chr(10).join(signal_details)}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}"""

                        if option_info:
                            message += f"""

📈 <b>عُمر مقترح:</b>
• السعر: ${option_info['price']:.2f}
• الإضراب: ${option_info['strike']:.2f}
• القيمة: ${option_info['value']:.2f}
• الإنتهاء: {option_info['expiry']}
• الرمز: {option_info['symbol']}"""

                        message += """

🎯 <b>ملاحظة:</b> يمكن استخدام مستويات فيبوناتشي (0.382, 0.618) ومستويات SMC للأهداف

⚠️ <b>تنبيه:</b> هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك"""
                        signal_type = "BULLISH_CONFIRMATION"
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية</b>

📊 <b>الإشارات المستلمة:</b>
{chr(10).join(signal_details)}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}"""

                        if option_info:
                            message += f"""

📉 <b>عُمر مقترح:</b>
• السعر: ${option_info['price']:.2f}
• الإضراب: ${option_info['strike']:.2f}
• القيمة: ${option_info['value']:.2f}
• الإنتهاء: {option_info['expiry']}
• الرمز: {option_info['symbol']}"""

                        message += """

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
        "active_symbols": list(signal_memory.keys())[:10]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🟢 Server started on port {port}")
    logger.info(f"🔒 Monitoring signals with high accuracy")
    logger.info(f"📊 Required signals: {REQUIRED_SIGNALS}")
    logger.info(f"📦 Memory limit: {MAX_MEMORY_SYMBOLS} symbols")
    logger.info(f"🌐 External API: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    logger.info(f"🎯 Added Fibonacci & SMC levels for better target identification")
    logger.info(f"📈 Webull integration: {'Enabled' if WEBULL_USERNAME and WEBULL_PASSWORD else 'Disabled'}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
