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
            "last_names": {},
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

    if "last_names" not in data:
        data["last_names"] = {}

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

    for store in stores:
        if normalize_text(store["store_name"]) == query:
            return store

    for store in stores:
        if normalize_text(store["display_name"]) == query:
            return store

    startswith_matches = []
    for store in stores:
        store_name = normalize_text(store["store_name"])
        display_name = normalize_text(store["display_name"])

        if store_name.startswith(query) or display_name.startswith(query):
            startswith_matches.append(store)

    if len(startswith_matches) == 1:
        return startswith_matches[0]

    contains_matches = []
    for store in stores:
        store_name = normalize_text(store["store_name"])
        display_name = normalize_text(store["display_name"])

        if query in store_name or query in display_name:
            contains_matches.append(store)

    if len(contains_matches) == 1:
        return contains_matches[0]

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
        [InlineKeyboardButton("👀 Watch", callback_data="watch_now")],
        [InlineKeyboardButton("➕ Add restaurant", callback_data="add_restaurant")],
        [InlineKeyboardButton("➖ Remove restaurant", callback_data="remove_restaurant")],
        [InlineKeyboardButton("📋 View watched restaurants", callback_data="show_restaurants")],
        [InlineKeyboardButton("ℹ️ Status", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_back_to_menu():
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to main menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_confirm_candidate_menu():
    keyboard = [
        [InlineKeyboardButton("✅ Yes, add", callback_data="confirm_add_restaurant")],
        [InlineKeyboardButton("❌ No, not this", callback_data="reject_add_restaurant")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_store_name_map():
    stores = load_items()
    return {str(store["store_id"]): store["store_name"] for store in stores}


def build_watch_text() -> str:
    state = load_state()
    watched_ids = [str(x) for x in state.get("watched_store_ids", [])]
    last = state.get("last", {})
    last_names = state.get("last_names", {})

    if not watched_ids:
        return (
            "👀 Watching enabled\n\n"
            "No restaurants added yet."
        )

    lines = [
        "👀 Watching enabled",
        "",
        "Current availability:"
    ]

    store_map = get_store_name_map()

    for sid in watched_ids:
        name = last_names.get(sid) or store_map.get(sid, f"Unknown store ({sid})")

        if sid in last:
            avail = int(last.get(sid, 0))
            lines.append(f"• {name}: {avail} items")
        else:
            lines.append(f"• {name}: no data yet")

    return "\n".join(lines)


def build_restaurants_text() -> str:
    state = load_state()
    watched_ids = [str(x) for x in state.get("watched_store_ids", [])]
    last = state.get("last", {})
    last_names = state.get("last_names", {})

    if not watched_ids:
        return "📋 Watched restaurants\n\nList is empty."

    store_map = get_store_name_map()

    lines = ["📋 Watched restaurants\n"]

    for idx, sid in enumerate(watched_ids, start=1):
        name = last_names.get(sid) or store_map.get(sid, f"Unknown store ({sid})")

        if sid in last:
            avail = int(last.get(sid, 0))
            lines.append(f"{idx}. {name} — {avail} items")
        else:
            lines.append(f"{idx}. {name} — no data yet")

    return "\n".join(lines)


def build_remove_restaurant_menu():
    state = load_state()
    watched_ids = [str(x) for x in state.get("watched_store_ids", [])]
    last_names = state.get("last_names", {})
    store_map = get_store_name_map()

    keyboard = []

    for sid in watched_ids:
        name = last_names.get(sid) or store_map.get(sid, f"Unknown store ({sid})")
        short_name = name[:55] + "…" if len(name) > 55 else name
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {short_name}",
                callback_data=f"delete_store:{sid}"
            )
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Back to main menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    state["bot"]["awaiting_restaurant_input"] = False
    state["bot"]["pending_store_candidate"] = None
    save_state(state)

    await update.message.reply_text(
        "TGTG Watcher\n\nMain menu:",
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
            text="TGTG Watcher\n\nMain menu:",
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
                "➕ Add restaurant\n\n"
                "Send the name as a message.\n"
                "Example: Anker or Finn"
            ),
            reply_markup=build_back_to_menu()
        )
        return

    if data == "confirm_add_restaurant":
        candidate = bot_state.get("pending_store_candidate")

        if not candidate:
            await query.edit_message_text(
                text="❌ No restaurant to confirm.\n\nReturning to main menu.",
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
                    f"ℹ️ This restaurant is already being tracked:\n\n"
                    f"{store_name}"
                ),
                reply_markup=build_main_menu()
            )
            return

        if len(watched_ids) >= MAX_WATCHED_RESTAURANTS:
            bot_state["pending_store_candidate"] = None
            save_state(state)

            await query.edit_message_text(
                text=f"❌ You cannot add more than {MAX_WATCHED_RESTAURANTS} restaurants.",
                reply_markup=build_main_menu()
            )
            return

        watched_ids.append(store_id)
        state["watched_store_ids"] = watched_ids
        bot_state["pending_store_candidate"] = None
        save_state(state)

        await query.edit_message_text(
            text=(
                "✅ Restaurant added to tracking\n\n"
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
            text="❌ Restaurant not found.\n\nReturning to main menu.",
            reply_markup=build_main_menu()
        )
        return

    if data == "remove_restaurant":
        bot_state["awaiting_restaurant_input"] = False
        bot_state["pending_store_candidate"] = None
        save_state(state)

        watched_ids = [str(x) for x in state.get("watched_store_ids", [])]

        if not watched_ids:
            await query.edit_message_text(
                text="➖ Remove restaurant\n\nWatched list is empty.",
                reply_markup=build_main_menu()
            )
            return

        await query.edit_message_text(
            text="➖ Choose a restaurant to remove:",
            reply_markup=build_remove_restaurant_menu()
        )
        return

    if data.startswith("delete_store:"):
        store_id = data.split(":", 1)[1]
        watched_ids = [str(x) for x in state.get("watched_store_ids", [])]
        last = state.get("last", {})
        last_names = state.get("last_names", {})
        store_map = get_store_name_map()

        if store_id not in watched_ids:
            await query.edit_message_text(
                text="❌ This restaurant is no longer being tracked.",
                reply_markup=build_main_menu()
            )
            return

        watched_ids = [sid for sid in watched_ids if sid != store_id]
        state["watched_store_ids"] = watched_ids

        removed_name = last_names.get(store_id) or store_map.get(store_id, f"Unknown store ({store_id})")

        if store_id in last:
            del last[store_id]
        if store_id in last_names:
            del last_names[store_id]

        state["last"] = last
        state["last_names"] = last_names
        save_state(state)

        await query.edit_message_text(
            text=(
                "✅ Restaurant removed from tracking\n\n"
                f"{removed_name}"
            ),
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

        enabled_text = "enabled" if bot_state.get("enabled") else "disabled"
        watched_count = len(state.get("watched_store_ids", []))

        await query.edit_message_text(
            text=(
                "ℹ️ Status\n\n"
                f"Watching: {enabled_text}\n"
                f"Mode: track quantity changes\n"
                f"Tracked restaurants: {watched_count}/{MAX_WATCHED_RESTAURANTS}"
            ),
            reply_markup=build_back_to_menu()
        )
        return

    await query.edit_message_text(
        text="Unknown command",
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
                f"❌ You cannot add more than {MAX_WATCHED_RESTAURANTS} restaurants.\n\n"
                "Returning to main menu."
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
                "❌ Restaurant not found.\n\n"
                "Returning to main menu."
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
            "❓ Did you mean this restaurant?\n\n"
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