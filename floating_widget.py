#!/usr/bin/env python3
"""
Antigravity Floating Monitor (Always on Top)
Sleek, true-black OLED Bento HUD desktop widget.
"""

import os
import sys
import traceback

# Ensure working directory is this script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import ctypes
from ctypes import c_int, byref, sizeof
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timezone, timedelta

# Import data parsing logic from usage.py
try:
    from usage import parse_events_by_category
except Exception as e:
    parse_events_by_category = lambda: {"gemini": [], "claude_gpt": [], "argon": []}

# Deep OLED Black Theme
BG_BLACK = "#000000"         # True black
HEADER_BG = "#08080a"        # Deep header
TILE_BG = "#0c0d12"          # Bento card background
TILE_BORDER = "#1b1d26"      # Subtle dark border
TRACK_BG = "#161822"         # Progress bar track

TEXT_WHITE = "#ffffff"       # Crisp white
TEXT_MUTED = "#94a3b8"       # Silver text
TEXT_DIM = "#475569"         # Muted labels

# Category Accent Colors
COLOR_GEMINI = "#38bdf8"     # Electric cyan
COLOR_CLAUDE = "#fb923c"     # Warm orange
COLOR_ARGON = "#c084fc"      # Neon purple

# Status Colors
STATUS_GREEN = "#22c55e"
STATUS_YELLOW = "#eab308"
STATUS_ORANGE = "#f97316"
STATUS_RED = "#ef4444"

def get_status_color(pct_used):
    if pct_used >= 70:
        return STATUS_RED
    elif pct_used >= 45:
        return STATUS_YELLOW
    elif pct_used >= 25:
        return STATUS_YELLOW
    else:
        return STATUS_GREEN

class BentoBlackFloatingWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Antigravity Usage Monitor")
        
        # Hide while setting up geometry
        self.root.withdraw()

        # Window flags
        self.is_pinned = True
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.98)
        self.root.overrideredirect(True)
        
        # Dimensions
        self.width = 340
        self.height = 340
        
        # Position at top-right of primary screen
        screen_w = self.root.winfo_screenwidth()
        x = max(20, screen_w - self.width - 24)
        y = 36
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.root.configure(bg=TILE_BORDER)

        # Main inner container
        self.container = tk.Frame(self.root, bg=BG_BLACK, bd=0)
        self.container.pack(fill="both", expand=True, padx=1, pady=1)

        # Dragging variables
        self._drag_x = 0
        self._drag_y = 0

        self.create_header()
        
        self.content_frame = tk.Frame(self.container, bg=BG_BLACK)
        self.content_frame.pack(fill="both", expand=True, padx=12, pady=10)

        # Build Bento Tiles
        self.build_bento_tiles()

        # Update and show
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

        # Apply Windows 11 DWM rounded corners if available
        self.apply_win11_style()

        # Start 2s update loop
        self.refresh_stats()

    def apply_win11_style(self):
        """Enable Windows 11 rounded window corners & dark mode frame via DWM."""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            if hwnd:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, byref(c_int(2)), sizeof(c_int))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(c_int(1)), sizeof(c_int))
        except Exception:
            pass

    def create_header(self):
        self.header = tk.Frame(self.container, bg=HEADER_BG, height=36)
        self.header.pack(fill="x", padx=0, pady=0)

        self.header.bind("<Button-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)

        # Title + Live Pulse
        left_box = tk.Frame(self.header, bg=HEADER_BG)
        left_box.pack(side="left", padx=10, pady=7)
        left_box.bind("<Button-1>", self.start_drag)
        left_box.bind("<B1-Motion>", self.do_drag)

        dot = tk.Label(left_box, text="●", font=("Segoe UI", 9), fg=STATUS_GREEN, bg=HEADER_BG)
        dot.pack(side="left", padx=(0, 6))
        
        title = tk.Label(left_box, text="Antigravity Usage", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=HEADER_BG)
        title.pack(side="left")

        # Right control buttons
        btn_close = tk.Label(self.header, text="✕", font=("Segoe UI", 9), fg=TEXT_DIM, bg=HEADER_BG, cursor="hand2")
        btn_close.pack(side="right", padx=10)
        btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        self.btn_pin = tk.Label(self.header, text="📌", font=("Segoe UI", 9), fg=TEXT_WHITE, bg=HEADER_BG, cursor="hand2")
        self.btn_pin.pack(side="right", padx=6)
        self.btn_pin.bind("<Button-1>", self.toggle_pin)

    def start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() - self._drag_x + event.x
        y = self.root.winfo_y() - self._drag_y + event.y
        self.root.geometry(f"+{x}+{y}")

    def toggle_pin(self, event=None):
        self.is_pinned = not self.is_pinned
        self.root.attributes("-topmost", self.is_pinned)
        self.btn_pin.configure(fg=TEXT_WHITE if self.is_pinned else TEXT_DIM)

    def get_data(self):
        events_by_cat = parse_events_by_category()
        now_utc = datetime.now(timezone.utc)

        # Gemini
        g_evs = events_by_cat.get("gemini", [])
        g_5h = [e for e in g_evs if e[0] >= (now_utc - timedelta(hours=5))]
        g_5h_tok = sum(e[1] for e in g_5h)
        g_5h_used = min(100.0, max(0.0, (g_5h_tok / 75_000_000) * 100)) if g_5h_tok else 0.0
        g_5h_rem = int(round(100.0 - g_5h_used))
        g_5h_timer = self.calc_timer(g_5h, 5, now_utc)

        g_wk = [e for e in g_evs if e[0] >= (now_utc - timedelta(days=7))]
        g_wk_tok = sum(e[1] for e in g_wk)
        g_wk_used = min(100.0, max(0.0, (g_wk_tok / 250_000_000) * 100)) if g_wk_tok else 0.0
        g_wk_rem = int(round(100.0 - g_wk_used))
        g_wk_timer = self.calc_timer(g_wk, 168, now_utc)

        # Claude & GPT
        c_evs = events_by_cat.get("claude_gpt", [])
        c_5h = [e for e in c_evs if e[0] >= (now_utc - timedelta(hours=5))]
        c_5h_tok = sum(e[1] for e in c_5h)
        c_5h_used = min(100.0, max(0.0, (c_5h_tok / 10_000_000) * 100)) if c_5h_tok else 0.0
        c_5h_rem = int(round(100.0 - c_5h_used))
        c_5h_timer = self.calc_timer(c_5h, 5, now_utc)

        c_wk = [e for e in c_evs if e[0] >= (now_utc - timedelta(days=7))]
        c_wk_tok = sum(e[1] for e in c_wk)
        c_wk_used = min(100.0, max(0.0, (c_wk_tok / 50_000_000) * 100)) if c_wk_tok else 0.0
        c_wk_rem = int(round(100.0 - c_wk_used))
        c_wk_timer = self.calc_timer(c_wk, 168, now_utc)

        # Argon
        a_evs = events_by_cat.get("argon", [])
        a_wk = [e for e in a_evs if e[0] >= (now_utc - timedelta(days=7))]
        a_wk_tok = sum(e[1] for e in a_wk)
        a_wk_used = min(100.0, max(0.0, (a_wk_tok / 20_000_000) * 100)) if a_wk_tok else 0.0
        a_wk_rem = int(round(100.0 - a_wk_used))
        a_wk_timer = self.calc_timer(a_wk, 168, now_utc)

        return {
            "gemini": {
                "title": "GEMINI MODELS",
                "color": COLOR_GEMINI,
                "limits": [
                    {"name": "5-Hour Limit", "rem": g_5h_rem, "used": g_5h_used, "timer": g_5h_timer},
                    {"name": "Weekly Limit", "rem": g_wk_rem, "used": g_wk_used, "timer": g_wk_timer}
                ]
            },
            "claude": {
                "title": "CLAUDE AND GPT",
                "color": COLOR_CLAUDE,
                "limits": [
                    {"name": "5-Hour Limit", "rem": c_5h_rem, "used": c_5h_used, "timer": c_5h_timer},
                    {"name": "Weekly Limit", "rem": c_wk_rem, "used": c_wk_used, "timer": c_wk_timer}
                ]
            },
            "argon": {
                "title": "GEMINI 4 ARGON",
                "color": COLOR_ARGON,
                "limits": [
                    {"name": "Weekly Limit", "rem": a_wk_rem, "used": a_wk_used, "timer": a_wk_timer}
                ]
            }
        }

    def calc_timer(self, events, window_hours, now_utc):
        if not events:
            return "Ready"
        oldest_dt = min(e[0] for e in events)
        reset_dt = oldest_dt + timedelta(hours=window_hours)
        rem_sec = max(0, int((reset_dt - now_utc).total_seconds()))
        if rem_sec <= 0:
            return "Ready"
        rem_d = rem_sec // 86400
        rem_h = (rem_sec % 86400) // 3600
        rem_m = (rem_sec % 3600) // 60
        if rem_d > 0:
            return f"{rem_d}d {rem_h}h"
        elif rem_h > 0:
            return f"{rem_h}h {rem_m}m"
        return f"{rem_m}m"

    def build_bento_tiles(self):
        for w in self.content_frame.winfo_children():
            w.destroy()

        self.cards = {}
        sections = [
            ("gemini", COLOR_GEMINI),
            ("claude", COLOR_CLAUDE),
            ("argon", COLOR_ARGON)
        ]

        for sec_key, color in sections:
            card = tk.Frame(self.content_frame, bg=TILE_BG, bd=1, relief="solid", highlightbackground=TILE_BORDER, highlightcolor=TILE_BORDER, highlightthickness=1)
            card.pack(fill="x", pady=4, padx=0, ipadx=4, ipady=4)

            # Card Header
            h_row = tk.Frame(card, bg=TILE_BG)
            h_row.pack(fill="x", padx=8, pady=(4, 6))

            dot = tk.Label(h_row, text="✦", font=("Segoe UI", 9, "bold"), fg=color, bg=TILE_BG)
            dot.pack(side="left", padx=(0, 5))

            lbl_title = tk.Label(h_row, text="", font=("Segoe UI", 8, "bold"), fg=color, bg=TILE_BG)
            lbl_title.pack(side="left")

            rows_data = []
            num_limits = 1 if sec_key == "argon" else 2

            for i in range(num_limits):
                l_row = tk.Frame(card, bg=TILE_BG)
                l_row.pack(fill="x", padx=8, pady=(2, 1))

                lbl_name = tk.Label(l_row, text="", font=("Segoe UI", 8), fg=TEXT_WHITE, bg=TILE_BG)
                lbl_name.pack(side="left")

                lbl_pct = tk.Label(l_row, text="", font=("Segoe UI", 8, "bold"), fg=STATUS_GREEN, bg=TILE_BG)
                lbl_pct.pack(side="right")

                lbl_time = tk.Label(l_row, text="", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=TILE_BG)
                lbl_time.pack(side="right", padx=(0, 6))

                canvas = tk.Canvas(card, height=4, bg=TRACK_BG, bd=0, highlightthickness=0)
                canvas.pack(fill="x", padx=8, pady=(2, 5 if i == num_limits - 1 else 3))

                rows_data.append({
                    "name": lbl_name,
                    "pct": lbl_pct,
                    "time": lbl_time,
                    "canvas": canvas
                })

            self.cards[sec_key] = {
                "title": lbl_title,
                "rows": rows_data
            }

    def refresh_stats(self):
        try:
            data = self.get_data()

            for sec_key, card_widgets in self.cards.items():
                sec_data = data.get(sec_key, {})
                card_widgets["title"].configure(text=sec_data.get("title", ""))

                limits = sec_data.get("limits", [])
                for idx, row in enumerate(card_widgets["rows"]):
                    if idx < len(limits):
                        lim = limits[idx]
                        row["name"].configure(text=lim["name"])
                        row["pct"].configure(text=f"{lim['rem']}%")
                        row["time"].configure(text=f"({lim['timer']})")

                        # Progress Bar
                        canvas = row["canvas"]
                        canvas.delete("all")
                        w = canvas.winfo_width()
                        if w <= 1:
                            w = self.width - 44

                        pct_used = lim["used"]
                        color = get_status_color(pct_used)

                        # Draw track and fill
                        canvas.create_rectangle(0, 0, w, 4, fill=TRACK_BG, outline="")
                        if pct_used > 0:
                            fill_w = max(3, int((pct_used / 100.0) * w))
                            canvas.create_rectangle(0, 0, fill_w, 4, fill=color, outline="")

        except Exception as e:
            pass

        self.root.after(2000, self.refresh_stats)

def main():
    try:
        app = BentoBlackFloatingWidget()
        app.root.mainloop()
    except Exception as e:
        err_msg = traceback.format_exc()
        try:
            messagebox.showerror("Antigravity Usage Monitor Error", f"Failed to start floating widget:\n\n{err_msg}")
        except Exception:
            print(err_msg, file=sys.stderr)

if __name__ == "__main__":
    main()
