import json
import os
from difflib import get_close_matches

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from watcher import fetch_tgtg_availability

load_dotenv()

STATE_FILE = "state.json"
ITEMS_FILE = "items-list"
MAX_WATCHED_RESTAURANTS = 10


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last": {},
            "bot": {
                "enabled": False,
                "mode": "track_changes",
                "awaiting_restaurant_input": False,
                "pending_store_candidate": None,
            },
            "watched_store_ids": []
        }

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "last" not in data:
        data["last"] = {}

    if "bot" not in data:
        data["bot"] = {}

    data["bot"].setdefault("enabled", False)
    data["bot"].setdefault("mode", "track_changes")
    data["bot"].setdefault("awaiting_restaurant_input", False)
    data["bot"].setdefault("pending_store_candidate", None)

    if "watched_store_ids" not in data:
        data["watched_store_ids"] = []

    return data


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_items():
    if not os.path.exists(ITEMS_FILE):
        return []

    with open(ITEMS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    items = raw.get("items", [])
    result = []

    for entry in items:
        store = entry.get("store", {})
        display_name = str(entry.get("display_name", "")).strip()
        store_id = str(store.get("store_id", "")).strip()
        store_name = str(store.get("store_name", "")).strip()

        if not store_id or not store_name:
            continue

        result.append({
            "store_id": store_id,
            "store_name": store_name,
            "display_name": display_name,
        })

    unique = {}
    for x in result:
        unique[x["store_id"]] = x

    return list(unique.values())


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def find_store_candidate(user_input: str):
    stores = load_items()
    query = normalize_text(user_input)

    if not query:
        return None

    # 1. точное совпадение store_name
    for store in stores:
        if normalize_text(store["store_name"]) == query:
            return store

    # 2. точное совпадение display_name
    for store in stores:
        if normalize_text(store["display_name"]) == query:
            return store

    # 3. store_name/display_name начинается с запроса
    startswith_matches = []
    for store in stores:
        store_name = normalize_text(store["store_name"])
        display_name = normalize_text(store["display_name"])

        if store_name.startswith(query) or display_name.startswith(query):
            startswith_matches.append(store)

    if len(startswith_matches) == 1:
        return startswith_matches[0]

    # 4. частичное совпадение
    contains_matches = []
    for store in stores:
        store_name = normalize_text(store["store_name"])
        display_name = normalize_text(store["display_name"])

        if query in store_name or query in display_name:
            contains_matches.append(store)

    if len(contains_matches) == 1:
        return contains_matches[0]

    # 5. fuzzy matching
    lookup = {}
    candidates = []

    for store in stores:
        for raw_name in [store["store_name"], store["display_name"]]:
            key = normalize_text(raw_name)
            if key:
                lookup[key] = store
                candidates.append(key)

    cutoff = 0.92 if len(query) <= 4 else 0.85
    close = get_close_matches(query, candidates, n=1, cutoff=cutoff)

    if close:
        return lookup[close[0]]

    return None


def build_main_menu():
    keyboard = [
        [InlineKeyboardButton("👀 Следить", callback_data="watch_now")],
        [InlineKeyboardButton("➕ Добавить ресторан", callback_data="add_restaurant")],
        [InlineKeyboardButton("📋 Посмотреть отслеживаемые рестораны", callback_data="show_restaurants")],
        [InlineKeyboardButton("ℹ️ Статус", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_back_to_menu():
    keyboard = [
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_confirm_candidate_menu():
    keyboard = [
        [InlineKeyboardButton("✅ Да, добавить", callback_data="confirm_add_restaurant")],
        [InlineKeyboardButton("❌ Нет, не он", callback_data="reject_add_restaurant")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_store_name_map():
    stores = load_items()
    return {str(store["store_id"]): store["store_name"] for store in stores}


def build_watch_text() -> str:
    state = load_state()
    watched_ids = [str(x) for x in state.get("watched_store_ids", [])]

    if not watched_ids:
        return (
            "👀 Слежение включено\n\n"
            "Но у тебя пока нет отслеживаемых ресторанов."
        )

    try:
        offers = fetch_tgtg_availability()
    except Exception as e:
        return (
            "👀 Слежение включено\n\n"
            "Не удалось получить текущие данные по ресторанам.\n"
            f"Ошибка: {e}"
        )

    offers_map = {}
    for offer in offers:
        sid = str(offer.get("store_id"))
        offers_map[sid] = offer

    store_map = get_store_name_map()

    lines = [
        "👀 Слежение включено",
        "",
        "Сейчас по отслеживаемым ресторанам:"
    ]

    for sid in watched_ids:
        name = store_map.get(sid, f"Unknown store ({sid})")
        offer = offers_map.get(sid)

        if offer:
            avail = int(offer.get("items_available", 0))
            lines.append(f"• {name}: {avail} пак.")
        else:
            lines.append(f"• {name}: нет данных")

    return "\n".join(lines)


def build_restaurants_text() -> str:
    state = load_state()
    watched_ids = [str(x) for x in state.get("watched_store_ids", [])]
    last = state.get("last", {})
    last_names = state.get("last_names", {})

    if not watched_ids:
        return "📋 Отслеживаемые рестораны\n\nСписок пуст."

    store_map = get_store_name_map()

    lines = ["📋 Отслеживаемые рестораны\n"]

    for idx, sid in enumerate(watched_ids, start=1):
        name = last_names.get(sid) or store_map.get(sid, f"Unknown store ({sid})")

        if sid in last:
            avail = int(last.get(sid, 0))
            lines.append(f"{idx}. {name} — {avail} пак.")
        else:
            lines.append(f"{idx}. {name} — пока нет данных")

    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    state["bot"]["awaiting_restaurant_input"] = False
    state["bot"]["pending_store_candidate"] = None
    save_state(state)

    await update.message.reply_text(
        "TGTG Watcher\n\nГлавное меню:",
        reply_markup=build_main_menu()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    state = load_state()
    bot_state = state["bot"]
    data = query.data

    if data == "main_menu":
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await query.edit_message_text(
            text="TGTG Watcher\n\nГлавное меню:",
            reply_markup=build_main_menu()
        )
        return

    if data == "watch_now":
        bot_state["enabled"] = True
        bot_state["mode"] = "track_changes"
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await query.edit_message_text(
            text=build_watch_text(),
            reply_markup=build_back_to_menu()
        )
        return

    if data == "add_restaurant":
        bot_state["awaiting_restaurant_input"] = True
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await query.edit_message_text(
            text=(
                "➕ Добавление ресторана\n\n"
                "Отправь название сообщением.\n"
                "Например: Anker или Finn"
            ),
            reply_markup=build_back_to_menu()
        )
        return

    if data == "confirm_add_restaurant":
        candidate = bot_state.get("pending_store_candidate")

        if not candidate:
            await query.edit_message_text(
                text="❌ Нет ресторана для подтверждения.\n\nВозвращаю в главное меню.",
                reply_markup=build_main_menu()
            )
            return

        watched_ids = [str(x) for x in state.get("watched_store_ids", [])]
        store_id = str(candidate["store_id"])
        store_name = candidate.get("display_name") or candidate["store_name"]

        if store_id in watched_ids:
            bot_state["pending_store_candidate"] = None
            save_state(state)

            await query.edit_message_text(
                text=(
                    f"ℹ️ Этот ресторан уже отслеживается:\n\n"
                    f"{store_name}"
                ),
                reply_markup=build_main_menu()
            )
            return

        if len(watched_ids) >= MAX_WATCHED_RESTAURANTS:
            bot_state["pending_store_candidate"] = None
            save_state(state)

            await query.edit_message_text(
                text=f"❌ Нельзя добавить больше {MAX_WATCHED_RESTAURANTS} ресторанов.",
                reply_markup=build_main_menu()
            )
            return

        watched_ids.append(store_id)
        state["watched_store_ids"] = watched_ids
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await query.edit_message_text(
            text=(
                "✅ Ресторан добавлен в слежку\n\n"
                f"{store_name}"
            ),
            reply_markup=build_main_menu()
        )
        return

    if data == "reject_add_restaurant":
        bot_state["pending_store_candidate"] = None
        bot_state["awaiting_restaurant_input"] = False
        save_state(state)

        await query.edit_message_text(
            text="❌ Не нашли такого ресторана.\n\nВозвращаю в главное меню.",
            reply_markup=build_main_menu()
        )
        return

    if data == "show_restaurants":
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await query.edit_message_text(
            text=build_restaurants_text(),
            reply_markup=build_back_to_menu()
        )
        return

    if data == "status":
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        enabled_text = "включено" if bot_state.get("enabled") else "выключено"
        watched_count = len(state.get("watched_store_ids", []))

        await query.edit_message_text(
            text=(
                "ℹ️ Статус\n\n"
                f"Слежение: {enabled_text}\n"
                f"Режим: следить за изменением количества\n"
                f"Ресторанов в слежке: {watched_count}/{MAX_WATCHED_RESTAURANTS}"
            ),
            reply_markup=build_back_to_menu()
        )
        return

    await query.edit_message_text(
        text="Неизвестная команда",
        reply_markup=build_back_to_menu()
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    state = load_state()
    bot_state = state["bot"]

    if not bot_state.get("awaiting_restaurant_input", False):
        return

    user_input = update.message.text.strip()
    watched_ids = [str(x) for x in state.get("watched_store_ids", [])]

    if len(watched_ids) >= MAX_WATCHED_RESTAURANTS:
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await update.message.reply_text(
            (
                f"❌ Нельзя добавить больше {MAX_WATCHED_RESTAURANTS} ресторанов.\n\n"
                "Возвращаю в главное меню."
            ),
            reply_markup=build_main_menu()
        )
        return

    store = find_store_candidate(user_input)

    if not store:
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await update.message.reply_text(
            (
                "❌ Не нашли такого ресторана.\n\n"
                "Возвращаю в главное меню."
            ),
            reply_markup=build_main_menu()
        )
        return

    bot_state["awaiting_restaurant_input"] = False
    bot_state["pending_store_candidate"] = {
        "store_id": str(store["store_id"]),
        "store_name": store["store_name"],
        "display_name": store.get("display_name", ""),
    }
    save_state(state)

    pretty_name = store.get("display_name") or store["store_name"]

    await update.message.reply_text(
        (
            "❓ Ты имел в виду этот ресторан?\n\n"
            f"{pretty_name}"
        ),
        reply_markup=build_confirm_candidate_menu()
    )


def main():
    token = os.environ["TG_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Telegram bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()