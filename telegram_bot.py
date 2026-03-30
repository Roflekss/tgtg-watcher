import json
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

load_dotenv()

STATE_FILE = "state.json"


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last": {},
            "bot": {
                "enabled": False,
                "mode": "last_package"
            }
        }

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "last" not in data:
        data["last"] = {}

    if "bot" not in data:
        data["bot"] = {
            "enabled": False,
            "mode": "last_package"
        }

    return data


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_menu():
    keyboard = [
        [InlineKeyboardButton("▶️ Начать слежение", callback_data="start_watch")],
        [InlineKeyboardButton("⏹ Остановить слежение", callback_data="stop_watch")],
        [InlineKeyboardButton("📦 Отслеживать последний пакет", callback_data="mode_last_package")],
        [InlineKeyboardButton("🔄 Следить за изменением количества", callback_data="mode_track_changes")],
        [InlineKeyboardButton("📊 Статус", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Got /start")
    await update.message.reply_text(
        "TGTG Watcher\n\nВыбери действие:",
        reply_markup=build_menu()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    state = load_state()
    bot_state = state["bot"]
    data = query.data

    if data == "start_watch":
        bot_state["enabled"] = True
        save_state(state)
        text = "✅ Слежение включено"

    elif data == "stop_watch":
        bot_state["enabled"] = False
        save_state(state)
        text = "⛔ Слежение выключено"

    elif data == "mode_track_changes":
        bot_state["mode"] = "track_changes"
        save_state(state)
        text = "🔄 Режим: следить за изменением количества пакетов"

    elif data == "mode_last_package":
        bot_state["mode"] = "last_package"
        save_state(state)
        text = "📦 Режим: отслеживать последний пакет"

    elif data == "status":
        enabled_text = "включено" if bot_state.get("enabled") else "выключено"
        mode_text = bot_state.get("mode", "unknown")
        text = (
            f"📊 Статус\n\n"
            f"Слежение: {enabled_text}\n"
            f"Режим: {mode_text}"
        )

    else:
        text = "Неизвестная команда"

    await query.edit_message_text(
        text=text,
        reply_markup=build_menu()
    )

def main():
    token = os.environ["TG_BOT_TOKEN"]

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Telegram bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()