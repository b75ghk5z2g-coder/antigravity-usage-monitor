# 🚀 Antigravity Usage Monitor

> **Real-time terminal & desktop quota monitor for Google Antigravity.**  
> Track your 5-Hour and Weekly limit resets, token consumption, and model quotas with **zero dependencies**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![Dependencies](https://img.shields.io/badge/dependencies-none%20(stdlib%20only)-success.svg)]()

---

## 📸 Preview

```text
╭────────────────────────────────────────────────────────────╮
│ Antigravity Usage Monitor                           ● LIVE │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ ✦ GEMINI MODELS                                            │
│   Five Hour Limit Remaining:     97% (refreshes in 3h, 7m) │
│   ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■             2.3M in window │
│                                                            │
│   Weekly Limit Remaining:       99% (refreshes in 6d, 22h) │
│   ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■             2.3M in window │
│                                                            │
│ ✦ CLAUDE AND GPT MODELS                                    │
│   Five Hour Limit Remaining:        100% (Fully refreshed) │
│   ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■                0 in window │
│                                                            │
│   Weekly Limit Remaining:           100% (Fully refreshed) │
│   ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■                0 in window │
│                                                            │
│ ✦ GEMINI 4 ARGON                                           │
│   Gemini 4 Argon Weekly Limit:      100% (Fully refreshed) │
│   ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■                0 in window │
│                                                            │
╰────────────────────────────────────────────────────────────╯
 Refreshes every 2s | Time: 10:11:03 | Quit: Ctrl+C
```

---

## ✨ Features

- ⚡ **Real-Time Quota Tracking**: Matches Antigravity's official tier buckets:
  - **Gemini Models** (5-Hour Rolling Limit & Weekly Limit)
  - **Claude & GPT models** (5-Hour Rolling Limit & Weekly Limit)
  - **Gemini 4 Argon** (Weekly Limit)
- ⏳ **Live Countdown Timers**: Automatically calculates and displays time remaining until your 5-hour and 7-day rate limits fully reset.
- 🎨 **Sleek Segmented UI**: Terminal card with colored block progress bars (Green ➔ Lime ➔ Yellow ➔ Orange ➔ Red) and token breakdown.
- 📌 **Always-on-Top Floating Desktop Widget**: Compact dark-mode desktop card pinned above all windows (`floating.bat` / `floating_widget.py`).
- 🔒 **100% Local & Private**: Reads directly from your local Antigravity transcripts and databases. No API keys, no logins, and zero external network requests.
- 📦 **Zero Dependencies**: Pure Python standard library (`sqlite3`, `json`, `datetime`, `tkinter`). No `pip install` required!

---

## 🖥️ 1. Terminal Monitor

### Windows:
Double-click `usage.bat` or run:
```powershell
.\usage.bat
# or: py usage.py
```

### macOS / Linux:
```bash
chmod +x usage.sh
./usage.sh
# or: python3 usage.py
```

---

## 📌 2. Always-on-Top Floating Desktop Widget

Want a compact card floating in the corner of your screen that stays **on top of Antigravity, VS Code, and browser windows**?

### Windows:
Double-click `floating.bat` (runs in windowed mode with no console window):
```powershell
.\floating.bat
# or: pyw floating_widget.py
```

### macOS / Linux:
```bash
python3 floating_widget.py
```

- **Draggable**: Click and drag the header to position anywhere.
- **Pin / Unpin (📌)**: Toggle Always-on-Top on/off.
- **Collapse (─)**: Collapse to a compact title bar.
- **Close (✕)**: Close widget.

---

## 🔍 How It Works

Google Antigravity stores conversation logs, generation metadata, and token usage locally in:
- `~/.gemini/antigravity/conversations/*.db` (SQLite)
- `~/.gemini/antigravity/brain/<id>/.system_generated/logs/transcript.jsonl`

**Antigravity Usage Monitor** inspects the rolling 5-hour and 7-day time windows to:
1. Aggregate input, output, and prompt-cached tokens per model category.
2. Determine the oldest request in the current rolling window.
3. Compute the exact time remaining until quota refresh.
4. Render in real time every 2 seconds.

---

## 🤝 Contributing

Contributions, feedback, and feature requests are welcome! Feel free to open an issue or submit a pull request.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
