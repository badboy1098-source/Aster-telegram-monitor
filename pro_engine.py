import os
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
PRO_ALERT_COOLDOWN = 1800

pro_last_alerts = {}


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
# =========================================================
# ASTER PRO — ДОПОЛНИТЕЛЬНЫЕ ФИЛЬТРЫ
# =========================================================

def detect_support_resistance(candles, lookback=50):

    if len(candles) < lookback:
        return None, None

    recent = candles[-lookback:]

    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]

    resistance = max(highs)
    support = min(lows)

    return support, resistance


def detect_volume_spike(candles, period=20, multiplier=1.8):

    if len(candles) < period + 1:
        return False, 0

    volumes = [c["volume"] for c in candles[-period-1:-1]]

    average_volume = sum(volumes) / len(volumes)

    current_volume = candles[-1]["volume"]

    if average_volume <= 0:
        return False, 0

    ratio = current_volume / average_volume

    return ratio >= multiplier, ratio


def detect_candle_pattern(candles):

    if len(candles) < 2:
        return "NONE"

    current = candles[-1]
    previous = candles[-2]

    current_open = current["open"]
    current_close = current["close"]
    current_high = current["high"]
    current_low = current["low"]

    previous_open = previous["open"]
    previous_close = previous["close"]

    body = abs(current_close - current_open)
    candle_range = current_high - current_low

    if candle_range <= 0:
        return "NONE"

    upper_wick = current_high - max(current_open, current_close)
    lower_wick = min(current_open, current_close) - current_low

    # Bullish engulfing
    if (
        current_close > current_open
        and previous_close < previous_open
        and current_close >= previous_open
        and current_open <= previous_close
    ):
        return "BULLISH_ENGULFING"

    # Bearish engulfing
    if (
        current_close < current_open
        and previous_close > previous_open
        and current_open >= previous_close
        and current_close <= previous_open
    ):
        return "BEARISH_ENGULFING"

    # Bullish pin bar
    if (
        lower_wick > body * 2
        and lower_wick > upper_wick * 1.5
    ):
        return "BULLISH_PIN"

    # Bearish pin bar
    if (
        upper_wick > body * 2
        and upper_wick > lower_wick * 1.5
    ):
        return "BEARISH_PIN"

    return "NONE"


def detect_breakout(candles, lookback=20):

    if len(candles) < lookback + 2:
        return "NONE"

    previous = candles[-lookback-1:-1]

    resistance = max(c["high"] for c in previous)
    support = min(c["low"] for c in previous)

    current = candles[-1]

    if current["close"] > resistance:
        return "BREAKOUT"

    if current["close"] < support:
        return "BREAKDOWN"

    return "NONE"

def calculate_pro_score(
    trend_1h,
    structure_15m,
    momentum_5m,
    rsi_5m,
    macd_5m,
    order_book,
    direction
):

    score = 0
    reasons = []

    target_trend = (
        "BULLISH"
        if direction == "LONG"
        else "BEARISH"
    )

    # 1H TREND — 25 баллов
    if trend_1h == target_trend:
        score += 25
        reasons.append(
            f"1H тренд: {trend_1h}"
        )

    # 15M STRUCTURE — 15 баллов
    if structure_15m == target_trend:
        score += 15
        reasons.append(
            f"15M структура: {structure_15m}"
        )

    # 5M MOMENTUM — 15 баллов
    if momentum_5m == target_trend:
        score += 15
        reasons.append(
            f"5M импульс: {momentum_5m}"
        )

    # RSI — 15 баллов
    if rsi_5m is not None:

        if direction == "LONG" and 50 <= rsi_5m <= 70:
            score += 15
            reasons.append(
                f"RSI подтверждает LONG: {rsi_5m:.1f}"
            )

        elif direction == "SHORT" and 30 <= rsi_5m < 50:
            score += 15
            reasons.append(
                f"RSI подтверждает SHORT: {rsi_5m:.1f}"
            )

    # MACD — 15 баллов
    if macd_5m is not None:

        macd, signal, histogram = macd_5m

        if (
            direction == "LONG"
            and macd is not None
            and signal is not None
            and macd > signal
            and histogram > 0
        ):
            score += 15
            reasons.append(
                "MACD подтверждает LONG"
            )

        elif (
            direction == "SHORT"
            and macd is not None
            and signal is not None
            and macd < signal
            and histogram < 0
        ):
            score += 15
            reasons.append(
                "MACD подтверждает SHORT"
            )

    # ORDER BOOK — 15 баллов
    if order_book is not None:

        imbalance = order_book.get(
            "imbalance",
            0
        )

        if direction == "LONG" and imbalance >= 1.5:
            score += 15
            reasons.append(
                f"Стакан подтверждает LONG: {imbalance:.2f}"
            )

        elif direction == "SHORT" and imbalance <= 0.67:
            score += 15
            reasons.append(
                f"Стакан подтверждает SHORT: {imbalance:.2f}"
            )

    # GRADE
    if score >= 85:
        grade = "VERY STRONG"

    elif score >= 75:
        grade = "STRONG"

    elif score >= 65:
        grade = "MODERATE"

    else:
        grade = "WEAK"

    return score, grade, reasons
    
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

