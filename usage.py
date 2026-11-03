#!/usr/bin/env python3
"""
Antigravity Terminal Usage Monitor
Real-time tracking of Antigravity Quota Tiers & Limits:
- Gemini Models (Weekly & 5-Hour Limits)
- Claude & GPT models (Weekly & 5-Hour Limits)
- Gemini 4 Argon (Weekly Limit)
"""

import os
import re
import sys
import glob
import json
import time
import sqlite3
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

APP_DATA_DIR = os.path.expanduser(r"~/.gemini/antigravity")
CONVERSATIONS_DIR = os.path.join(APP_DATA_DIR, "conversations")
BRAIN_DIR = os.path.join(APP_DATA_DIR, "brain")

# Default Tier Baselines (Tokens per window for percentage calibration)
LIMIT_CONFIG = {
    "gemini": {
        "title": "Gemini Models",
        "color_code": "\033[38;2;56;189;248m", # Cyan/Sky blue
        "icon": "✦",
        "limits": {
            "5h": {"name": "Five Hour Limit Remaining", "hours": 5, "base_tokens": 75_000_000},
            "weekly": {"name": "Weekly Limit Remaining", "hours": 168, "base_tokens": 250_000_000}
        }
    },
    "claude_gpt": {
        "title": "Claude and GPT models",
        "color_code": "\033[38;2;251;146;60m", # Orange
        "icon": "✦",
        "limits": {
            "5h": {"name": "Five Hour Limit Remaining", "hours": 5, "base_tokens": 10_000_000},
            "weekly": {"name": "Weekly Limit Remaining", "hours": 168, "base_tokens": 50_000_000}
        }
    },
    "argon": {
        "title": "Gemini 4 Argon",
        "color_code": "\033[38;2;192;132;252m", # Purple
        "icon": "✦",
        "limits": {
            "weekly": {"name": "Gemini 4 Argon Weekly Limit", "hours": 168, "base_tokens": 20_000_000}
        }
    }
}

# ANSI Color Codes
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_BORDER = "\033[38;2;71;85;105m"     # Slate border
C_LABEL = "\033[38;2;241;245;249m"    # Bright white
C_MUTED = "\033[38;2;148;163;184m"    # Gray text
C_DARK_BLOCK = "\033[38;2;40;48;64m"  # Unused block

# Usage-based block colors
C_RED = "\033[38;2;239;68;68m"       # > 70% used
C_ORANGE = "\033[38;2;249;115;22m"   # 50 - 70% used
C_YELLOW = "\033[38;2;234;179;8m"    # 30 - 50% used
C_LIME = "\033[38;2;132;204;22m"     # 15 - 30% used
C_GREEN = "\033[38;2;34;197;94m"     # < 15% used

def visible_len(text: str) -> int:
    """Return visible string length ignoring ANSI escape codes."""
    return len(re.sub(r"\033\[[0-9;?]*[a-zA-Z]", "", text))

def get_color_for_used_pct(pct_used: float) -> str:
    if pct_used >= 70:
        return C_RED
    elif pct_used >= 45:
        return C_ORANGE
    elif pct_used >= 25:
        return C_YELLOW
    elif pct_used >= 10:
        return C_LIME
    else:
        return C_GREEN

def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)

def classify_model(raw_name: str) -> str:
    low = (raw_name or "").lower()
    if "argon" in low:
        return "argon"
    elif "claude" in low or "gpt" in low:
        return "claude_gpt"
    else:
        return "gemini"

