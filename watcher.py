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
        response = client.post(url, json={
            "chat_id": chat_id,
            "text": text
        })
        response.raise_for_status()

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"last": {}}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def fetch_tgtg_availability():
    client = TgtgClient(
        access_token=os.environ["TGTG_ACCESS_TOKEN"],
        refresh_token=os.environ["TGTG_REFRESH_TOKEN"],
        cookie=os.environ["TGTG_COOKIE"]
    )

    items = client.get_items()
    return [
        {
            "store_id": item["store"]["store_id"],
            "store_name": item["store"]["store_name"],
            "items_available": item.get("items_available", 0),
        }
        for item in items
    ]



def main() -> None:
    watched_ids = set(filter(None, os.environ.get("WATCHED_STORE_IDS", "").split(",")))
    state = load_state()
    last = state.get("last", {})

    offers = fetch_tgtg_availability()

    for o in offers:
        sid = str(o["store_id"])
        if sid not in watched_ids:
            continue

        avail = int(o.get("items_available", 0))
        prev = int(last.get(sid, -1))
        name = o.get("store_name", "Unknown store")

        if avail > 0 and prev != avail:
            tg_send(f"В {name} сейчас доступно пакетов: {avail}")
        elif avail == 0:
            tg_send(f"В {name} пакетов больше нет")

        last[sid] = avail

    state["last"] = last
    save_state(state)

if __name__ == "__main__":
    main()