# =========================================================
# ASTER PRO — ПОЛНЫЙ АНАЛИЗ МОНЕТЫ
# =========================================================

def analyze_pro_symbol(symbol):

    timeframes = get_pro_timeframes(symbol)

    if not timeframes:
        return None

    candles_1h = timeframes.get("1h")
    candles_15m = timeframes.get("15m")
    candles_5m = timeframes.get("5m")
    candles_1m = timeframes.get("1m")

    if not candles_1h:
        return None

    if not candles_15m:
        return None

    if not candles_5m:
        return None

    if not candles_1m:
        return None

    # =====================================================
    # 1H — ГЛАВНЫЙ ТРЕНД
    # =====================================================

    closes_1h = [
        c["close"]
        for c in candles_1h
    ]

    ema20_1h = calculate_ema(
        closes_1h,
        20
    )

    ema50_1h = calculate_ema(
        closes_1h,
        50
    )

    ema200_1h = calculate_ema(
        closes_1h,
        200
    )

    if (
        ema20_1h is None
        or ema50_1h is None
        or ema200_1h is None
    ):
        return None

    price_1h = closes_1h[-1]

    if (
        price_1h > ema20_1h
        and ema20_1h > ema50_1h
        and ema50_1h > ema200_1h
    ):

        trend_1h = "BULLISH"

    elif (
        price_1h < ema20_1h
        and ema20_1h < ema50_1h
        and ema50_1h < ema200_1h
    ):

        trend_1h = "BEARISH"

    else:

        trend_1h = "RANGE"

    # =====================================================
    # 15M — СТРУКТУРА
    # =====================================================

    structure_data = analyze_market_structure(
        candles_15m
    )

    if not structure_data:
        return None

    structure_15m = structure_data["trend"]

    # =====================================================
    # 5M — MOMENTUM
    # =====================================================

    momentum_data = analyze_volume_momentum(
        candles_5m
    )

    if not momentum_data:
        return None

    momentum_5m = momentum_data["momentum"]

    # =====================================================
    # 5M — RSI
    # =====================================================

    closes_5m = [
        c["close"]
        for c in candles_5m
    ]

    rsi_5m = calculate_rsi(
        closes_5m
    )

    # =====================================================
    # 5M — MACD
    # =====================================================

    macd_5m = calculate_macd(
        closes_5m
    )

    # =====================================================
    # 5M — ATR
    # =====================================================

    atr_5m = calculate_atr(
        candles_5m
    )

    if atr_5m is None:
        return None

    # =====================================================
    # СТАКАН
    # =====================================================

    order_book = get_pro_order_book(
        symbol
    )

    if order_book is None:
        return None

    # =====================================================
    # ASTER PRO — ДОПОЛНИТЕЛЬНЫЕ ФИЛЬТРЫ
    # =====================================================

    support_5m, resistance_5m = detect_support_resistance(
        candles_5m
    )

    volume_spike, volume_ratio = detect_volume_spike(
        candles_5m
    )

    candle_pattern = detect_candle_pattern(
        candles_5m
    )

    breakout = detect_breakout(
        candles_5m
    )

    # =====================================================
    # НАПРАВЛЕНИЕ
    # =====================================================

    long_conditions = 0
    short_conditions = 0

    if trend_1h == "BULLISH":
        long_conditions += 1

    if trend_1h == "BEARISH":
        short_conditions += 1

    if structure_15m == "BULLISH":
        long_conditions += 1

    if structure_15m == "BEARISH":
        short_conditions += 1

    if momentum_5m == "BULLISH":
        long_conditions += 1

    if momentum_5m == "BEARISH":
        short_conditions += 1

    if (
        rsi_5m is not None
        and 50 <= rsi_5m <= 70
    ):
        long_conditions += 1

    if (
        rsi_5m is not None
        and 30 <= rsi_5m < 50
    ):
        short_conditions += 1

    if macd_5m[0] is not None:

        macd, signal, histogram = macd_5m

        if (
            macd > signal
            and histogram > 0
        ):
            long_conditions += 1

        if (
            macd < signal
            and histogram < 0
        ):
            short_conditions += 1

    imbalance = order_book.get(
        "imbalance",
        0
    )

    if imbalance >= 1.5:
        long_conditions += 1

    if (
        imbalance > 0
        and imbalance <= 0.67
    ):
        short_conditions += 1

    # =====================================================
    # ДОПОЛНИТЕЛЬНЫЕ УСЛОВИЯ PRO
    # =====================================================

    # Объём
    if volume_spike:

        if momentum_5m == "BULLISH":
            long_conditions += 1

        elif momentum_5m == "BEARISH":
            short_conditions += 1

    # Свечные паттерны
    if candle_pattern in (
        "BULLISH_ENGULFING",
        "BULLISH_PIN"
    ):
        long_conditions += 1

    if candle_pattern in (
        "BEARISH_ENGULFING",
        "BEARISH_PIN"
    ):
        short_conditions += 1

    # Пробой
    if breakout == "BREAKOUT":
        long_conditions += 1

    if breakout == "BREAKDOWN":
        short_conditions += 1

    # =====================================================
    # ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ
    # =====================================================

    if long_conditions >= 4 and (
        long_conditions > short_conditions
    ):

        direction = "LONG"

    elif short_conditions >= 4 and (
        short_conditions > long_conditions
    ):

        direction = "SHORT"

    else:

        direction = None

    if direction is None:
        return None

    # =====================================================
    # ФИЛЬТР SUPPORT / RESISTANCE
    # =====================================================

    current_price = candles_5m[-1]["close"]

    if (
        support_5m is None
        or resistance_5m is None
        or current_price <= 0
    ):
        return None

    resistance_distance = (
        (resistance_5m - current_price)
        / current_price
    ) * 100

    support_distance = (
        (current_price - support_5m)
        / current_price
    ) * 100

    # LONG не берём прямо под сопротивлением
    if direction == "LONG":

        if resistance_distance < 1.0:
            return None

    # SHORT не берём прямо над поддержкой
    if direction == "SHORT":

        if support_distance < 1.0:
            return None

    # =====================================================
    # SCORE
    # =====================================================

    score, grade, reasons = calculate_pro_score(
    trend_1h,
    structure_15m,
    momentum_5m,
    rsi_5m,
    macd_5m,
    order_book,
    direction
    )

    # =====================================================
    # ASTER PRO — ДОПОЛНИТЕЛЬНЫЕ БАЛЛЫ
    # =====================================================

    extra_score = 0

    # 📊 Всплеск объёма
    if volume_spike:
        extra_score += 5
        reasons.append(
            f"📊 Всплеск объёма x{volume_ratio:.1f}"
        )

    # 🕯 Свечной паттерн
    if direction == "LONG" and candle_pattern in (
        "BULLISH_ENGULFING",
        "BULLISH_PIN"
    ):
        extra_score += 5
        reasons.append(
            f"🕯 Бычий паттерн: {candle_pattern}"
        )

    if direction == "SHORT" and candle_pattern in (
        "BEARISH_ENGULFING",
        "BEARISH_PIN"
    ):
        extra_score += 5
        reasons.append(
            f"🕯 Медвежий паттерн: {candle_pattern}"
        )

    # 💥 Пробой
    if direction == "LONG" and breakout == "BREAKOUT":
        extra_score += 5
        reasons.append(
            "💥 Подтверждён пробой сопротивления"
        )

    if direction == "SHORT" and breakout == "BREAKDOWN":
        extra_score += 5
        reasons.append(
            "💥 Подтверждён пробой поддержки"
        )

    # 📍 Положение относительно уровней
    if direction == "LONG" and resistance_distance >= 2.0:
        extra_score += 5
        reasons.append(
            f"📍 До сопротивления: {resistance_distance:.2f}%"
        )

    if direction == "SHORT" and support_distance >= 2.0:
        extra_score += 5
        reasons.append(
            f"📍 До поддержки: {support_distance:.2f}%"
        )

    score = min(
        100,
        score + extra_score
    )

    # Обновляем оценку после дополнительных баллов
    if score >= 85:
        grade = "VERY STRONG"

    elif score >= 75:
        grade = "STRONG"

    elif score >= 65:
        grade = "MODERATE"

    else:
        grade = "WEAK"

    # =====================================================
    # ENTRY / SL / TP
    # =====================================================

    trade_levels = calculate_trade_levels(
        candles_5m,
        direction,
        atr_5m
    )

    if not trade_levels:
        return None

    return {
        "symbol": symbol,
        "direction": direction,

        "score": score,
        "grade": grade,
        "reasons": reasons,

        "trend_1h": trend_1h,
        "structure_15m": structure_15m,
        "momentum_5m": momentum_5m,

        "rsi_5m": rsi_5m,
        "macd_5m": macd_5m,
        "atr_5m": atr_5m,

        "order_book": order_book,

        "entry": trade_levels["entry"],
        "stop_loss": trade_levels["stop_loss"],
        "tp1": trade_levels["tp1"],
        "tp2": trade_levels["tp2"],
        "tp3": trade_levels["tp3"],

        "risk_percent": trade_levels[
            "risk_percent"
        ],

        "rr_tp1": trade_levels["rr_tp1"],
        "rr_tp2": trade_levels["rr_tp2"],
        "rr_tp3": trade_levels["rr_tp3"],
        "volume_spike": volume_spike,
        "volume_ratio": volume_ratio,

        "candle_pattern": candle_pattern,
        "breakout": breakout,

        "support_5m": support_5m,
        "resistance_5m": resistance_5m,

        "support_distance": support_distance,
        "resistance_distance": resistance_distance
    }

