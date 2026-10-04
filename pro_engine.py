import requests
import time


# =========================================================
# ASTER PRO ENGINE
# Отдельный модуль для высоковероятностных сетапов
# =========================================================

ASTER_BASE = "https://fapi.asterdex.com"

PRO_EXCLUDED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT"
}

PRO_MIN_VOLUME = 15000
PRO_ORDER_THRESHOLD = 15000


# =========================================================
# Получение всех подходящих монет
# =========================================================

def get_pro_symbols():

    try:

        url = f"{ASTER_BASE}/fapi/v1/ticker/24hr"

        response = requests.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        symbols = []

        for item in data:

            symbol = item.get("symbol", "")

            if not symbol.endswith("USDT"):
                continue

            if symbol in PRO_EXCLUDED_SYMBOLS:
                continue

            try:
                volume = float(
                    item.get("quoteVolume", 0)
                )
            except:
                continue

            if volume < PRO_MIN_VOLUME:
                continue

            symbols.append(
                (symbol, volume)
            )

        return symbols

    except Exception as e:

        print(
            "❌ ASTER PRO: ошибка получения монет:",
            e
        )

        return []


# =========================================================
# Получение свечей
# =========================================================

def get_pro_klines(
    symbol,
    interval,
    limit=250
):

    try:

        url = f"{ASTER_BASE}/fapi/v1/klines"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:

        print(
            f"❌ ASTER PRO {symbol} {interval}:",
            e
        )

        return []


# =========================================================
# Преобразование свечей
# =========================================================

def prepare_candles(klines):

    candles = []

    for k in klines:

        try:

            candles.append({
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })

        except:

            continue

    return candles


# =========================================================
# EMA
# =========================================================

