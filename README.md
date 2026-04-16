# TGTG Watcher (Too Good To Go Bot)

Telegram bot that monitors Too Good To Go restaurant availability and notifies you when the number of available packages changes.

---

## Features

* Track multiple restaurants (up to 10)
* Get notifications when availability changes
* Smart restaurant search (supports partial names)
* Add restaurants via Telegram
* Remove restaurants easily
* View tracked restaurants with current availability
* Lightweight and fast

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Roflekss/tgtg-watcher.git
cd tgtg-watcher
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Telegram Bot Setup

### 1. Create a bot via BotFather

1. Open Telegram and search for BotFather
2. Send:

```
/start
```

3. Then:

```
/newbot
```

4. Enter:

   * Bot name (e.g. TGTG Watcher)
   * Username (must end with "bot")

5. You will receive a token like:

```
123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
```

---

### 2. Add token to .env

Create a `.env` file in the project root:

```
TG_BOT_TOKEN=your_token_here
```

---

### 3. Run the bot

```bash
python telegram_bot.py
```

---

### 4. Run the watcher (separate terminal)

```bash
python run_watcher.py
```

---

### 5. Use the bot

1. Open your bot in Telegram
2. Press "Start"
3. Use the menu to:

   * Add restaurants
   * Start watching
   * Receive notifications

---

## How it works

* `watcher.py` fetches data from Too Good To Go
* `run_watcher.py` continuously checks for changes
* `telegram_bot.py` handles user interaction

---

## Configuration

* Maximum tracked restaurants: 10
* Data is stored in `state.json`

---

## Security

Make sure the following files are not committed:

```
.env
state.json
```

---

## Future improvements

* Multi-language support (EN / DE / RU)
* Multi-user support
* Deployment to VPS or cloud
* Web interface
* Smarter notifications (e.g. only when availability > 0)

---

## Contributing

Pull requests are welcome.

---

## Disclaimer

This project is not affiliated with Too Good To Go. Use at your own risk.

---

## License

MIT