# =========================================================
# ASTER PRO — 1M ПОДТВЕРЖДЕНИЕ ВХОДА
# =========================================================

def confirm_1m_entry(
    candles,
    direction
):

    if len(candles) < 20:
        return None

    recent = candles[-5:]

    green = 0
    red = 0

    for candle in recent:

        if candle["close"] > candle["open"]:
            green += 1

        elif candle["close"] < candle["open"]:
            red += 1

    current = candles[-1]

    candle_range = (
        current["high"]
        - current["low"]
    )

    if candle_range <= 0:
        return False

    body = abs(
        current["close"]
        - current["open"]
    )

    body_ratio = (
        body / candle_range
    )

    if direction == "LONG":

        confirmation = (
            current["close"]
            > current["open"]
            and green >= 3
            and body_ratio >= 0.45
        )

    elif direction == "SHORT":

        confirmation = (
            current["close"]
            < current["open"]
            and red >= 3
            and body_ratio >= 0.45
        )

    else:

        confirmation = False

    return confirmation

# =========================================================
# ASTER PRO — ФИНАЛЬНЫЙ ФИЛЬТР
# =========================================================

def is_valid_pro_setup(
    analysis,
    entry_confirmation
):

    if not analysis:
        return False

    score = analysis.get(
        "score",
        0
    )

    direction = analysis.get(
        "direction"
    )

    if direction not in (
        "LONG",
        "SHORT"
    ):
        return False

    # Только сильные сетапы

    if score < 75:
        return False

    # Обязательное подтверждение 1M

    if not entry_confirmation:
        return False

    # Минимальный R/R до TP1

    rr = analysis.get(
        "rr_tp1",
        0
    )

    if rr < 1.5:
        return False

    return True