def calculate_ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    values,
    period=14
):

    if len(values) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = (
            values[i] - values[i - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    avg_gain = (
        sum(gains[:period]) / period
    )

    avg_loss = (
        sum(losses[:period]) / period
    )

    if avg_loss == 0:
        return 100

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# =========================================================
# ATR
# =========================================================

def calculate_atr(
    candles,
    period=14
):

    if len(candles) <= period:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
            )
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    atr = (
        sum(true_ranges[:period])
        / period
    )

    for tr in true_ranges[period:]:

        atr = (
            (atr * (period - 1))
            + tr
        ) / period

    return atr


# =========================================================
# MACD
# =========================================================

def calculate_macd(
    values,
    fast_period=12,
    slow_period=26,
    signal_period=9
):

    if len(values) < slow_period + signal_period:
        return None, None, None

    macd_values = []

    for i in range(
        slow_period,
        len(values) + 1
    ):

        window = values[:i]

        ema_fast = calculate_ema(
            window,
            fast_period
        )

        ema_slow = calculate_ema(
            window,
            slow_period
        )

        if ema_fast is None or ema_slow is None:
            continue

        macd_values.append(
            ema_fast - ema_slow
        )

    if len(macd_values) < signal_period:
        return None, None, None

    signal = calculate_ema(
        macd_values,
        signal_period
    )

    if signal is None:
        return None, None, None

    macd = macd_values[-1]

    histogram = macd - signal

    return macd, signal, histogram


# =========================================================
# Средний объём
# =========================================================

def average_volume(
    candles,
    period=20
):

    if len(candles) < period:
        return None

    volumes = [
        c["volume"]
        for c in candles[-period:]
    ]

    return (
        sum(volumes)
        / len(volumes)
    )


# =========================================================
# Последняя цена
# =========================================================

def get_last_price(candles):

    if not candles:
        return None

    return candles[-1]["close"]


# =========================================================
# ASTER PRO тест
# =========================================================

def test_pro_engine():

    print("")
    print("==============================")
    print("🧠 ASTER PRO ENGINE")
    print("==============================")

    symbols = get_pro_symbols()

    print(
        f"🔎 Монет для PRO анализа: "
        f"{len(symbols)}"
    )

    if not symbols:
        print(
            "⚪ Подходящих монет нет"
        )
        return

    symbol = symbols[0][0]

    print(
        f"🧪 Тестируем: {symbol}"
    )

    klines = get_pro_klines(
        symbol,
        "1h",
        250
    )

    candles = prepare_candles(
        klines
    )

    if not candles:
        print(
            "❌ Нет данных свечей"
        )
        return

    closes = [
        c["close"]
        for c in candles
    ]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    ema200 = calculate_ema(
        closes,
        200
    )

    rsi = calculate_rsi(
        closes
    )

    atr = calculate_atr(
        candles
    )

    volume = average_volume(
        candles
    )

    price = get_last_price(
        candles
    )

    print(
        f"💲 Цена: {price}"
    )

    print(
        f"📈 EMA20: {ema20}"
    )

    print(
        f"📈 EMA50: {ema50}"
    )

    print(
        f"📈 EMA200: {ema200}"
    )

    print(
        f"📊 RSI: {rsi}"
    )

    print(
        f"📐 ATR: {atr}"
    )

    print(
        f"💰 Средний объём: {volume}"
    )

    print(
        "✅ ASTER PRO ENGINE работает"
    )
# =========================================================
# ASTER PRO — АНАЛИЗ СТАКАНА
# =========================================================

def get_pro_order_book(symbol):

    try:

        url = f"{ASTER_BASE}/fapi/v1/depth"

        params = {
            "symbol": symbol,
            "limit": 100
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        buy_total = 0
        sell_total = 0

        for price, quantity in bids:

            buy_total += (
                float(price)
                * float(quantity)
            )

        for price, quantity in asks:

            sell_total += (
                float(price)
                * float(quantity)
            )

        best_bid = (
            float(bids[0][0])
            if bids else None
        )

        best_ask = (
            float(asks[0][0])
            if asks else None
        )

        if not best_bid or not best_ask:
            return None

        spread = (
            best_ask - best_bid
        )

        mid_price = (
            best_bid + best_ask
        ) / 2

        imbalance = (
            buy_total / sell_total
            if sell_total > 0
            else 999
        )

        return {
            "buy_total": buy_total,
            "sell_total": sell_total,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "mid_price": mid_price,
            "imbalance": imbalance
        }

    except Exception as e:

        print(
            f"❌ ASTER PRO стакан {symbol}:",
            e
        )

        return None
        
# =========================================================
# ASTER PRO — МУЛЬТИТАЙМФРЕЙМ
# =========================================================

def get_pro_timeframes(symbol):

    timeframes = {
        "1h": 250,
        "15m": 250,
        "5m": 250,
        "1m": 250
    }

    result = {}

    for interval, limit in timeframes.items():

        klines = get_pro_klines(
            symbol,
            interval,
            limit
        )

        candles = prepare_candles(
            klines
        )

        if not candles:
            print(
                f"⚠️ ASTER PRO {symbol}: "
                f"нет данных {interval}"
            )
            continue

        result[interval] = candles

    return result
    
# =========================================================
# ASTER PRO — СТРУКТУРА РЫНКА
# =========================================================

def analyze_market_structure(candles, lookback=30):

    if len(candles) < lookback:
        return None

    recent = candles[-lookback:]

    highest = max(
        c["high"]
        for c in recent
    )

    lowest = min(
        c["low"]
        for c in recent
    )

    current_price = recent[-1]["close"]

    previous_high = max(
        c["high"]
        for c in recent[:-5]
    )

    previous_low = min(
        c["low"]
        for c in recent[:-5]
    )

    higher_high = (
        highest > previous_high
    )

    higher_low = (
        lowest > previous_low
    )

    lower_high = (
        highest < previous_high
    )

    lower_low = (
        lowest < previous_low
    )

    bullish = (
        higher_high
        and higher_low
    )

    bearish = (
        lower_high
        and lower_low
    )

    if bullish:

        trend = "BULLISH"

    elif bearish:

        trend = "BEARISH"

    else:

        trend = "RANGE"

    return {
        "trend": trend,
        "highest": highest,
        "lowest": lowest,
        "current_price": current_price,
        "higher_high": higher_high,
        "higher_low": higher_low,
        "lower_high": lower_high,
        "lower_low": lower_low
    }

# =========================================================
# ASTER PRO — ОБЪЁМ И ИМПУЛЬС
# =========================================================

def analyze_volume_momentum(
    candles,
    volume_period=20
):

    if len(candles) < volume_period + 5:
        return None

    current = candles[-1]

    previous = candles[-2]

    average_vol = average_volume(
        candles[:-1],
        volume_period
    )

    if average_vol is None or average_vol == 0:
        return None

    current_volume = current["volume"]

    volume_ratio = (
        current_volume / average_vol
    )

    price_change = (
        (
            current["close"]
            - previous["close"]
        )
        / previous["close"]
    ) * 100

    candle_range = (
        current["high"]
        - current["low"]
    )

    if candle_range <= 0:
        candle_strength = 0
    else:
        candle_strength = (
            abs(
                current["close"]
                - current["open"]
            )
            / candle_range
        )

    bullish = (
        current["close"]
        > current["open"]
    )

    bearish = (
        current["close"]
        < current["open"]
    )

    strong_volume = (
        volume_ratio >= 1.5
    )

    strong_bullish = (
        bullish
        and strong_volume
        and price_change > 0
        and candle_strength >= 0.5
    )

    strong_bearish = (
        bearish
        and strong_volume
        and price_change < 0
        and candle_strength >= 0.5
    )

    if strong_bullish:

        momentum = "BULLISH"

    elif strong_bearish:

        momentum = "BEARISH"

    else:

        momentum = "NEUTRAL"

    return {
        "current_volume": current_volume,
        "average_volume": average_vol,
        "volume_ratio": volume_ratio,
        "price_change": price_change,
        "candle_strength": candle_strength,
        "momentum": momentum,
        "strong_volume": strong_volume
    }
    
# =========================================================
# ASTER PRO — SCORE 0-100
# =========================================================

def calculate_pro_score(
    trend_1h,
    structure_15m,
    momentum_5m,
    rsi_5m,
    macd_5m,
    order_book
):

    score = 0
    reasons = []

    # -----------------------------------------------------
    # 1. ТРЕНД 1H — максимум 25 баллов
    # -----------------------------------------------------

    if trend_1h == "BULLISH":

        score += 25
        reasons.append("🟢 1H BULLISH")

    elif trend_1h == "BEARISH":

        score += 25
        reasons.append("🔴 1H BEARISH")

    # -----------------------------------------------------
    # 2. СТРУКТУРА 15M — максимум 15 баллов
    # -----------------------------------------------------

    if structure_15m == "BULLISH":

        score += 15
        reasons.append("🟢 15M структура BULLISH")

    elif structure_15m == "BEARISH":

        score += 15
        reasons.append("🔴 15M структура BEARISH")

    # -----------------------------------------------------
    # 3. MOMENTUM 5M — максимум 15 баллов
    # -----------------------------------------------------

    if momentum_5m == "BULLISH":

        score += 15
        reasons.append("🟢 5M импульс BULLISH")

    elif momentum_5m == "BEARISH":

        score += 15
        reasons.append("🔴 5M импульс BEARISH")

    # -----------------------------------------------------
    # 4. RSI — максимум 15 баллов
    # -----------------------------------------------------

    if rsi_5m is not None:

        if 50 <= rsi_5m <= 70:

            score += 15
            reasons.append("📊 RSI подтверждает рост")

        elif 30 <= rsi_5m < 50:

            score += 15
            reasons.append("📊 RSI подтверждает снижение")

    # -----------------------------------------------------
    # 5. MACD — максимум 15 баллов
    # -----------------------------------------------------

    if macd_5m is not None:

        macd, signal, histogram = macd_5m

        if (
            macd > signal
            and histogram > 0
        ):

            score += 15
            reasons.append("📈 MACD BULLISH")

        elif (
            macd < signal
            and histogram < 0
        ):

            score += 15
            reasons.append("📉 MACD BEARISH")

    # -----------------------------------------------------
    # 6. СТАКАН — максимум 15 баллов
    # -----------------------------------------------------

    if order_book is not None:

        imbalance = order_book.get(
            "imbalance",
            0
        )

        if imbalance >= 1.5:

            score += 15
            reasons.append(
                "🟢 Стакан перевешивает BUY"
            )

        elif (
            imbalance > 0
            and imbalance <= 0.67
        ):

            score += 15
            reasons.append(
                "🔴 Стакан перевешивает SELL"
            )

    # -----------------------------------------------------
    # Итог
    # -----------------------------------------------------

    if score >= 85:

        grade = "🔥 VERY STRONG"

    elif score >= 75:

        grade = "🟢 STRONG"

    elif score >= 65:

        grade = "🟡 MODERATE"

    else:

        grade = "⚪ WEAK"

    return {
        "score": score,
        "grade": grade,
        "reasons": reasons
    }
    
# =========================================================
# ASTER PRO — ENTRY / STOP LOSS / TAKE PROFIT
# =========================================================

def calculate_trade_levels(
    candles,
    direction,
    atr
):

    if not candles or atr is None or atr <= 0:
        return None

    current_price = candles[-1]["close"]

    recent = candles[-20:]

    recent_high = max(
        c["high"]
        for c in recent
    )

    recent_low = min(
        c["low"]
        for c in recent
    )

    # -----------------------------------------------------
    # LONG
    # -----------------------------------------------------

    if direction == "LONG":

        entry = current_price

        structure_stop = (
            recent_low - atr * 0.30
        )

        atr_stop = (
            entry - atr * 1.20
        )

        stop_loss = min(
            structure_stop,
            atr_stop
        )

        risk = (
            entry - stop_loss
        )

        if risk <= 0:
            return None

        tp1 = (
            entry + risk * 1.5
        )

        tp2 = (
            entry + risk * 2.5
        )

        tp3 = (
            entry + risk * 3.5
        )

    # -----------------------------------------------------
    # SHORT
    # -----------------------------------------------------

    elif direction == "SHORT":

        entry = current_price

        structure_stop = (
            recent_high + atr * 0.30
        )

        atr_stop = (
            entry + atr * 1.20
        )

        stop_loss = max(
            structure_stop,
            atr_stop
        )

        risk = (
            stop_loss - entry
        )

        if risk <= 0:
            return None

        tp1 = (
            entry - risk * 1.5
        )

        tp2 = (
            entry - risk * 2.5
        )

        tp3 = (
            entry - risk * 3.5
        )

    else:

        return None

    rr_tp1 = 1.5
    rr_tp2 = 2.5
    rr_tp3 = 3.5

    risk_percent = (
        abs(
            entry - stop_loss
        )
        / entry
    ) * 100

    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_percent": risk_percent,
        "rr_tp1": rr_tp1,
        "rr_tp2": rr_tp2,
        "rr_tp3": rr_tp3
    }
