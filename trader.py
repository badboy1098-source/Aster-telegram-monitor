import os
import time
import math
import requests


# =========================================================
# ASTER AUTO TRADER
# PAPER MODE — РЕАЛЬНЫЕ ОРДЕРА ПОКА ОТКЛЮЧЕНЫ
# =========================================================

ASTER_BASE = "https://fapi.asterdex.com"

# ---------------------------------------------------------
# ОСНОВНЫЕ НАСТРОЙКИ
# ---------------------------------------------------------

AUTO_TRADE = False

RISK_PER_TRADE = 0.01          # 1%
MIN_RR = 3.0                    # минимум 1:3
MAX_OPEN_POSITIONS = 3

PAPER_START_BALANCE = 100.0
paper_balance = PAPER_START_BALANCE

# Пока пусто — автоматические сделки запрещены.
# Позже сюда добавим разрешённые символы.
ALLOWED_SYMBOLS = set()

TRADER_CHAT_ID = os.getenv("TRADER_CHAT_ID")

# Защита от повторных сделок
active_trades = {}
completed_trade_ids = set()


# =========================================================
# УТИЛИТЫ
# =========================================================

def log(message):
    print(f"[TRADER] {message}", flush=True)

def send_trader_telegram(message):
    """
    Отправляет торговые уведомления только владельцу.
    Подписчики ASTER PRO это сообщение не получают.
    """

    token = os.getenv("TELEGRAM_TOKEN")

    if not token:
        log("❌ TRADER: TELEGRAM_TOKEN не найден")
        return False

    if not TRADER_CHAT_ID:
        log("❌ TRADER: TRADER_CHAT_ID не найден")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": TRADER_CHAT_ID,
                "text": message
            },
            timeout=10
        )

        if response.ok:
            return True

        log(
            f"❌ TRADER Telegram ошибка: "
            f"{response.status_code} {response.text}"
        )

    except Exception as e:
        log(f"❌ TRADER Telegram ошибка: {e}")

    return False


def get_account_balance():
    """
    PAPER MODE.
    Реальный баланс Aster пока НЕ запрашивается.
    """
    return None


def calculate_position_size(
    balance,
    entry_price,
    stop_price,
    risk_percent=RISK_PER_TRADE
):
    """
    Рассчитывает размер позиции так,
    чтобы риск до Stop Loss составлял
    не более заданного процента баланса.
    """

    if balance <= 0:
        return 0

    if entry_price <= 0 or stop_price <= 0:
        return 0

    stop_distance = abs(entry_price - stop_price)

    if stop_distance <= 0:
        return 0

    risk_amount = balance * risk_percent

    quantity = risk_amount / stop_distance

    return quantity


def calculate_rr(entry, stop, target):
    """
    Расчёт Risk/Reward.
    """

    risk = abs(entry - stop)

    if risk <= 0:
        return 0

    reward = abs(target - entry)

    return reward / risk


# =========================================================
# ПРОВЕРКА СИГНАЛА
# =========================================================

def validate_trade_signal(signal):
    """
    Финальная проверка сигнала перед PAPER/REAL торговлей.

    Реальный ордер здесь пока НЕ отправляется.
    """

    symbol = signal.get("symbol")
    direction = signal.get("direction")
    entry = signal.get("entry")
    stop = signal.get("stop_loss")

    # Для автоматической торговли используем TP3,
    # потому что минимальный RR должен быть 1:3.
    target = signal.get("tp3")

    if not symbol:
        return False, "Нет symbol"

    if not direction:
        return False, "Нет direction"

    direction = direction.upper()

    if direction not in {"LONG", "SHORT"}:
        return False, f"Неверное направление: {direction}"

    if entry is None or stop is None or target is None:
        return False, "Не хватает entry / stop_loss / tp3"

    try:
        entry = float(entry)
        stop = float(stop)
        target = float(target)
    except (TypeError, ValueError):
        return False, "Некорректные цены"

    if entry <= 0 or stop <= 0 or target <= 0:
        return False, "Цена должна быть больше 0"

    # ---------------------------------------------------------
    # Проверяем Stop Loss и Target
    # ---------------------------------------------------------

    if direction == "LONG":

        if stop >= entry:
            return False, "LONG: Stop Loss должен быть ниже Entry"

        if target <= entry:
            return False, "LONG: TP3 должен быть выше Entry"

    elif direction == "SHORT":

        if stop <= entry:
            return False, "SHORT: Stop Loss должен быть выше Entry"

        if target >= entry:
            return False, "SHORT: TP3 должен быть ниже Entry"

    # ---------------------------------------------------------
    # Проверяем RR
    # ---------------------------------------------------------

    rr = calculate_rr(
        entry,
        stop,
        target
    )

    if rr < MIN_RR:
        return False, f"RR слишком маленький: {rr:.2f}"

    # ---------------------------------------------------------
    # Проверяем разрешённые монеты
    # ---------------------------------------------------------

    if ALLOWED_SYMBOLS and symbol not in ALLOWED_SYMBOLS:
        return False, f"{symbol} запрещён для автоторговли"

    return True, {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "stop_loss": stop,
        "target": target,
        "rr": rr
    }