# =========================================================
# ASTER PRO — СКАНЕР ВСЕХ МОНЕТ
# =========================================================

def scan_pro_market():

    print("")
    print("==============================")
    print("🧠 ASTER PRO — СКАНИРОВАНИЕ")
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
        return []

    setups = []

    for symbol, volume in symbols:

        try:

            analysis = analyze_pro_symbol(
                symbol
            )

            if not analysis:
                continue

            direction = analysis[
                "direction"
            ]

            candles_1m = get_pro_klines(
                symbol,
                "1m",
                50
            )

            candles_1m = prepare_candles(
                candles_1m
            )

            if not candles_1m:
                continue

            entry_confirmation = (
                confirm_1m_entry(
                    candles_1m,
                    direction
                )
            )

            if not is_valid_pro_setup(
                analysis,
                entry_confirmation
            ):
                continue

            analysis["volume_24h"] = volume

            analysis[
                "entry_confirmation"
            ] = entry_confirmation

            setups.append(
                analysis
            )

            print(
                f"🔥 PRO SETUP: "
                f"{symbol} "
                f"{direction} "
                f"Score={analysis['score']}"
            )

        except Exception as e:

            print(
                f"❌ PRO {symbol}:",
                e
            )

    # =====================================================
    # СОРТИРОВКА ПО SCORE
    # =====================================================

    setups.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    print(
        f"✅ Найдено PRO сетапов: "
        f"{len(setups)}"
    )

    return setups

