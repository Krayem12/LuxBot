# ✅ التحقق من التكرار (معدل بشكل أكثر صرامة)
def is_duplicate_signal(symbol, signal_text, signal_fingerprint):
    """التحقق مما إذا كانت الإشارة مكررة خلال الفترة الزمنية المحددة"""
    if symbol in signal_memory:
        # التحقق من البصمة أولاً
        last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
        if last_seen:
            time_diff = (datetime.utcnow() - last_seen).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ إشارة مكررة لـ {symbol} تم تجاهلها (البصمة، الفارق: {time_diff:.1f} ثانية)")
                return True
        
        # تنظيف الإشارة الحالية من الرموز والأحرف الخاصة والمسافات الزائدة
        current_signal = signal_text.strip()
        current_clean = re.sub(r'[^\w\s]', '', current_signal.lower())
        current_clean = re.sub(r'\s+', ' ', current_clean).strip()
        
        # إزالة اسم السهم من الإشارة للمقارنة
        current_without_symbol = re.sub(r'\b' + re.escape(symbol) + r'\b', '', current_clean).strip()
        
        for existing_signal, ts, fp in signal_memory[symbol]["bullish"] + signal_memory[symbol]["bearish"]:
            # تنظيف الإشارة المخزنة
            existing_clean = re.sub(r'[^\w\s]', '', existing_signal.split('_')[0].lower())
            existing_clean = re.sub(r'\s+', ' ', existing_clean).strip()
            
            # إزالة اسم السهم من الإشارة المخزنة
            existing_without_symbol = re.sub(r'\b' + re.escape(symbol) + r'\b', '', existing_clean).strip()
            
            # المقارنة بعد إزالة اسم السهم
            if current_without_symbol == existing_without_symbol and current_without_symbol != "":
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"⚠️ إشارة مكررة لـ {symbol} تم تجاهلها (نفس المحتوى بعد إزالة السهم، الفارق: {time_diff:.1f} ثانية)")
                    print(f"   الإشارة الحالية: {current_signal}")
                    print(f"   الإشارة السابقة: {existing_signal.split('_')[0]}")
                    return True
            
            # مقارنة أكثر صرامة: إذا كانت الإشارتان متطابقتان تماماً بما في ذلك اسم السهم
            if current_clean == existing_clean:
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"⚠️ إشارة مكررة لـ {symbol} تم تجاهلها (نفس المحتوى الكامل، الفارق: {time_diff:.1f} ثانية)")
                    return True
            
            # مقارنة الكلمات الرئيسية (إذا احتوت على نفس الكلمات الأساسية)
            current_words = set(current_clean.split())
            existing_words = set(existing_clean.split())
            
            # إذا كان هناك تشابه كبير في الكلمات الرئيسية (80% من الكلمات متشابهة)
            common_words = current_words.intersection(existing_words)
            similarity_ratio = len(common_words) / max(len(current_words), len(existing_words))
            
            if similarity_ratio >= 0.8 and len(common_words) >= 2:  # 80% تشابه وكرتين مشتركتين على الأقل
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"⚠️ إشارة متشابهة لـ {symbol} تم تجاهلها (تشابه {similarity_ratio:.0%}، الفارق: {time_diff:.1f} ثانية)")
                    print(f"   الكلمات المشتركة: {common_words}")
                    return True
    
    return False
