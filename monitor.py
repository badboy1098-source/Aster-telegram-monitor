import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
# =========================================================
# SUPABASE — ПОДПИСЧИКИ TELEGRAM
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET = os.getenv("SUPABASE_SECRET")


def get_subscribers():

    if not SUPABASE_URL or not SUPABASE_SECRET:
        print("❌ SUPABASE настройки не найдены")
        return []

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/subscribers"
        f"?select=chat_id"
    )

    headers = {
        "apikey": SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}"
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
            "❌ Ошибка получения подписчиков:",
            e
        )

        return []


def add_subscriber(chat_id):

    if not SUPABASE_URL or not SUPABASE_SECRET:
        print("❌ SUPABASE настройки не найдены")
        return False

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/subscribers"
    )

    headers = {
        "apikey": SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    data = {
        "chat_id": str(chat_id)
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=10
        )

        response.raise_for_status()

        return True

    except Exception as e:

        print(
            "❌ Ошибка добавления подписчика:",
            e
        )

        return False


# =========================================================
# НАСТРОЙКИ
# =========================================================

ASTER_BASE = "https://fapi.asterdex.com"

ORDER_THRESHOLD = 15000
MIN_VOLUME = 15000

SCAN_INTERVAL = 30
ALERT_COOLDOWN = 300

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

EXCLUDED_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT"
}

last_alerts = {}


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(message):

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_TOKEN или CHAT_ID не найдены")
        return

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:

        response = requests.post(
            url,
            data=data,
            timeout=10
        )

        response.raise_for_status()

    except Exception as e:

        print(
            "❌ Ошибка Telegram:",
            e
        )


# =========================================================
# СТАКАН
# =========================================================

def get_order_book(symbol):

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

        buy_total = sum(
            float(price) * float(quantity)
            for price, quantity in bids
        )

        sell_total = sum(
            float(price) * float(quantity)
            for price, quantity in asks
        )

        best_bid = None
        best_ask = None

        if bids:
            best_bid = float(bids[0][0])

        if asks:
            best_ask = float(asks[0][0])

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

        return (
            0,
            0,
            None,
            None
        )


# =========================================================
# ПРОВЕРКА ОСНОВНОГО СИГНАЛА
# =========================================================

