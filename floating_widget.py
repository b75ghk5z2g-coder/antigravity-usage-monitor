#!/usr/bin/env python3
"""
Antigravity Floating Monitor (Always on Top)
Sleek, modern floating desktop widget with multiple switchable styles:
1. 'Cupertino' - Segmented rounded blocks (matching macOS / Antigravity status popup)
2. 'Minimal'   - Ultra-thin smooth continuous gauge lines
3. 'Bento'     - Modular tiled cards with badges
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

# Colors
BG_DARK = "#090d16"
CARD_BG = "#101626"
BORDER_COLOR = "#1e283d"
TEXT_WHITE = "#f8fafc"
TEXT_MUTED = "#94a3b8"
TEXT_DIM = "#64748b"
BLOCK_EMPTY = "#1e293b"

COLOR_RED = "#ef4444"
COLOR_ORANGE = "#f97316"
COLOR_YELLOW = "#f59e0b"
COLOR_LIME = "#84cc16"
COLOR_GREEN = "#22c55e"
COLOR_CYAN = "#38bdf8"
COLOR_PURPLE = "#c084fc"

def get_status_color(pct_used):
    if pct_used >= 70:
        return COLOR_RED
    elif pct_used >= 45:
        return COLOR_YELLOW
    elif pct_used >= 25:
        return COLOR_LIME
    else:
        return COLOR_GREEN

class SleekFloatingWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Antigravity Usage Monitor")
        
        # Hide while setting up geometry
        self.root.withdraw()

        # Window flags
        self.is_pinned = True
        self.current_style = 1 # 1: Cupertino Blocks, 2: Minimal Lines, 3: Bento
        
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.overrideredirect(True)
        
        # Dimensions
        self.width = 350
        self.height = 360
        
        # Position at top-right of primary screen
        screen_w = self.root.winfo_screenwidth()
        x = max(20, screen_w - self.width - 30)
        y = 50
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.root.configure(bg=BORDER_COLOR)

        # Main inner container
        self.container = tk.Frame(self.root, bg=BG_DARK, bd=0)
        self.container.pack(fill="both", expand=True, padx=1, pady=1)

        # Dragging variables
        self._drag_x = 0
        self._drag_y = 0

        self.create_header()
        
        self.content_frame = tk.Frame(self.container, bg=BG_DARK)
        self.content_frame.pack(fill="both", expand=True, padx=14, pady=10)

        # Render initial view
        self.rebuild_view()

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
        self.header = tk.Frame(self.container, bg=CARD_BG, height=36)
        self.header.pack(fill="x", padx=0, pady=0)

        self.header.bind("<Button-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)

        # Title + Live Pulse
        left_box = tk.Frame(self.header, bg=CARD_BG)
        left_box.pack(side="left", padx=10, pady=7)
        left_box.bind("<Button-1>", self.start_drag)
        left_box.bind("<B1-Motion>", self.do_drag)

        dot = tk.Label(left_box, text="●", font=("Segoe UI", 9), fg=COLOR_GREEN, bg=CARD_BG)
        dot.pack(side="left", padx=(0, 5))
        
        title = tk.Label(left_box, text="Antigravity Usage", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=CARD_BG)
        title.pack(side="left")

        # Right control buttons
        btn_close = tk.Label(self.header, text="✕", font=("Segoe UI", 9), fg=TEXT_DIM, bg=CARD_BG, cursor="hand2")
        btn_close.pack(side="right", padx=10)
        btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        self.btn_pin = tk.Label(self.header, text="📌", font=("Segoe UI", 9), fg=TEXT_WHITE, bg=CARD_BG, cursor="hand2")
        self.btn_pin.pack(side="right", padx=6)
        self.btn_pin.bind("<Button-1>", self.toggle_pin)

        # Style Switcher Pill
        self.btn_style = tk.Label(
            self.header, 
            text="Style 1 ▾", 
            font=("Segoe UI", 8, "bold"), 
            fg=COLOR_CYAN, 
            bg="#17223b", 
            padx=6, 
            pady=1, 
            cursor="hand2"
        )
        self.btn_style.pack(side="right", padx=6)
        self.btn_style.bind("<Button-1>", self.cycle_style)

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

    def cycle_style(self, event=None):
        self.current_style = (self.current_style % 3) + 1
        self.btn_style.configure(text=f"Style {self.current_style} ▾")
        if self.current_style == 1:
            self.height = 360
        elif self.current_style == 2:
            self.height = 310
        else:
            self.height = 380
        self.root.geometry(f"{self.width}x{self.height}")
        self.rebuild_view()
        self.refresh_stats()

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

        return [
            {"cat": "Gemini Models", "color": COLOR_CYAN, "name": "Five Hour Limit", "rem": g_5h_rem, "used": g_5h_used, "timer": g_5h_timer, "tok": g_5h_tok},
            {"cat": "Gemini Models", "color": COLOR_CYAN, "name": "Weekly Limit", "rem": g_wk_rem, "used": g_wk_used, "timer": g_wk_timer, "tok": g_wk_tok},
            {"cat": "Claude and GPT", "color": COLOR_ORANGE, "name": "Five Hour Limit", "rem": c_5h_rem, "used": c_5h_used, "timer": c_5h_timer, "tok": c_5h_tok},
            {"cat": "Claude and GPT", "color": COLOR_ORANGE, "name": "Weekly Limit", "rem": c_wk_rem, "used": c_wk_used, "timer": c_wk_timer, "tok": c_wk_tok},
            {"cat": "Gemini 4 Argon", "color": COLOR_PURPLE, "name": "Weekly Limit", "rem": a_wk_rem, "used": a_wk_used, "timer": a_wk_timer, "tok": a_wk_tok},
        ]

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
            return f"{rem_d}d {rem_h}h to reset"
        elif rem_h > 0:
            return f"{rem_h}h {rem_m}m to reset"
        return f"{rem_m}m to reset"

    def rebuild_view(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.row_widgets = []
        data = self.get_data()

        if self.current_style == 1:
            # STYLE 1: Cupertino Segmented Rounded Blocks
            for item in data:
                row_box = tk.Frame(self.content_frame, bg=BG_DARK)
                row_box.pack(fill="x", pady=4)

                top_line = tk.Frame(row_box, bg=BG_DARK)
                top_line.pack(fill="x")

                lbl_name = tk.Label(
                    top_line, 
                    text=f"{item['cat']} ({item['name'].replace(' Limit', '')}):", 
                    font=("Segoe UI", 9, "bold"), 
                    fg=TEXT_WHITE, 
                    bg=BG_DARK
                )
                lbl_name.pack(side="left")

                lbl_info = tk.Label(
                    top_line, 
                    text=f"{item['rem']}% ({item['timer']})", 
                    font=("Segoe UI", 9), 
                    fg=TEXT_MUTED, 
                    bg=BG_DARK
                )
                lbl_info.pack(side="right")

                canvas = tk.Canvas(row_box, height=12, bg=BG_DARK, bd=0, highlightthickness=0)
                canvas.pack(fill="x", pady=(3, 0))

                self.row_widgets.append({"type": "blocks", "info_lbl": lbl_info, "canvas": canvas, "item": item})

        elif self.current_style == 2:
            # STYLE 2: Nordic Minimalist
            for item in data:
                row_box = tk.Frame(self.content_frame, bg=BG_DARK)
                row_box.pack(fill="x", pady=5)

                top_line = tk.Frame(row_box, bg=BG_DARK)
                top_line.pack(fill="x")

                lbl_name = tk.Label(
                    top_line, 
                    text=f"{item['cat'].split()[0]} {item['name'].replace(' Limit', '')}", 
                    font=("Segoe UI", 9, "bold"), 
                    fg=item["color"], 
                    bg=BG_DARK
                )
                lbl_name.pack(side="left")

                lbl_info = tk.Label(
                    top_line, 
                    text=f"{item['rem']}%  ·  {item['timer']}", 
                    font=("Segoe UI", 8), 
                    fg=TEXT_MUTED, 
                    bg=BG_DARK
                )
                lbl_info.pack(side="right")

                canvas = tk.Canvas(row_box, height=4, bg=CARD_BG, bd=0, highlightthickness=0)
                canvas.pack(fill="x", pady=(3, 0))

                self.row_widgets.append({"type": "line", "info_lbl": lbl_info, "canvas": canvas, "item": item})

        elif self.current_style == 3:
            # STYLE 3: Bento HUD Tiles
            categories = ["Gemini Models", "Claude and GPT", "Gemini 4 Argon"]
            for cat in categories:
                cat_items = [d for d in data if d["cat"] == cat]
                if not cat_items:
                    continue
                color = cat_items[0]["color"]
                
                tile = tk.Frame(self.content_frame, bg=CARD_BG, bd=1, relief="solid")
                tile.pack(fill="x", pady=4, ipady=4, ipadx=6)

                h_box = tk.Frame(tile, bg=CARD_BG)
                h_box.pack(fill="x", padx=6, pady=(2, 4))
                
                tk.Label(h_box, text=f"✦ {cat.upper()}", font=("Segoe UI", 8, "bold"), fg=color, bg=CARD_BG).pack(side="left")
                
                for item in cat_items:
                    l_box = tk.Frame(tile, bg=CARD_BG)
                    l_box.pack(fill="x", padx=6, pady=2)
                    
                    sub_title = tk.Label(l_box, text=item['name'].replace(' Limit', ''), font=("Segoe UI", 8), fg=TEXT_WHITE, bg=CARD_BG)
                    sub_title.pack(side="left")

                    lbl_info = tk.Label(l_box, text=f"{item['rem']}%  ·  {item['timer']}", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=CARD_BG)
                    lbl_info.pack(side="right")

                    canvas = tk.Canvas(tile, height=4, bg="#1a2336", bd=0, highlightthickness=0)
                    canvas.pack(fill="x", padx=6, pady=(1, 3))

                    self.row_widgets.append({"type": "line", "info_lbl": lbl_info, "canvas": canvas, "item": item})

    def refresh_stats(self):
        try:
            data = self.get_data()
            for idx, r in enumerate(self.row_widgets):
                if idx < len(data):
                    item = data[idx]
                    r["info_lbl"].configure(
                        text=f"{item['rem']}% ({item['timer']})" if r["type"] == "blocks" else f"{item['rem']}%  ·  {item['timer']}"
                    )
                    
                    canvas = r["canvas"]
                    canvas.delete("all")
                    w = canvas.winfo_width()
                    if w <= 1:
                        w = self.width - 32

                    pct_used = item["used"]
                    color = get_status_color(pct_used)

                    if r["type"] == "blocks":
                        num_blocks = 15
                        gap = 4
                        block_w = max(4, int((w - (gap * (num_blocks - 1))) / num_blocks))
                        block_h = 10
                        
                        filled_blocks = int(round((pct_used / 100.0) * num_blocks))
                        if pct_used > 0 and filled_blocks == 0:
                            filled_blocks = 1

                        for b_i in range(num_blocks):
                            bx1 = b_i * (block_w + gap)
                            bx2 = bx1 + block_w
                            b_fill = color if b_i < filled_blocks else BLOCK_EMPTY
                            canvas.create_rectangle(bx1, 0, bx2, block_h, fill=b_fill, outline="")

                    elif r["type"] == "line":
                        fill_w = max(2, int((pct_used / 100.0) * w))
                        canvas.create_rectangle(0, 0, w, 4, fill=BLOCK_EMPTY, outline="")
                        if pct_used > 0:
                            canvas.create_rectangle(0, 0, fill_w, 4, fill=color, outline="")

        except Exception as e:
            pass

        self.root.after(2000, self.refresh_stats)

def main():
    try:
        app = SleekFloatingWidget()
        app.root.mainloop()
    except Exception as e:
        err_msg = traceback.format_exc()
        try:
            messagebox.showerror("Antigravity Usage Monitor Error", f"Failed to start floating widget:\n\n{err_msg}")
        except Exception:
            print(err_msg, file=sys.stderr)

if __name__ == "__main__":
    main()
