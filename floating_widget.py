#!/usr/bin/env python3
"""
Antigravity Floating Mini-Widget (Always on Top)
Draggable, compact, dark-mode desktop widget.
"""

import os
import sys
import time
import tkinter as tk
from datetime import datetime, timezone, timedelta

# Import data parsing logic from usage.py
from usage import parse_events_by_category, LIMIT_CONFIG

class FloatingUsageWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Antigravity Usage")
        
        # Window properties
        self.is_pinned = True
        self.is_compact = False
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True) # Frameless for modern look
        
        # Dimensions
        self.width = 330
        self.height = 250
        
        # Position at top-right of screen by default
        screen_w = self.root.winfo_screenwidth()
        x = screen_w - self.width - 30
        y = 40
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        # Colors
        self.bg_color = "#0f172a"        # Dark slate
        self.card_bg = "#1e293b"         # Card background
        self.border_color = "#334155"    # Subtle border
        self.text_main = "#f8fafc"       # Crisp white
        self.text_dim = "#94a3b8"        # Slate muted
        self.accent_green = "#22c55e"    # Emerald
        self.accent_cyan = "#38bdf8"     # Gemini cyan
        self.accent_orange = "#fb923c"   # Claude orange
        self.accent_purple = "#c084fc"   # Argon purple

        self.root.configure(bg=self.border_color)
        
        # Main inner container with padding for border effect
        self.main_frame = tk.Frame(self.root, bg=self.bg_color, bd=0)
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Dragging variables
        self._drag_start_x = 0
        self._drag_start_y = 0

        self.create_header()
        self.create_body()

        # Update loop
        self.update_stats()

    def create_header(self):
        self.header = tk.Frame(self.main_frame, bg=self.card_bg, height=34)
        self.header.pack(fill="x", padx=0, pady=0)
        
        # Allow dragging window by clicking header
        self.header.bind("<Button-1>", self.on_drag_start)
        self.header.bind("<B1-Motion>", self.on_drag_motion)

        # Title
        title_label = tk.Label(
            self.header, 
            text="● AG Usage Monitor", 
            font=("Segoe UI", 10, "bold"), 
            fg=self.accent_green, 
            bg=self.card_bg
        )
        title_label.pack(side="left", padx=10, pady=6)
        title_label.bind("<Button-1>", self.on_drag_start)
        title_label.bind("<B1-Motion>", self.on_drag_motion)

        # Controls on the right
        btn_close = tk.Label(self.header, text="✕", font=("Segoe UI", 9, "bold"), fg=self.text_dim, bg=self.card_bg, cursor="hand2")
        btn_close.pack(side="right", padx=8)
        btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        self.pin_label = tk.Label(self.header, text="📌", font=("Segoe UI", 9), fg=self.text_main, bg=self.card_bg, cursor="hand2")
        self.pin_label.pack(side="right", padx=6)
        self.pin_label.bind("<Button-1>", self.toggle_pin)

        self.compact_btn = tk.Label(self.header, text="─", font=("Segoe UI", 9, "bold"), fg=self.text_dim, bg=self.card_bg, cursor="hand2")
        self.compact_btn.pack(side="right", padx=6)
        self.compact_btn.bind("<Button-1>", self.toggle_compact)

    def create_body(self):
        self.body_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.body_frame.pack(fill="both", expand=True, padx=12, pady=10)

        # Gemini Section
        self.lbl_gemini_title = tk.Label(self.body_frame, text="GEMINI MODELS", font=("Segoe UI", 8, "bold"), fg=self.accent_cyan, bg=self.bg_color)
        self.lbl_gemini_title.pack(anchor="w")
        
        self.lbl_gemini_5h = tk.Label(self.body_frame, text="5h Limit: 100% (Ready)", font=("Segoe UI", 9), fg=self.text_main, bg=self.bg_color)
        self.lbl_gemini_5h.pack(anchor="w")
        self.bar_gemini_5h = self.create_progress_bar(self.body_frame)

        self.lbl_gemini_wk = tk.Label(self.body_frame, text="Weekly Limit: 100% (Ready)", font=("Segoe UI", 9), fg=self.text_main, bg=self.bg_color)
        self.lbl_gemini_wk.pack(anchor="w", pady=(4, 0))
        self.bar_gemini_wk = self.create_progress_bar(self.body_frame)

        # Claude & GPT Section
        self.lbl_claude_title = tk.Label(self.body_frame, text="CLAUDE & GPT", font=("Segoe UI", 8, "bold"), fg=self.accent_orange, bg=self.bg_color)
        self.lbl_claude_title.pack(anchor="w", pady=(8, 0))
        self.lbl_claude_5h = tk.Label(self.body_frame, text="5h Limit: 100% (Ready)", font=("Segoe UI", 9), fg=self.text_main, bg=self.bg_color)
        self.lbl_claude_5h.pack(anchor="w")
        self.bar_claude_5h = self.create_progress_bar(self.body_frame)

        # Argon Section
        self.lbl_argon_title = tk.Label(self.body_frame, text="GEMINI 4 ARGON", font=("Segoe UI", 8, "bold"), fg=self.accent_purple, bg=self.bg_color)
        self.lbl_argon_title.pack(anchor="w", pady=(8, 0))
        self.lbl_argon_wk = tk.Label(self.body_frame, text="Weekly Limit: 100% (Ready)", font=("Segoe UI", 9), fg=self.text_main, bg=self.bg_color)
        self.lbl_argon_wk.pack(anchor="w")
        self.bar_argon_wk = self.create_progress_bar(self.body_frame)

    def create_progress_bar(self, parent):
        canvas = tk.Canvas(parent, height=5, bg="#334155", bd=0, highlightthickness=0)
        canvas.pack(fill="x", pady=(2, 2))
        return canvas

    def update_progress_bar(self, canvas, pct_used):
        canvas.delete("all")
        w = canvas.winfo_width()
        if w <= 1:
            w = self.width - 24
        fill_w = int((pct_used / 100.0) * w)
        if pct_used > 0 and fill_w < 3:
            fill_w = 3

        if pct_used >= 70:
            color = "#ef4444"
        elif pct_used >= 40:
            color = "#f59e0b"
        elif pct_used >= 15:
            color = "#84cc16"
        else:
            color = "#22c55e"

        canvas.create_rectangle(0, 0, fill_w, 5, fill=color, outline="")

    def on_drag_start(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def on_drag_motion(self, event):
        x = self.root.winfo_x() - self._drag_start_x + event.x
        y = self.root.winfo_y() - self._drag_start_y + event.y
        self.root.geometry(f"+{x}+{y}")

    def toggle_pin(self, event=None):
        self.is_pinned = not self.is_pinned
        self.root.attributes("-topmost", self.is_pinned)
        self.pin_label.configure(fg=self.text_main if self.is_pinned else self.text_dim)

    def toggle_compact(self, event=None):
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.body_frame.pack_forget()
            self.root.geometry(f"{self.width}x34")
            self.compact_btn.configure(text="□")
        else:
            self.body_frame.pack(fill="both", expand=True, padx=12, pady=10)
            self.root.geometry(f"{self.width}x{self.height}")
            self.compact_btn.configure(text="─")

    def update_stats(self):
        try:
            events_by_cat = parse_events_by_category()
            now_utc = datetime.now(timezone.utc)

            # Gemini
            g_evs = events_by_cat.get("gemini", [])
            g_5h = [e for e in g_evs if e[0] >= (now_utc - timedelta(hours=5))]
            g_5h_tok = sum(e[1] for e in g_5h)
            g_5h_used = min(100.0, max(0.0, (g_5h_tok / 75_000_000) * 100)) if g_5h_tok else 0.0
            g_5h_rem = int(round(100.0 - g_5h_used))
            g_5h_timer = self.format_timer(g_5h, 5, now_utc)

            self.lbl_gemini_5h.configure(text=f"5h Limit: {g_5h_rem}% ({g_5h_timer})")
            self.update_progress_bar(self.bar_gemini_5h, g_5h_used)

            g_wk = [e for e in g_evs if e[0] >= (now_utc - timedelta(days=7))]
            g_wk_tok = sum(e[1] for e in g_wk)
            g_wk_used = min(100.0, max(0.0, (g_wk_tok / 250_000_000) * 100)) if g_wk_tok else 0.0
            g_wk_rem = int(round(100.0 - g_wk_used))
            g_wk_timer = self.format_timer(g_wk, 168, now_utc)

            self.lbl_gemini_wk.configure(text=f"Weekly Limit: {g_wk_rem}% ({g_wk_timer})")
            self.update_progress_bar(self.bar_gemini_wk, g_wk_used)

            # Claude
            c_evs = events_by_cat.get("claude_gpt", [])
            c_5h = [e for e in c_evs if e[0] >= (now_utc - timedelta(hours=5))]
            c_5h_tok = sum(e[1] for e in c_5h)
            c_5h_used = min(100.0, max(0.0, (c_5h_tok / 10_000_000) * 100)) if c_5h_tok else 0.0
            c_5h_rem = int(round(100.0 - c_5h_used))
            c_5h_timer = self.format_timer(c_5h, 5, now_utc)

            self.lbl_claude_5h.configure(text=f"5h Limit: {c_5h_rem}% ({c_5h_timer})")
            self.update_progress_bar(self.bar_claude_5h, c_5h_used)

            # Argon
            a_evs = events_by_cat.get("argon", [])
            a_wk = [e for e in a_evs if e[0] >= (now_utc - timedelta(days=7))]
            a_wk_tok = sum(e[1] for e in a_wk)
            a_wk_used = min(100.0, max(0.0, (a_wk_tok / 20_000_000) * 100)) if a_wk_tok else 0.0
            a_wk_rem = int(round(100.0 - a_wk_used))
            a_wk_timer = self.format_timer(a_wk, 168, now_utc)

            self.lbl_argon_wk.configure(text=f"Weekly Limit: {a_wk_rem}% ({a_wk_timer})")
            self.update_progress_bar(self.bar_argon_wk, a_wk_used)

        except Exception as e:
            pass

        # Re-schedule every 2 seconds
        self.root.after(2000, self.update_stats)

    def format_timer(self, events, window_hours, now_utc):
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
            return f"refreshes in {rem_d}d, {rem_h}h"
        elif rem_h > 0:
            return f"refreshes in {rem_h}h, {rem_m}m"
        return f"refreshes in {rem_m}m"

def main():
    app = FloatingUsageWidget()
    app.root.mainloop()

if __name__ == "__main__":
    main()