# =========================================================
# ASTER PRO — ЗАЩИТА ОТ ПОВТОРНЫХ СИГНАЛОВ
# =========================================================

def is_pro_cooldown_active(
    symbol,
    direction
):

    key = (
        f"{symbol}_{direction}"
    )

    last_time = pro_last_alerts.get(
        key
    )

    if last_time is None:
        return False

    elapsed = (
        time.time()
        - last_time
    )

    if elapsed < PRO_ALERT_COOLDOWN:

        return True

    return False


def mark_pro_alert(
    symbol,
    direction
):

    key = (
        f"{symbol}_{direction}"
    )

    pro_last_alerts[key] = (
        time.time()
    )

# =========================================================
# ASTER PRO — ФОРМИРОВАНИЕ TELEGRAM СООБЩЕНИЯ
# =========================================================

def format_pro_signal(analysis):

    symbol = analysis["symbol"]
    direction = analysis["direction"]

    score = analysis["score"]
    grade = analysis["grade"]

    entry = analysis["entry"]
    stop_loss = analysis["stop_loss"]

    tp1 = analysis["tp1"]
    tp2 = analysis["tp2"]
    tp3 = analysis["tp3"]

    risk_percent = analysis[
        "risk_percent"
    ]

    trend_1h = analysis[
        "trend_1h"
    ]

    structure_15m = analysis[
        "structure_15m"
    ]

    momentum_5m = analysis[
        "momentum_5m"
    ]

    rsi_5m = analysis[
        "rsi_5m"
    ]

    order_book = analysis[
        "order_book"
    ]

    buy_total = order_book[
        "buy_total"
    ]

    sell_total = order_book[
        "sell_total"
    ]

    imbalance = order_book[
        "imbalance"
    ]

    rr1 = analysis[
        "rr_tp1"
    ]

    rr2 = analysis[
        "rr_tp2"
    ]

    rr3 = analysis[
        "rr_tp3"
    ]

    if direction == "LONG":

        direction_text = "🟢 LONG"

    else:

        direction_text = "🔴 SHORT"

    message = (

        "🧠 ASTER PRO\n\n"

        f"{direction_text} — "
        f"{symbol}\n\n"

        f"🔥 Score: {score}/100\n"
        f"{grade}\n\n"

        "━━━━━━━━━━━━━━\n\n"

        f"💲 Entry: {entry:.8g}\n"
        f"🛑 Stop Loss: {stop_loss:.8g}\n\n"

        f"🎯 TP1: {tp1:.8g} "
        f"(R/R 1:{rr1})\n"

        f"🎯 TP2: {tp2:.8g} "
        f"(R/R 1:{rr2})\n"

        f"🎯 TP3: {tp3:.8g} "
        f"(R/R 1:{rr3})\n\n"

        f"📉 Риск до SL: "
        f"{risk_percent:.2f}%\n\n"

        "━━━━━━━━━━━━━━\n\n"

        f"📈 1H: {trend_1h}\n"
        f"📊 15M: {structure_15m}\n"
        f"⚡ 5M: {momentum_5m}\n"
        f"🎯 1M: CONFIRMED\n\n"

        "━━━━━━━━━━━━━━\n\n"

        f"💚 BUY стакан: "
        f"${buy_total:,.0f}\n"

        f"❤️ SELL стакан: "
        f"${sell_total:,.0f}\n"

        f"⚖️ Imbalance: "
        f"{imbalance:.2f}\n\n"

        f"📊 RSI 5M: "
        f"{rsi_5m:.1f}\n\n"
        
        "━━━━━━━━━━━━━━\n\n"

        f"📊 Объём: "
        f"x{analysis['volume_ratio']:.1f}\n"

        f"🕯 Паттерн: "
        f"{analysis['candle_pattern']}\n"

        f"💥 Пробой: "
        f"{analysis['breakout']}\n\n"

        f"🟢 Support: "
        f"{analysis['support_5m']:.6f}\n"

        f"🔴 Resistance: "
        f"{analysis['resistance_5m']:.6f}\n\n"

        f"📏 До Support: "
        f"{analysis['support_distance']:.2f}%\n"

        f"📏 До Resistance: "
        f"{analysis['resistance_distance']:.2f}%\n\n"

        "━━━━━━━━━━━━━━\n\n"

        "⚠️ ASTER PRO — "
        "информационный сигнал.\n"
        "Сделка автоматически НЕ открывается."
    )

    return message

