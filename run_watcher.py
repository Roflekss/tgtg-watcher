import time
from datetime import datetime
from watcher import main

CHECK_EVERY_SECONDS = 300  # 5 минут

if __name__ == "__main__":
    print("Watcher loop started")
    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] checking...")
            main()
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] error: {e!r}")

        time.sleep(CHECK_EVERY_SECONDS)