def parse_events_by_category():
    events = {"gemini": [], "claude_gpt": [], "argon": []}
    db_files = glob.glob(os.path.join(CONVERSATIONS_DIR, "*.db"))

    for db_path in db_files:
        cid = os.path.splitext(os.path.basename(db_path))[0]
        step_to_cat = {}
        fallback_cat = "gemini"

        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT idx, data FROM gen_metadata ORDER BY idx ASC")
            for idx, data in cur.fetchall():
                pos = data.find(b"last_step_index")
                m_resp = re.findall(rb'(gemini-[a-zA-Z0-9.\-_]+|claude-[a-zA-Z0-9.\-_]+|gpt-[a-zA-Z0-9.\-_]+)', data)
                model_raw = m_resp[0].decode("ascii", errors="ignore") if m_resp else "gemini-3.8-flash-n"
                cat = classify_model(model_raw)
                fallback_cat = cat

                if pos != -1 and pos + 16 < len(data):
                    length = data[pos + 16]
                    val_str = data[pos + 17 : pos + 17 + length].decode("ascii", errors="ignore")
                    if val_str.isdigit():
                        step_to_cat[int(val_str) + 1] = cat
            con.close()
        except Exception:
            pass

        t_path = os.path.join(BRAIN_DIR, cid, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(t_path):
            continue

        try:
            with open(t_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue

                    st = d.get("step_index")
                    inp = d.get("input_tokens", 0) or 0
                    out = d.get("output_tokens", 0) or 0
                    cached = d.get("cache_read_tokens", 0) or 0
                    created_at = d.get("created_at", "")

                    if (inp or out or cached) and created_at:
                        cat = step_to_cat.get(st, fallback_cat)
                        try:
                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            events[cat].append((dt, inp + out, cached))
                        except Exception:
                            pass
        except Exception:
            pass

    return events

def render_terminal():
    events_by_cat = parse_events_by_category()
    now_utc = datetime.now(timezone.utc)

    box_width = 62
    total_blocks = 15

    lines = ["\033[H"]

    # Header
    top_border = f"{C_BORDER}╭{'─' * (box_width - 2)}╮{C_RESET}"
    lines.append(top_border)

    title_left = f" {C_BOLD}{C_LABEL}Antigravity Usage Monitor{C_RESET}"
    title_right = f"{C_GREEN}● LIVE{C_RESET} "
    gap_title = box_width - 2 - visible_len(title_left) - visible_len(title_right)
    lines.append(f"{C_BORDER}│{C_RESET}{title_left}{' ' * gap_title}{title_right}{C_BORDER}│{C_RESET}")
    lines.append(f"{C_BORDER}├{'─' * (box_width - 2)}┤{C_RESET}")

    categories = ["gemini", "claude_gpt", "argon"]

    for c_idx, cat_key in enumerate(categories):
        cfg = LIMIT_CONFIG[cat_key]
        evs = events_by_cat.get(cat_key, [])

        # Category Header
        lines.append(f"{C_BORDER}│{' ' * (box_width - 2)}│{C_RESET}")
        cat_title_str = f" {cfg['color_code']}{cfg['icon']} {C_BOLD}{cfg['title'].upper()}{C_RESET}"
        gap_cat = box_width - 2 - visible_len(cat_title_str)
        lines.append(f"{C_BORDER}│{C_RESET}{cat_title_str}{' ' * gap_cat}{C_BORDER}│{C_RESET}")

        for lim_key, lim_cfg in cfg["limits"].items():
            hours = lim_cfg["hours"]
            base_tokens = lim_cfg["base_tokens"]
            lim_name = lim_cfg["name"]
            cutoff = now_utc - timedelta(hours=hours)

            # Filter events in window
            win_events = [e for e in evs if e[0] >= cutoff]
            used_tokens = sum(e[1] for e in win_events)

            # Percentage calculation
            if used_tokens > 0:
                pct_used = min(100.0, max(1.0, (used_tokens / base_tokens) * 100))
                pct_remaining = int(round(100.0 - pct_used))
                if pct_remaining < 0:
                    pct_remaining = 0
            else:
                pct_used = 0.0
                pct_remaining = 100

            # Countdown string
            if win_events:
                oldest_dt = min(e[0] for e in win_events)
                reset_dt = oldest_dt + timedelta(hours=hours)
                rem_sec = max(0, int((reset_dt - now_utc).total_seconds()))
                rem_d = rem_sec // 86400
                rem_h = (rem_sec % 86400) // 3600
                rem_m = (rem_sec % 3600) // 60

                if rem_d > 0:
                    timer_str = f"refreshes in {rem_d}d, {rem_h}h"
                elif rem_h > 0:
                    timer_str = f"refreshes in {rem_h}h, {rem_m}m"
                else:
                    timer_str = f"refreshes in {rem_m}m"
            else:
                timer_str = "Fully refreshed"

            # Block representation
            filled_count = int(round((pct_used / 100.0) * total_blocks))
            if pct_used > 0 and filled_count == 0:
                filled_count = 1

            bar_color = get_color_for_used_pct(pct_used)
            blocks = []
            for b_i in range(total_blocks):
                if b_i < filled_count:
                    blocks.append(f"{bar_color}■{C_RESET}")
                else:
                    blocks.append(f"{C_DARK_BLOCK}■{C_RESET}")
            blocks_str = " ".join(blocks)

            # Line 1: Limit name + Remaining % + timer
            left_1 = f"   {lim_name}:"
            pct_formatted = f"{pct_remaining}%"
            # Highlight remaining in green/yellow/red
            if pct_remaining >= 70:
                pct_color = C_GREEN
            elif pct_remaining >= 40:
                pct_color = C_YELLOW
            else:
                pct_color = C_RED

            right_1 = f"{pct_color}{C_BOLD}{pct_formatted}{C_RESET} {C_MUTED}({timer_str}){C_RESET} "
            gap_1 = box_width - 2 - visible_len(left_1) - visible_len(right_1)
            if gap_1 < 1:
                gap_1 = 1
            line1 = f"{C_BORDER}│{C_RESET}{C_LABEL}{left_1}{C_RESET}{' ' * gap_1}{right_1}{C_BORDER}│{C_RESET}"
            lines.append(line1)

            # Line 2: Segmented blocks + token details
            left_2 = f"   {blocks_str}"
            tok_details = f"{format_tokens(used_tokens)} in window "
            gap_2 = box_width - 2 - visible_len(left_2) - visible_len(tok_details)
            if gap_2 < 1:
                gap_2 = 1
            line2 = f"{C_BORDER}│{C_RESET}{left_2}{' ' * gap_2}{C_MUTED}{tok_details}{C_RESET}{C_BORDER}│{C_RESET}"
            lines.append(line2)

            # Slight gap between limits within same category
            if lim_key != list(cfg["limits"].keys())[-1]:
                lines.append(f"{C_BORDER}│{' ' * (box_width - 2)}│{C_RESET}")

    lines.append(f"{C_BORDER}│{' ' * (box_width - 2)}│{C_RESET}")
    bottom_border = f"{C_BORDER}╰{'─' * (box_width - 2)}╯{C_RESET}"
    lines.append(bottom_border)

    local_time = datetime.now().strftime("%H:%M:%S")
    footer = f" {C_MUTED}Refreshes every 2s | Time: {local_time} | Quit: Ctrl+C{C_RESET}"
    lines.append(footer)

    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()

def main():
    os.system("cls" if os.name == "nt" else "clear")
    try:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        while True:
            render_terminal()
            time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
        print(f"{C_MUTED}Usage Monitor stopped.{C_RESET}")

if __name__ == "__main__":
    main()