# =========================================================
# ASTER PRO — ПОЛУЧЕНИЕ ПОДПИСЧИКОВ
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


def get_pro_subscribers():

    if not SUPABASE_URL or not SUPABASE_SECRET:

        print(
            "❌ ASTER PRO: "
            "SUPABASE настройки не найдены"
        )

        return []

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/subscribers?select=chat_id"
    )

    headers = {
        "apikey": SUPABASE_SECRET,
        "Authorization": (
            f"Bearer {SUPABASE_SECRET}"
        )
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return [
            str(item["chat_id"])
            for item in data
            if item.get("chat_id")
        ]

    except Exception as e:

        print(
            "❌ ASTER PRO: "
            "ошибка получения подписчиков:",
            e
        )

        return []


# =========================================================
# ASTER PRO — ОТПРАВКА В TELEGRAM
# =========================================================

def send_pro_telegram_message(
    message
):

    if not TELEGRAM_TOKEN:

        print(
            "❌ ASTER PRO: "
            "TELEGRAM_TOKEN не найден"
        )

        return False

    subscribers = get_pro_subscribers()

    if not subscribers:

        print(
            "⚪ ASTER PRO: "
            "подписчиков нет"
        )

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    success = False

    for chat_id in subscribers:

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message
                },
                timeout=10
            )

            response.raise_for_status()

            success = True

        except Exception as e:

            print(
                f"❌ ASTER PRO Telegram "
                f"{chat_id}:",
                e
            )

    return success

# =========================================================
# ASTER PRO — ЗАПУСК ОДНОГО СКАНИРОВАНИЯ
# =========================================================

def run_pro_scan():

    print("")
    print("==============================")
    print("🧠 ASTER PRO — НОВЫЙ СКАН")
    print("==============================")

    setups = scan_pro_market()

    if not setups:

        print(
            "⚪ ASTER PRO: "
            "сильных сетапов нет"
        )

        return

    # Берём только лучшие сетапы
    # чтобы не отправлять много сигналов

    setups = setups[:3]

    for analysis in setups:

        symbol = analysis[
            "symbol"
        ]

        direction = analysis[
            "direction"
        ]

        if is_pro_cooldown_active(
            symbol,
            direction
        ):

            print(
                f"⏳ ASTER PRO: "
                f"{symbol} {direction} "
                f"ещё на cooldown"
            )

            continue

        message = format_pro_signal(
            analysis
        )

        sent = send_pro_telegram_message(
            message
        )

        if sent:

            mark_pro_alert(
                symbol,
                direction
            )

            print(
                f"📨 ASTER PRO: "
                f"{symbol} {direction} "
                f"отправлен"
            )

# =========================================================
# ASTER PRO — ТЕСТ TELEGRAM
# =========================================================

def test_pro_telegram():

    print("")
    print("==============================")
    print("📨 ASTER PRO — TELEGRAM TEST")
    print("==============================")

    message = (
        "🧠 ASTER PRO\n\n"
        "✅ Telegram подключён!\n\n"
        "PRO-модуль готов отправлять "
        "торговые сетапы.\n\n"
        "⚠️ Сделки автоматически не открываются."
    )

    return send_pro_telegram_message(
        message
    )


if __name__ == "__main__":
    run_pro_scan()