# =========================================================
# PAPER TRADE
# =========================================================

def paper_trade(signal):
    """
    Имитация сделки.

    Реальный ордер НЕ отправляется.
    """

    symbol = signal.get("symbol")

    if not symbol:
        log("❌ PAPER: отсутствует symbol")
        return False

    # ---------------------------------------------------------
    # Защита от повторного входа
    # ---------------------------------------------------------

    if symbol in active_trades:
        log(
            f"⛔ PAPER: {symbol} уже находится "
            f"в активной позиции."
        )
        return False

    # ---------------------------------------------------------
    # Финальная проверка
    # ---------------------------------------------------------

    valid, result = validate_trade_signal(signal)

    if not valid:
        log(f"❌ PAPER: {symbol}: {result}")
        return False

    symbol = result["symbol"]
    direction = result["direction"]
    entry = result["entry"]
    stop = result["stop_loss"]
    target = result["target"]
    rr = result["rr"]

    # ---------------------------------------------------------
    # Лимит одновременных позиций
    # ---------------------------------------------------------

    if len(active_trades) >= MAX_OPEN_POSITIONS:
        log(
            f"⛔ PAPER: достигнут лимит "
            f"{MAX_OPEN_POSITIONS} позиций."
        )
        return False

    # ---------------------------------------------------------
    # PAPER баланс
    # ---------------------------------------------------------

    global paper_balance

    balance = paper_balance

    if balance <= 0:
        log("❌ PAPER: баланс закончился")
        return False

    # ---------------------------------------------------------
    # Размер позиции
    # ---------------------------------------------------------

    quantity = calculate_position_size(
        balance=balance,
        entry_price=entry,
        stop_price=stop,
        risk_percent=RISK_PER_TRADE
    )

    if quantity <= 0:
        log("❌ PAPER: некорректный размер позиции")
        return False

    # ---------------------------------------------------------
    # Trade ID
    # ---------------------------------------------------------

    trade_id = (
        f"{symbol}_"
        f"{direction}_"
        f"{entry}_"
        f"{stop}"
    )

    if trade_id in completed_trade_ids:
        log(
            f"⛔ PAPER: дубликат сделки "
            f"{trade_id}"
        )
        return False

    # ---------------------------------------------------------
    # Сохраняем активную сделку
    # ---------------------------------------------------------

    active_trades[symbol] = {
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "stop_loss": stop,
        "target": target,
        "quantity": quantity,
        "balance": balance,
        "risk_percent": RISK_PER_TRADE,
        "rr": rr,
        "status": "PAPER_OPEN",
        "created_at": time.time()
    }

    # ---------------------------------------------------------
    # Лог
    # ---------------------------------------------------------

    log("=" * 60)
    log("🧪 PAPER TRADE ОТКРЫТА")
    log(f"📊 Монета: {symbol}")
    log(f"📈 Направление: {direction}")
    log(f"💰 Entry: {entry}")
    log(f"🛑 Stop Loss: {stop}")
    log(f"🎯 Target: {target}")
    log(f"📐 RR: 1:{rr:.2f}")
    log(f"⚠️ Риск: {RISK_PER_TRADE * 100:.2f}%")
    log(f"📦 Количество: {quantity}")
    log(f"💵 PAPER баланс: {balance}")
    log(f"🆔 Trade ID: {trade_id}")
    
    log("🚫 РЕАЛЬНЫЙ ОРДЕР НЕ ОТПРАВЛЕН")
    log("=" * 60)

    # ---------------------------------------------------------
    # ЛИЧНОЕ УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦУ
    # ---------------------------------------------------------

    trader_message = (
        "🧪 ASTER PAPER TRADE\n\n"
        f"📊 Монета: {symbol}\n"
        f"📈 Направление: {direction}\n"
        f"💰 Entry: {entry}\n"
        f"🛑 Stop Loss: {stop}\n"
        f"🎯 Target: {target}\n"
        f"📐 RR: 1:{rr:.2f}\n"
        f"⚠️ Риск: {RISK_PER_TRADE * 100:.2f}%\n"
        f"📦 Количество: {quantity:.6f}\n"
        f"💵 PAPER баланс: ${balance:.2f}\n\n"
        "🚫 Реальный ордер НЕ отправлен."
    )

    send_trader_telegram(trader_message)

    return True


# =========================================================
# ЗАКРЫТИЕ PAPER-СДЕЛКИ
# =========================================================