def check_symbol(symbol, volume):

    try:

        url = f"{ASTER_BASE}/fapi/v1/klines"

        params = {
            "symbol": symbol,
            "interval": "1m",
            "limit": 3
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        klines = response.json()

        if not klines or len(klines) < 2:
            return None

        # Последняя свеча может быть текущей
        current_candle = klines[-1]

        # Предыдущая свеча уже закрыта
        closed_candle = klines[-2]

        current_open = float(
            current_candle[1]
        )

        current_close = float(
            current_candle[4]
        )

        closed_open = float(
            closed_candle[1]
        )

        closed_close = float(
            closed_candle[4]
        )

        if current_open == 0 or closed_open == 0:
            return None

        change_current = (
            (current_close - current_open)
            / current_open
        ) * 100

        change_closed = (
            (closed_close - closed_open)
            / closed_open
        ) * 100

        # =================================================
        # СИЛЬНОЕ ДВИЖЕНИЕ
        # =================================================

        strong_rise = (
            change_current >= 3
            or
            change_closed >= 3
        )

        strong_fall = (
            change_current <= -3
            or
            change_closed <= -3
        )

        # Если нет сильного движения —
        # стакан пока не проверяем
        if not strong_rise and not strong_fall:
            return None

        # =================================================
        # СТАКАН
        # =================================================

        (
            buy_total,
            sell_total,
            best_bid,
            best_ask
        ) = get_order_book(symbol)

        signal = None

        entry = None
        stop = None
        tp1 = None
        tp2 = None

        # =================================================
        # СИЛЬНЫЙ BUY
        # =================================================

        if (
            strong_rise
            and buy_total >= ORDER_THRESHOLD
            and buy_total > sell_total
        ):

            signal = "🚀 СИЛЬНЫЙ BUY"

            if best_ask:
                entry = best_ask
                stop = entry * 0.99
                tp1 = entry * 1.015
                tp2 = entry * 1.025

        # =================================================
        # СИЛЬНЫЙ SELL
        # =================================================

        elif (
            strong_fall
            and sell_total >= ORDER_THRESHOLD
            and sell_total > buy_total
        ):

            signal = "🚨 СИЛЬНЫЙ SELL"

            if best_bid:
                entry = best_bid
                stop = entry * 1.01
                tp1 = entry * 0.985
                tp2 = entry * 0.975

        if not signal:
            return None

        return {
            "symbol": symbol,
            "signal": signal,

            "change_current": change_current,
            "change_closed": change_closed,

            "buy": buy_total,
            "sell": sell_total,

            "entry": entry,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,

            "key": f"{symbol}:{signal}"
        }

    except Exception as e:

        print(
            f"Ошибка проверки {symbol}:",
            e
        )

        return None


# =========================================================
# ОТПРАВКА ОСНОВНОГО СИГНАЛА
# =========================================================

def send_signal(result):

    if not result:
        return

    key = result["key"]

    now = time.time()

    # Не отправляем тот же сигнал
    # чаще одного раза в 5 минут
    if key in last_alerts:

        if now - last_alerts[key] < ALERT_COOLDOWN:
            return

    last_alerts[key] = now

    levels = ""

    if (
        result["signal"] == "🚀 СИЛЬНЫЙ BUY"
        and result.get("entry")
    ):

        levels = (
            "\n\n"
            "🎯 ТОЧКА ВХОДА\n"
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
            "\n\n"
            "🎯 ТОЧКА ВХОДА\n"
            f"💵 Вход: {result['entry']:.8f}\n"
            f"🛑 Stop Loss: {result['stop']:.8f}\n"
            f"🎯 TP1: {result['tp1']:.8f}\n"
            f"🎯 TP2: {result['tp2']:.8f}"
        )

    message = (
        "🚨 СИГНАЛ Aster DEX\n\n"

        f"💲 {result['symbol']}\n"
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


# =========================================================
# 🔎 ПРЕДСИГНАЛ — АНАЛИЗ 1 ЧАСА
# =========================================================

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

        # Берём 60 полностью закрытых минут
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

        # =================================================
        # ДВИЖЕНИЕ ЗА ЧАС
        # =================================================

        first_open = float(
            candles[0][1]
        )

        last_close = float(
            candles[-1][4]
        )

        if first_open == 0:
            return None

        hour_change = (
            (last_close - first_open)
            / first_open
        ) * 100

        # =================================================
        # ПОСЛЕДНИЕ 15 МИНУТ
        # =================================================

        last_15 = changes[-15:]

        last_15_change = sum(last_15)

        # =================================================
        # ПРЕДЫДУЩИЕ 15 МИНУТ
        # =================================================

        previous_15 = changes[-30:-15]

        previous_15_change = sum(
            previous_15
        )

        # =================================================
        # УСКОРЕНИЕ
        # =================================================

        acceleration_up = (
            last_15_change
            >
            previous_15_change
        )

        acceleration_down = (
            last_15_change
            <
            previous_15_change
        )

        # =================================================
        # ОБЪЁМ
        # =================================================

        previous_volume = sum(
            volumes[-30:-15]
        )

        last_volume = sum(
            volumes[-15:]
        )

        volume_rising = (
            last_volume
            >
            previous_volume * 1.10
        )

        # =================================================
        # СВЕЧИ
        # =================================================

        green_count = sum(
            1
            for change in last_15
            if change > 0
        )

        red_count = sum(
            1
            for change in last_15
            if change < 0
        )

        # =================================================
        # ПРЕДВАРИТЕЛЬНОЕ ДВИЖЕНИЕ
        # =================================================

        possible_buy = (
            hour_change > 0.5
            and last_15_change > 0.5
            and acceleration_up
            and volume_rising
            and green_count >= 9
        )

        possible_sell = (
            hour_change < -0.5
            and last_15_change < -0.5
            and acceleration_down
            and volume_rising
            and red_count >= 9
        )

        # Никакого предсигнала
        # если движение ещё недостаточное
        if not possible_buy and not possible_sell:
            return None

        # =================================================
        # СТАКАН
        # =================================================

        (
            buy_total,
            sell_total,
            best_bid,
            best_ask
        ) = get_order_book(symbol)

        # =================================================
        # ПРЕДСИГНАЛ BUY
        # =================================================

        if (
            possible_buy
            and buy_total > sell_total
        ):

            return {
                "symbol": symbol,

                "direction":
                    "🔎 ВОЗМОЖНЫЙ BUY",

                "hour_change":
                    hour_change,

                "last_15_change":
                    last_15_change,

                "price":
                    last_close,

                "buy":
                    buy_total,

                "sell":
                    sell_total,

                "entry":
                    last_close,

                "key":
                    f"{symbol}:PRE_BUY"
            }

        # =================================================
        # ПРЕДСИГНАЛ SELL
        # =================================================

        if (
            possible_sell
            and sell_total > buy_total
        ):

            return {
                "symbol": symbol,

                "direction":
                    "🔎 ВОЗМОЖНЫЙ SELL",

                "hour_change":
                    hour_change,

                "last_15_change":
                    last_15_change,

                "price":
                    last_close,

                "buy":
                    buy_total,

                "sell":
                    sell_total,

                "entry":
                    last_close,

                "key":
                    f"{symbol}:PRE_SELL"
            }

        return None

    except Exception as e:

        print(
            f"Ошибка предсигнала {symbol}:",
            e
        )

        return None


# =========================================================
# 📩 ОТПРАВКА ПРЕДСИГНАЛА
# =========================================================

def send_pre_signal(result):

    if not result:
        return

    key = result["key"]

    now = time.time()

    # Не отправляем один и тот же
    # предсигнал чаще одного раза в 5 минут
    if key in last_alerts:

        if now - last_alerts[key] < ALERT_COOLDOWN:
            return

    last_alerts[key] = now

    message = (
        "🔎 ПРЕДСИГНАЛ Aster DEX\n\n"

        f"💲 {result['symbol']}\n"

        f"📌 {result['direction']}\n\n"

        f"📊 Изменение за 1 час: "
        f"{result['hour_change']:+.2f}%\n"

        f"⚡ Последние 15 минут: "
        f"{result['last_15_change']:+.2f}%\n"

        f"💵 Текущая цена: "
        f"{result['price']:.8f}\n\n"

        f"🟢 BUY: "
        f"${result['buy']:,.0f}\n"

        f"🔴 SELL: "
        f"${result['sell']:,.0f}\n\n"

        "⚠️ Движение только формируется\n"
        "Ожидается подтверждение"
    )

    print(message)

    send_telegram(message)


# =========================================================
# ПОЛУЧАЕМ СПИСОК МОНЕТ
# =========================================================

def get_symbols():

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

            symbol = item.get("symbol")

            if not symbol:
                continue

            if not symbol.endswith("USDT"):
                continue

            if symbol in EXCLUDED_SYMBOLS:
                continue

            volume = float(
                item.get("quoteVolume", 0)
            )

            if volume < MIN_VOLUME:
                continue

            symbols.append(
                (
                    symbol,
                    volume
                )
            )

        return symbols

    except Exception as e:

        print(
            "❌ Ошибка получения списка монет:",
            e
        )

        return []


# =========================================================
# ОСНОВНОЙ СКАН
# =========================================================

def scan():

    print(
        "\n"
        "=============================="
    )

    print(
        "🔥 Aster DEX — новый скан"
    )

    print(
        "=============================="
    )

    symbols = get_symbols()

    print(
        f"✅ Монет для проверки: "
        f"{len(symbols)}"
    )

    results = []
    pre_results = []

    # =====================================================
    # ОСНОВНАЯ ПРОВЕРКА
    # =====================================================

    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:

        futures = {}

        for symbol, volume in symbols:

            future = executor.submit(
                check_symbol,
                symbol,
                volume
            )

            futures[future] = symbol

        for future in as_completed(futures):

            symbol = futures[future]

            try:

                result = future.result()

                if result:
                    results.append(result)

            except Exception as e:

                print(
                    f"Ошибка результата {symbol}:",
                    e
                )

    # =====================================================
    # ОСНОВНЫЕ СИГНАЛЫ
    # =====================================================

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

    # =====================================================
    # ПРЕДСИГНАЛЫ
    # =====================================================

    for symbol, volume in symbols:

        try:

            pre_result = get_pre_signal(
                symbol
            )

            if pre_result:

                pre_results.append(
                    pre_result
                )

        except Exception as e:

            print(
                f"Ошибка предсигнала {symbol}:",
                e
            )

    # =====================================================
    # ОТПРАВКА ПРЕДСИГНАЛОВ
    # =====================================================

    if pre_results:

        print(
            f"\n🔎 Найдено предсигналов: "
            f"{len(pre_results)}"
        )

        for pre_result in pre_results:

            send_pre_signal(
                pre_result
            )

    else:

        print(
            "🔎 Предсигналов нет"
        )


# =========================================================
# ЗАПУСК МОНИТОРА
# =========================================================

def main():

    print(
        "🚀 Aster Monitor запущен"
    )

    print(
        "🚫 BTCUSDT и ETHUSDT исключены"
    )

    print(
        "📊 Порог движения: ±3% за 1M"
    )

    print(
        "💰 Порог стакана: $15,000"
    )

    print(
        "⏱ Интервал сканирования: 30 секунд"
    )

    print(
        "=============================="
    )

    while True:

        try:

            scan()

        except Exception as e:

            print(
                "❌ Критическая ошибка скана:",
                e
            )

        print(
            "\n🔄 Следующий скан через "
            f"{SCAN_INTERVAL} секунд.."
        )

        time.sleep(
            SCAN_INTERVAL
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
