import os
import json
import httpx
from typing import Dict, Any, List

STATE_FILE = "state.json"

def tg_send(text: str) -> None:
    token = os.environ["TG_BOT_TOKEN"]
    chat_id = os.environ["TG_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=15) as client:
        client.post(url, json={"chat_id": chat_id, "text": text})

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"last": {}}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

def fetch_tgtg_availability() -> List[Dict[str, Any]]:
    # TODO: подключим TGTG позже
    return []

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