def close_paper_trade(symbol, exit_price, reason="MANUAL"):
    """
    Закрывает виртуальную сделку,
    рассчитывает прибыль/убыток
    и обновляет PAPER баланс.
    """

    global paper_balance

    if symbol not in active_trades:
        log(
            f"ℹ️ PAPER: активной сделки "
            f"{symbol} нет."
        )
        return False

    try:
        exit_price = float(exit_price)
    except (TypeError, ValueError):
        log("❌ PAPER: некорректная цена выхода")
        return False

    trade = active_trades.pop(symbol)

    entry = trade["entry"]
    quantity = trade["quantity"]
    direction = trade["direction"]

    # ---------------------------------------------------------
    # Расчёт PnL
    # ---------------------------------------------------------

    if direction == "LONG":
        pnl = (exit_price - entry) * quantity
    else:
        pnl = (entry - exit_price) * quantity

    old_balance = paper_balance
    paper_balance += pnl

    # ---------------------------------------------------------
    # Защита от отрицательного баланса
    # ---------------------------------------------------------

    if paper_balance < 0:
        paper_balance = 0

    completed_trade_ids.add(
        trade["trade_id"]
    )

    # ---------------------------------------------------------
    # Лог
    # ---------------------------------------------------------

    log("=" * 60)
    log("🧪 PAPER TRADE ЗАКРЫТА")
    log(f"📊 Монета: {symbol}")
    log(f"📈 Направление: {direction}")
    log(f"💰 Entry: {entry}")
    log(f"🏁 Exit: {exit_price}")
    log(f"📦 Количество: {quantity}")
    log(f"💵 PnL: {pnl:+.2f} USDT")
    log(f"💵 Баланс до сделки: {old_balance:.2f} USDT")
    log(f"💵 Новый PAPER баланс: {paper_balance:.2f} USDT")
    log(f"📌 Причина: {reason}")
    log(f"🆔 Trade ID: {trade['trade_id']}")
    log("=" * 60)

    # ---------------------------------------------------------
    # Личное уведомление
    # ---------------------------------------------------------

    trader_message = (
        "🧪 ASTER PAPER TRADE ЗАКРЫТА\n\n"
        f"📊 Монета: {symbol}\n"
        f"📈 Направление: {direction}\n"
        f"💰 Entry: {entry}\n"
        f"🏁 Exit: {exit_price}\n"
        f"💵 PnL: {pnl:+.2f} USDT\n"
        f"💰 Баланс: ${paper_balance:.2f}\n"
        f"📌 Причина: {reason}"
    )

    send_trader_telegram(trader_message)

    return True

# =========================================================
# PAPER POSITION MONITOR
# =========================================================

def check_paper_positions():
    """
    Проверяет активные PAPER-позиции.
    Если цена достигла Stop Loss или Target —
    автоматически закрывает виртуальную сделку.
    """

    if not active_trades:
        return

    for symbol in list(active_trades.keys()):

        trade = active_trades.get(symbol)

        if not trade:
            continue

        try:
            response = requests.get(
                f"{ASTER_BASE}/fapi/v1/ticker/price",
                params={"symbol": symbol},
                timeout=10
            )

            response.raise_for_status()

            data = response.json()
            current_price = float(data["price"])

        except Exception as e:
            log(
                f"❌ PAPER: ошибка получения цены "
                f"{symbol}: {e}"
            )
            continue

        direction = trade["direction"]
        stop = trade["stop_loss"]
        target = trade["target"]

        # -----------------------------------------------------
        # LONG
        # -----------------------------------------------------

        if direction == "LONG":

            if current_price <= stop:

                log(
                    f"🛑 PAPER SL: {symbol} "
                    f"цена {current_price}"
                )

                close_paper_trade(
                    symbol,
                    current_price,
                    "STOP_LOSS"
                )

            elif current_price >= target:

                log(
                    f"🎯 PAPER TP: {symbol} "
                    f"цена {current_price}"
                )

                close_paper_trade(
                    symbol,
                    current_price,
                    "TAKE_PROFIT"
                )

        # -----------------------------------------------------
        # SHORT
        # -----------------------------------------------------

        elif direction == "SHORT":

            if current_price >= stop:

                log(
                    f"🛑 PAPER SL: {symbol} "
                    f"цена {current_price}"
                )

                close_paper_trade(
                    symbol,
                    current_price,
                    "STOP_LOSS"
                )

            elif current_price <= target:

                log(
                    f"🎯 PAPER TP: {symbol} "
                    f"цена {current_price}"
                )

                close_paper_trade(
                    symbol,
                    current_price,
                    "TAKE_PROFIT"
                )


# =========================================================
# ТЕСТОВЫЙ ЗАПУСК
# =========================================================

if __name__ == "__main__":

    log("🚀 ASTER AUTO TRADER запущен")
    log("🧪 PAPER MODE: ON")
    log(f"⚠️ Риск на сделку: {RISK_PER_TRADE * 100:.2f}%")
    log(f"📐 Минимальный RR: 1:{MIN_RR:.1f}")
    log(f"📊 Максимум позиций: {MAX_OPEN_POSITIONS}")
    log("🚫 Реальные ордера: OFF")
    log("⏳ Ожидание подключения ASTER PRO...")
