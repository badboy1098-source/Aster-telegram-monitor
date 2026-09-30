import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================
# НАСТРОЙКИ
# =========================

ASTER_BASE = "https://fapi.asterdex.com"

ORDER_THRESHOLD = 15000
MIN_VOLUME = 50000
MAX_SYMBOLS = 90

SCAN_INTERVAL = 30
ALERT_COOLDOWN = 60

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
            for coin in coins[:MAX_SYMBOLS]
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

        # BUY
        for price, qty in data.get("bids", []):

            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                buy_total += value

        # SELL
        for price, qty in data.get("asks", []):

            value = float(price) * float(qty)

            if value >= ORDER_THRESHOLD:
                sell_total += value

        return buy_total, sell_total

    except Exception as e:

        print(
            f"Ошибка стакана {symbol}:",
            e
        )

        return 0, 0


# =========================
# ПРОВЕРКА ОДНОЙ МОНЕТЫ
# =========================

def check_symbol(symbol):

    if symbol in EXCLUDED_SYMBOLS:
        return None

    change_current, change_closed = get_1m_change(symbol)

    if change_current is None:
        return None

    # Сильный рост:
    # текущая ИЛИ закрытая 1M свеча >= +3%
    strong_rise = (
        change_current >= 3
        or change_closed >= 3
    )

    # Сильное падение:
    # текущая ИЛИ закрытая 1M свеча <= -3%
    strong_fall = (
        change_current <= -3
        or change_closed <= -3
    )

    # Если движения нет — стакан вообще не проверяем
    if not strong_rise and not strong_fall:
        return None

    buy_total, sell_total = get_order_book(symbol)

    # =========================
    # BUY
    # =========================

    if (
        strong_rise
        and buy_total >= ORDER_THRESHOLD
        and buy_total > sell_total
    ):

        signal = "🟢 BUY"

        key = f"{symbol}:BUY"

        return {
            "symbol": symbol,
            "signal": signal,
            "change_current": change_current,
            "change_closed": change_closed,
            "buy": buy_total,
            "sell": sell_total,
            "key": key
        }

    # =========================
    # SELL
    # =========================

    if (
        strong_fall
        and sell_total >= ORDER_THRESHOLD
        and sell_total > buy_total
    ):

        signal = "🔴 SELL"

        key = f"{symbol}:SELL"

        return {
            "symbol": symbol,
            "signal": signal,
            "change_current": change_current,
            "change_closed": change_closed,
            "buy": buy_total,
            "sell": sell_total,
            "key": key
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

    # Не отправляем тот же сигнал чаще 1 раза в минуту
    if key in last_alerts:

        if now - last_alerts[key] < ALERT_COOLDOWN:
            return

    last_alerts[key] = now

    symbol = result["symbol"]

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
