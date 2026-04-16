import os
import json
import httpx
from typing import Dict, Any, List
from api import TgtgClient
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = "state.json"


def tg_send(text: str) -> None:
    token = os.environ["TG_BOT_TOKEN"]
    chat_id = os.environ["TG_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    with httpx.Client(timeout=15) as client:
        response = client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text
            }
        )
        response.raise_for_status()


def load_state() -> Dict[str, Any]:
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


def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_tgtg_availability() -> List[Dict[str, Any]]:
    client = TgtgClient(
        access_token=os.environ["TGTG_ACCESS_TOKEN"],
        refresh_token=os.environ["TGTG_REFRESH_TOKEN"],
        cookie=os.environ["TGTG_COOKIE"],
    )

    all_items = []
    page = 1

    while True:
        items = client.get_items(
            favorites_only=False,
            latitude=48.2082,
            longitude=16.3738,
            radius=25,
            page_size=100,
            page=page,
        )

        if not items:
            break

        all_items.extend(items)

        if len(items) < 100:
            break

        page += 1

    stores_map: Dict[str, Dict[str, Any]] = {}

    for item in all_items:
        store = item.get("store", {})
        store_id = str(store.get("store_id", "")).strip()
        store_name = str(store.get("store_name", "Unknown store")).strip()
        items_available = int(item.get("items_available", 0))

        if not store_id:
            continue

        if store_id not in stores_map:
            stores_map[store_id] = {
                "store_id": store_id,
                "store_name": store_name,
                "items_available": items_available,
            }
        else:
            stores_map[store_id]["items_available"] = max(
                int(stores_map[store_id]["items_available"]),
                items_available
            )

    result = list(stores_map.values())

    print(f"LIVE RAW ITEMS: {len(all_items)}")
    print(f"LIVE UNIQUE STORES: {len(result)}")

    return result


def main() -> None:
    state = load_state()
    last = state.get("last", {})
    last_names = state.get("last_names", {})
    bot_state = state.get("bot", {})
    watched_ids = set(str(x) for x in state.get("watched_store_ids", []))

    if not bot_state.get("enabled", False):
        print("Watcher disabled from Telegram")
        return

    if not watched_ids:
        print("No watched restaurants")
        return

    offers = fetch_tgtg_availability()

    for o in offers:
        sid = str(o["store_id"])
        if sid not in watched_ids:
            continue

        avail = int(o.get("items_available", 0))
        prev = int(last.get(sid, -1))
        name = o.get("store_name", "Unknown store")

        last_names[sid] = name

        if prev != -1 and prev != avail:
            tg_send(
                f"📦 {name}\n\n"
                f"Было: {prev}\n"
                f"Стало: {avail}"
            )

        last[sid] = avail

    state["last"] = last
    state["last_names"] = last_names
    save_state(state)


if __name__ == "__main__":
    main()