import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================
# НАСТРОЙКИ
# =========================

ASTER_BASE = "https://fapi.asterdex.com"

ORDER_THRESHOLD = 15000
MIN_VOLUME = 15000

SCAN_INTERVAL = 30
ALERT_COOLDOWN = 300

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# BTC и ETH полностью исключаем
EXCLUDED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT"
}

last_alerts = {}


# =========================
# TELEGRAM
# =========================

def send_telegram(message):

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram не настроен")
        print(message)
        return

    try:

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=10
        )

        if not response.ok:
            print("Ошибка Telegram:", response.text)

    except Exception as e:
        print("Ошибка отправки Telegram:", e)


# =========================
# ПОЛУЧАЕМ МОНЕТЫ
# =========================

def get_symbols():

    try:

        url = f"{ASTER_BASE}/fapi/v1/ticker/24hr"

        response = requests.get(
            url,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        coins = []

        for item in data:

            symbol = item.get("symbol", "")

            if not symbol.endswith("USDT"):
                continue

            if symbol in EXCLUDED_SYMBOLS:
                continue

            try:
                volume = float(item.get("quoteVolume", 0))
            except:
                volume = 0

            if volume < MIN_VOLUME:
                continue

            coins.append({
                "symbol": symbol,
                "volume": volume
            })

        # Сначала самые ликвидные
        coins.sort(
            key=lambda x: x["volume"],
            reverse=True
        )

        symbols = [
    coin["symbol"]
    for coin in coins
        ]

        print(
            f"✅ Монет для проверки: {len(symbols)}"
        )

        return symbols

    except Exception as e:

        print(
            "❌ Ошибка получения списка монет:",
            e
        )

        return []


# =========================
# 1M СВЕЧИ
# =========================

def get_1m_change(symbol):

    try:

        url = f"{ASTER_BASE}/fapi/v1/klines"

        params = {
            "symbol": symbol,
            "interval": "1m",
            "limit": 2
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        klines = response.json()

        if not klines or len(klines) < 2:
            return None, None

        # Текущая свеча
        current = klines[-1]

        # Предыдущая закрытая свеча
        closed = klines[-2]

        current_open = float(current[1])
        current_close = float(current[4])

        closed_open = float(closed[1])
        closed_close = float(closed[4])

        if current_open == 0 or closed_open == 0:
            return None, None

        change_current = (
            (current_close - current_open)
            / current_open
        ) * 100

        change_closed = (
            (closed_close - closed_open)
            / closed_open
        ) * 100

        return change_current, change_closed

    except Exception as e:

        print(
            f"Ошибка 1M {symbol}:",
            e
        )

        return None, None
# =========================
# 🔎 ПРЕДСИГНАЛ — АНАЛИЗ 1 ЧАСА
# =========================

def get_pre_signal(symbol):

    try:

        url = f"{ASTER_BASE}/fapi/v1/klines"

        params = {
            "symbol": symbol,
            "interval": "1m",
            "limit": 61
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        klines = response.json()

        if not klines or len(klines) < 61:
            return None

        # Берём 60 последних закрытых свечей
        candles = klines[-61:-1]

        changes = []
        volumes = []

        for candle in candles:

            open_price = float(candle[1])
            close_price = float(candle[4])
            volume = float(candle[5])

            if open_price == 0:
                return None

            change = (
                (close_price - open_price)
                / open_price
            ) * 100

            changes.append(change)
            volumes.append(volume)

        # =========================
        # ОБЩЕЕ ДВИЖЕНИЕ ЗА ЧАС
        # =========================

        first_open = float(candles[0][1])
        last_close = float(candles[-1][4])

        if first_open == 0:
            return None

        hour_change = (
            (last_close - first_open)
            / first_open
        ) * 100

        # =========================
        # ПОСЛЕДНИЕ 15 МИНУТ
        # =========================

        last_15 = changes[-15:]

        last_15_change = sum(last_15)

        # =========================
        # ПРЕДЫДУЩИЕ 15 МИНУТ
        # =========================

        previous_15 = changes[-30:-15]

        previous_15_change = sum(previous_15)

        # =========================
        # УСКОРЕНИЕ
        # =========================

        acceleration_up = (
            last_15_change > previous_15_change
        )

        acceleration_down = (
            last_15_change < previous_15_change
        )

        # =========================
        # ОБЪЁМ
        # =========================

        previous_volume = sum(volumes[-30:-15])
        last_volume = sum(volumes[-15:])

        volume_rising = (
            last_volume > previous_volume * 1.10
        )

        # =========================
        # КОЛИЧЕСТВО ЗЕЛЁНЫХ / КРАСНЫХ
        # =========================

        green_count = sum(
            1 for change in last_15
            if change > 0
        )

        red_count = sum(
            1 for change in last_15
            if change < 0
        )

        # =========================
        # 🔎 ПРЕДСИГНАЛ BUY
        # =========================

        if (
            hour_change > 0.5
            and last_15_change > 0.5
            and acceleration_up
            and volume_rising
            and green_count >= 9
        ):

            return {
                "symbol": symbol,
                "direction": "🔎 ВОЗМОЖНЫЙ BUY",
                "hour_change": hour_change,
                "last_15_change": last_15_change,
                "price": last_close,
                "key": f"{symbol}:PRE_BUY"
            }

        # =========================
        # 🔎 ПРЕДСИГНАЛ SELL
        # =========================

        if (
            hour_change < -0.5
            and last_15_change < -0.5
            and acceleration_down
            and volume_rising
            and red_count >= 9
        ):

            return {
                "symbol": symbol,
                "direction": "🔎 ВОЗМОЖНЫЙ SELL",
                "hour_change": hour_change,
                "last_15_change": last_15_change,
                "price": last_close,
                "key": f"{symbol}:PRE_SELL"
            }

        return None

    except Exception as e:

        print(
            f"Ошибка предсигнала {symbol}:",
            e
        )

        return None


# =========================
# 📩 ОТПРАВКА ПРЕДСИГНАЛА
# =========================

def send_pre_signal(result):

    if not result:
        return

    key = result["key"]

    now = time.time()

    # Не отправляем один и тот же предсигнал
    # чаще одного раза в 5 минут
    if key in last_alerts:

        if now - last_alerts[key] < ALERT_COOLDOWN:
            return

    last_alerts[key] = now

    message = (
        f"🔎 ПРЕДСИГНАЛ Aster DEX\n\n"
        f"💲 {result['symbol']}\n"
        f"📌 {result['direction']}\n\n"
        f"📊 Изменение за 1 час: "
        f"{result['hour_change']:+.2f}%\n"
        f"⚡ Последние 15 минут: "
        f"{result['last_15_change']:+.2f}%\n"
        f"💵 Текущая цена: "
        f"{result['price']:.8f}\n\n"
        f"⚠️ Движение только формируется\n"
        f"Ожидается подтверждение"
    )

    print(message)

    send_telegram(message)

# =========================
# СТАКАН
# =========================

def get_order_book(symbol):

    try:

        url = f"{ASTER_BASE}/fapi/v1/depth"

        params = {
            "symbol": symbol,
            "limit": 20
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        buy_total = 0
        sell_total = 0

        # Лучшая цена BUY
        best_bid = None

        # Лучшая цена SELL
        best_ask = None

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        if bids:
            best_bid = float(bids[0][0])

        if asks:
            best_ask = float(asks[0][0])

        # BUY
        for price, qty in bids:

            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                buy_total += value

        # SELL
        for price, qty in asks:

            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                sell_total += value

        return (
            buy_total,
            sell_total,
            best_bid,
            best_ask
        )

    except Exception as e:

        print(
            f"Ошибка стакана {symbol}:",
            e
        )

        return 0, 0, None, None


def check_symbol(symbol):

    if symbol in EXCLUDED_SYMBOLS:
        return None

    change_current, change_closed = get_1m_change(symbol)

    if change_current is None:
        return None

    # =========================
    # СИЛЬНОЕ ДВИЖЕНИЕ ±3%
    # =========================

    strong_rise = (
        change_current >= 3
        or change_closed >= 3
    )

    strong_fall = (
        change_current <= -3
        or change_closed <= -3
    )

    # =========================
    # ДВИЖЕНИЕ ДЛЯ НАБЛЮДЕНИЯ ±2%
    # =========================

    watch_rise = (
        change_current >= 2
        or change_closed >= 2
    )

    watch_fall = (
        change_current <= -2
        or change_closed <= -2
    )

    # Если движение меньше ±2% —
    # монету вообще не проверяем
    if not watch_rise and not watch_fall:
        return None

    buy_total, sell_total, best_bid, best_ask = get_order_book(symbol)

    # =========================
    # 🚨 СИЛЬНЫЙ BUY
    # =========================

    if (
        strong_rise
        and buy_total >= ORDER_THRESHOLD
        and buy_total > sell_total
    ):
        return {
            "symbol": symbol,
            "signal": "🚀 СИЛЬНЫЙ BUY",
            "change_current": change_current,
            "change_closed": change_closed,
            "buy": buy_total,
            "sell": sell_total,
            "entry": best_ask,
"stop": best_ask * 0.99 if best_ask else None,
"tp1": best_ask * 1.015 if best_ask else None,
"tp2": best_ask * 1.025 if best_ask else None,
            "key": f"{symbol}:STRONG_BUY"
        }

    # =========================
    # 🚨 СИЛЬНЫЙ SELL
    # =========================

    if (
        strong_fall
        and sell_total >= ORDER_THRESHOLD
        and sell_total > buy_total
    ):
        return {
            "symbol": symbol,
            "signal": "🚨 СИЛЬНЫЙ SELL",
            "change_current": change_current,
            "change_closed": change_closed,
            "buy": buy_total,
            "sell": sell_total,
            "entry": best_bid,
"stop": best_bid * 1.01 if best_bid else None,
"tp1": best_bid * 0.985 if best_bid else None,
"tp2": best_bid * 0.975 if best_bid else None,
            "key": f"{symbol}:STRONG_SELL"
        }

    # =========================
    # 👀 НАБЛЮДЕНИЕ BUY
    # =========================

    if (
        watch_rise
        and buy_total >= 10000
        and buy_total > sell_total
    ):
        return {
            "symbol": symbol,
            "signal": "👀 НАБЛЮДЕНИЕ BUY",
            "change_current": change_current,
            "change_closed": change_closed,
            "buy": buy_total,
            "sell": sell_total,
            "key": f"{symbol}:WATCH_BUY"
        }

    # =========================
    # 👀 НАБЛЮДЕНИЕ SELL
    # =========================

    if (
        watch_fall
        and sell_total >= 10000
        and sell_total > buy_total
    ):
        return {
            "symbol": symbol,
            "signal": "👀 НАБЛЮДЕНИЕ SELL",
            "change_current": change_current,
            "change_closed": change_closed,
            "buy": buy_total,
            "sell": sell_total,
            "key": f"{symbol}:WATCH_SELL"
        }

    return None


# =========================
# ОТПРАВКА СИГНАЛА
# =========================

def send_signal(result):

    if not result:
        return

    key = result["key"]

    now = time.time()

    # Не отправляем тот же сигнал чаще 1 раза в 5 минут
    if key in last_alerts:

        if now - last_alerts[key] < ALERT_COOLDOWN:
            return

    last_alerts[key] = now

    symbol = result["symbol"]

    levels = ""

    if (
        result["signal"] == "🚀 СИЛЬНЫЙ BUY"
        and result.get("entry")
    ):
        levels = (
            f"\n\n🎯 ТОЧКА ВХОДА\n"
            f"💵 Вход: {result['entry']:.8f}\n"
            f"🛑 Stop Loss: {result['stop']:.8f}\n"
            f"🎯 TP1: {result['tp1']:.8f}\n"
            f"🎯 TP2: {result['tp2']:.8f}"
        )

    elif (
        result["signal"] == "🚨 СИЛЬНЫЙ SELL"
        and result.get("entry")
    ):
        levels = (
            f"\n\n🎯 ТОЧКА ВХОДА\n"
            f"💵 Вход: {result['entry']:.8f}\n"
            f"🛑 Stop Loss: {result['stop']:.8f}\n"
            f"🎯 TP1: {result['tp1']:.8f}\n"
            f"🎯 TP2: {result['tp2']:.8f}"
        )

    message = (
        f"🚨 СИГНАЛ Aster DEX\n\n"
        f"💲 {symbol}\n"
        f"📌 Сигнал: {result['signal']}\n\n"
        f"📈 1M текущая: "
        f"{result['change_current']:+.2f}%\n"
        f"🕐 1M закрытая: "
        f"{result['change_closed']:+.2f}%\n\n"
        f"🟢 BUY ≥ $15k: "
        f"${result['buy']:,.0f}\n"
        f"🔴 SELL ≥ $15k: "
        f"${result['sell']:,.0f}"
        f"{levels}"
    )

    print(message)

    send_telegram(message)


# =========================
# ОДИН ЦИКЛ СКАНИРОВАНИЯ
# =========================

def scan():

    print("\n==============================")
    print("🔥 Aster DEX — новый скан")
    print("==============================")

    symbols = get_symbols()

    if not symbols:
        return

    results = []
        pre_results = []

    # Проверяем монеты параллельно,
    # чтобы не ждать каждую по очереди
    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        futures = {
            executor.submit(
                check_symbol,
                symbol
            ): symbol
            for symbol in symbols
        }

        for future in as_completed(futures):

            symbol = futures[future]

            try:

                result = future.result()

                if result:
                    results.append(result)
                                    # =========================
                # 🔎 ОТДЕЛЬНЫЙ ПРЕДСИГНАЛ
                # =========================

                try:

                    pre_result = get_pre_signal(symbol)

                    if pre_result:
                        pre_results.append(pre_result)

                except Exception as e:

                    print(
                        f"Ошибка предсигнала {symbol}:",
                        e
                    )

            except Exception as e:

                print(
                    f"Ошибка проверки {symbol}:",
                    e
                )

    # Сначала выводим найденные сигналы
    if results:

        print(
            f"\n🚨 Найдено сигналов: "
            f"{len(results)}"
        )

        for result in results:
            send_signal(result)

    else:

        print(
            "⚪ Подходящих сигналов нет"
        )


# =========================
# ЗАПУСК
# =========================

print("🚀 Aster Monitor запущен")
print("🚫 BTCUSDT и ETHUSDT исключены")
print("📊 Порог движения: ±3% за 1M")
print("💰 Порог стакана: $15,000")
print("⏱ Интервал сканирования: 30 секунд")

while True:

    try:

        scan()

    except Exception as e:

        print(
            "❌ Ошибка основного цикла:",
            e
        )

    print(
        f"\n🔄 Следующий скан через "
        f"{SCAN_INTERVAL} секунд..."
    )

    time.sleep(SCAN_INTERVAL)
