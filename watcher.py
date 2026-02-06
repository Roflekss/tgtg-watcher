import os
import json
import httpx
from typing import Dict, Any, List
from tgtg import TgtgClient


STATE_FILE = "state.json"

def tg_send(text: str) -> None:
    print("TG SEND:", text)

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"last": {}}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def fetch_tgtg_availability():
    email = os.environ["TGTG_EMAIL"]
    password = os.environ["TGTG_PASSWORD"]

    client = TgtgClient(email=email)
    client.login(password=password)

    items = client.get_items()

    result = []
    for item in items:
        result.append({
            "store_id": item["store"]["store_id"],
            "store_name": item["store"]["store_name"],
            "items_available": item["items_available"],
        })

    return result


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

        if avail == 1 and prev != 1:
            tg_send(f"🔥 Остался последний пакет: {o['store_name']}")

        last[sid] = avail

    state["last"] = last
    save_state(state)

if __name__ == "__main__":
    main()
