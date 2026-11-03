#!/usr/bin/env python3
"""
Antigravity Real-Time Model Usage Tracker
Lightweight, zero-dependency real-time usage monitor for Google Antigravity.
"""

import os
import re
import sys
import glob
import json
import sqlite3
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

PORT = 7890
HOST = "127.0.0.1"

APP_DATA_DIR = os.path.expanduser(r"~/.gemini/antigravity")
CONVERSATIONS_DIR = os.path.join(APP_DATA_DIR, "conversations")
BRAIN_DIR = os.path.join(APP_DATA_DIR, "brain")
SUMMARIES_DB = os.path.join(APP_DATA_DIR, "conversation_summaries.db")

MODEL_DISPLAY_NAMES = {
    "gemini-3.8-flash-n": "Gemini 3.8 Flash (Normal)",
    "gemini-3.8-flash-medium": "Gemini 3.8 Flash (Medium)",
    "gemini-3.8-flash-high": "Gemini 3.8 Flash (High)",
    "gemini-3.7-flash": "Gemini 3.7 Flash",
    "gemini-3.7-flash-medium": "Gemini 3.7 Flash (Medium)",
    "claude-sonnet-4-6": "Claude 3.7 Sonnet (Hybrid/Thinking)",
    "claude-3-5-sonnet": "Claude 3.5 Sonnet",
    "claude-3-7-sonnet": "Claude 3.7 Sonnet",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini"
}

def clean_model_name(raw_name: str) -> str:
    if not raw_name:
        return "Unknown Model"
    return MODEL_DISPLAY_NAMES.get(raw_name, raw_name)

def classify_model(raw_name: str) -> str:
    low = (raw_name or "").lower()
    if "argon" in low:
        return "argon"
    elif "claude" in low or "gpt" in low:
        return "claude_gpt"
    else:
        return "gemini"

def get_conversation_metadata():
    titles = {}
    active_id = None
    if not os.path.exists(SUMMARIES_DB):
        return titles, active_id
    try:
        con = sqlite3.connect(f"file:{SUMMARIES_DB}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("SELECT conversation_id, title, last_modified_time FROM conversation_summaries ORDER BY last_modified_time DESC")
        rows = cur.fetchall()
        if rows:
            active_id = rows[0][0]
        for cid, title, _ in rows:
            titles[cid] = title or "Untitled Conversation"
        con.close()
    except Exception:
        pass
    return titles, active_id

def compute_model_stats(events):
    summary = {}
    totals = {"requests": 0, "input": 0, "output": 0, "cache": 0, "total": 0}
    for e in events:
        m = e["model"]
        if m not in summary:
            summary[m] = {
                "name": m,
                "requests": 0,
                "input": 0,
                "output": 0,
                "cache": 0,
                "total": 0,
                "last_used": e["timestamp"]
            }
        summary[m]["requests"] += 1
        summary[m]["input"] += e["input"]
        summary[m]["output"] += e["output"]
        summary[m]["cache"] += e["cache"]
        summary[m]["total"] += e["total"]
        if e["timestamp"] > summary[m]["last_used"]:
            summary[m]["last_used"] = e["timestamp"]

        totals["requests"] += 1
        totals["input"] += e["input"]
        totals["output"] += e["output"]
        totals["cache"] += e["cache"]
        totals["total"] += e["total"]

    models_list = sorted(summary.values(), key=lambda x: x["total"], reverse=True)
    return totals, models_list

def compute_quota_tiers(all_events):
    now_utc = datetime.now(timezone.utc)
    tiers = {
        "gemini": {
            "title": "Gemini Models",
            "icon": "✦",
            "color": "#38bdf8",
            "limits": [
                {"name": "Five Hour Limit Remaining", "hours": 5, "base_tokens": 75_000_000},
                {"name": "Weekly Limit Remaining", "hours": 168, "base_tokens": 250_000_000}
            ]
        },
        "claude_gpt": {
            "title": "Claude and GPT models",
            "icon": "✦",
            "color": "#fb923c",
            "limits": [
                {"name": "Five Hour Limit Remaining", "hours": 5, "base_tokens": 10_000_000},
                {"name": "Weekly Limit Remaining", "hours": 168, "base_tokens": 50_000_000}
            ]
        },
        "argon": {
            "title": "Gemini 4 Argon",
            "icon": "✦",
            "color": "#c084fc",
            "limits": [
                {"name": "Gemini 4 Argon Weekly Limit", "hours": 168, "base_tokens": 20_000_000}
            ]
        }
    }

    tier_results = []

    for cat_key, t_cfg in tiers.items():
        cat_events = []
        for e in all_events:
            if classify_model(e.get("raw_model", "")) == cat_key and e.get("timestamp"):
                try:
                    dt = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                    cat_events.append((dt, e["total"]))
                except Exception:
                    pass

        limit_items = []
        for lim in t_cfg["limits"]:
            hours = lim["hours"]
            base = lim["base_tokens"]
            cutoff = now_utc - timedelta(hours=hours)
            win_events = [ev for ev in cat_events if ev[0] >= cutoff]
            used_tokens = sum(ev[1] for ev in win_events)

            if used_tokens > 0:
                pct_used = min(100.0, max(1.0, (used_tokens / base) * 100))
                pct_rem = int(round(100.0 - pct_used))
            else:
                pct_used = 0.0
                pct_rem = 100

            if win_events:
                oldest_dt = min(ev[0] for ev in win_events)
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

            limit_items.append({
                "name": lim["name"],
                "remaining_pct": pct_rem,
                "used_pct": pct_used,
                "used_tokens": used_tokens,
                "timer": timer_str
            })

        tier_results.append({
            "key": cat_key,
            "title": t_cfg["title"],
            "color": t_cfg["color"],
            "limits": limit_items
        })

    return tier_results

def parse_all_usage():
    titles, active_id = get_conversation_metadata()
    all_events = []
    conversations_summary = {}

    db_files = glob.glob(os.path.join(CONVERSATIONS_DIR, "*.db"))
    
    for db_path in db_files:
        cid = os.path.splitext(os.path.basename(db_path))[0]
        convo_title = titles.get(cid, cid[:8] + "...")
        
        step_to_model = {}
        fallback_model = "gemini-3.8-flash-n"
        
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT idx, data FROM gen_metadata ORDER BY idx ASC")
            for idx, data in cur.fetchall():
                pos = data.find(b"last_step_index")
                m_resp = re.findall(rb'(gemini-[a-zA-Z0-9.\-_]+|claude-[a-zA-Z0-9.\-_]+|gpt-[a-zA-Z0-9.\-_]+)', data)
                model_name = m_resp[0].decode("ascii", errors="ignore") if m_resp else fallback_model
                fallback_model = model_name
                
                if pos != -1 and pos + 16 < len(data):
                    length = data[pos + 16]
                    val_str = data[pos + 17 : pos + 17 + length].decode("ascii", errors="ignore")
                    if val_str.isdigit():
                        resp_step = int(val_str) + 1
                        step_to_model[resp_step] = model_name
            con.close()
        except Exception:
            pass

        t_path = os.path.join(BRAIN_DIR, cid, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(t_path):
            continue

        convo_stats = {
            "id": cid,
            "title": convo_title,
            "requests": 0,
            "input": 0,
            "output": 0,
            "cache": 0,
            "total": 0,
            "models": set(),
            "last_active": "",
            "is_active": (cid == active_id)
        }

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
                    
                    if inp or out or cached:
                        model_raw = step_to_model.get(st, fallback_model)
                        model_name = clean_model_name(model_raw)
                        step_total = inp + out + cached

                        convo_stats["requests"] += 1
                        convo_stats["input"] += inp
                        convo_stats["output"] += out
                        convo_stats["cache"] += cached
                        convo_stats["total"] += step_total
                        convo_stats["models"].add(model_name)
                        if created_at > convo_stats["last_active"]:
                            convo_stats["last_active"] = created_at

                        all_events.append({
                            "timestamp": created_at,
                            "conversation_id": cid,
                            "conversation_title": convo_title,
                            "raw_model": model_raw,
                            "model": model_name,
                            "input": inp,
                            "output": out,
                            "cache": cached,
                            "total": step_total
                        })
        except Exception:
            pass

        if convo_stats["requests"] > 0:
            convo_stats["models"] = list(convo_stats["models"])
            conversations_summary[cid] = convo_stats

    # Sort events descending
    all_events.sort(key=lambda x: x["timestamp"], reverse=True)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_events = [e for e in all_events if e["timestamp"].startswith(today_str)]
    active_events = [e for e in all_events if e["conversation_id"] == active_id]

    totals_all, models_all = compute_model_stats(all_events)
    totals_today, models_today = compute_model_stats(today_events)
    totals_active, models_active = compute_model_stats(active_events)

    quota_tiers = compute_quota_tiers(all_events)

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "active_conversation_id": active_id,
        "quota_tiers": quota_tiers,
        "views": {
            "all": {
                "totals": totals_all,
                "models": models_all
            },
            "today": {
                "totals": totals_today,
                "models": models_today
            },
            "active": {
                "totals": totals_active,
                "models": models_active
            }
        },
        "conversations": sorted(conversations_summary.values(), key=lambda c: c["last_active"], reverse=True),
        "recent_events": all_events[:40]
    }

HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity Real-Time Model Usage Tracker</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #101626;
      --card-border: #1e283d;
      --card-hover: #172138;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --primary: #3b82f6;
      --primary-light: #60a5fa;
      --accent-gemini: #38bdf8;
      --accent-claude: #f97316;
      --accent-green: #10b981;
      --accent-purple: #c084fc;
      --bar-bg: #1e293b;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    body {
      background-color: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 24px;
      line-height: 1.5;
    }
    .container {
      max-width: 1320px;
      margin: 0 auto;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }
    .header-title {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .logo-badge {
      background: linear-gradient(135deg, #2563eb, #8b5cf6);
      color: white;
      padding: 10px 16px;
      border-radius: 12px;
      font-weight: 800;
      font-size: 18px;
      letter-spacing: 0.5px;
      box-shadow: 0 4px 18px rgba(37, 99, 235, 0.45);
    }
    h1 {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .live-status {
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.35);
      padding: 8px 16px;
      border-radius: 9999px;
      font-size: 13px;
      color: #34d399;
      font-weight: 600;
    }
    .pulse-dot {
      width: 10px;
      height: 10px;
      background: #10b981;
      border-radius: 50%;
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { transform: scale(1.05); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .controls-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 12px;
    }
    .pill-filters {
      display: flex;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 4px;
      gap: 4px;
    }
    .pill-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 18px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .pill-btn:hover {
      color: var(--text);
    }
    .pill-btn.active {
      background: var(--primary);
      color: white;
      box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
    }
    .refresh-info {
      font-size: 13px;
      color: var(--text-dim);
    }

    /* Section Headers */
    .section-title {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    /* Quota Tiers Grid */
    .tiers-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }
    .tier-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      position: relative;
    }
    .tier-header {
      font-size: 15px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .tier-limit-row {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .tier-limit-top {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
    }
    .tier-timer {
      font-size: 12px;
      color: var(--text-dim);
    }

    /* Stat Cards */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      position: relative;
      overflow: hidden;
      transition: border-color 0.2s;
    }
    .stat-card:hover {
      border-color: #2b3954;
    }
    .stat-card::after {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 3px;
      background: var(--card-border);
    }
    .stat-card.c-primary::after { background: var(--primary); }
    .stat-card.c-accent::after { background: var(--accent-gemini); }
    .stat-card.c-green::after { background: var(--accent-green); }
    .stat-card.c-purple::after { background: var(--accent-purple); }
    .stat-label {
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.6px;
    }
    .stat-val {
      font-size: 26px;
      font-weight: 700;
      color: var(--text);
      font-feature-settings: "tnum";
    }
    .stat-sub {
      font-size: 12px;
      color: var(--text-dim);
    }

    /* Models Cards */
    .models-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 16px;
      margin-bottom: 30px;
    }
    .model-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      transition: transform 0.15s, border-color 0.15s;
    }
    .model-card:hover {
      border-color: #2d3b58;
      transform: translateY(-2px);
    }
    .model-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
    }
    .model-name {
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
    }
    .model-badge {
      font-size: 12px;
      padding: 3px 9px;
      border-radius: 9999px;
      font-weight: 700;
      white-space: nowrap;
    }
    .badge-gemini {
      background: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.35);
    }
    .badge-claude {
      background: rgba(249, 115, 22, 0.15);
      color: #fb923c;
      border: 1px solid rgba(249, 115, 22, 0.35);
    }
    .badge-other {
      background: rgba(192, 132, 252, 0.15);
      color: #c084fc;
      border: 1px solid rgba(192, 132, 252, 0.35);
    }
    .token-breakdown-row {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      color: var(--text-muted);
      padding: 5px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .token-breakdown-row:last-child {
      border-bottom: none;
    }
    .token-val {
      font-weight: 700;
      color: var(--text);
      font-feature-settings: "tnum";
    }

    /* Mini Progress Bar */
    .bar-container {
      width: 100%;
      height: 7px;
      background: var(--bar-bg);
      border-radius: 4px;
      overflow: hidden;
      display: flex;
      margin-top: 5px;
    }
    .bar-segment {
      height: 100%;
      transition: width 0.3s;
    }
    .bar-input { background: #3b82f6; }
    .bar-output { background: #10b981; }
    .bar-cache { background: #a855f7; }

    /* Tables */
    .tables-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 1024px) {
      .tables-grid { grid-template-columns: 1fr; }
    }
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 20px;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      text-align: left;
    }
    th {
      color: var(--text-dim);
      font-weight: 700;
      padding: 10px 12px;
      border-bottom: 1px solid var(--card-border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.6px;
    }
    td {
      padding: 11px 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-muted);
    }
    tr:hover td {
      background: var(--card-hover);
      color: var(--text);
    }
    .convo-title {
      font-weight: 600;
      color: var(--text);
      max-width: 240px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .active-convo-pill {
      font-size: 10px;
      background: rgba(16, 185, 129, 0.2);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
      padding: 1px 6px;
      border-radius: 4px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .event-pill {
      display: inline-block;
      font-size: 11px;
      padding: 3px 7px;
      border-radius: 5px;
      background: #1e293b;
      color: var(--text);
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-title">
        <div class="logo-badge">AG</div>
        <div>
          <h1>Antigravity Real-Time Model Usage</h1>
          <p style="font-size: 13px; color: var(--text-muted);">Real-time model & token usage monitoring</p>
        </div>
      </div>
      <div style="display: flex; gap: 10px; align-items: center;">
        <button onclick="togglePiP()" style="background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4); color: #60a5fa; padding: 7px 14px; border-radius: 9999px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px;">
          <span>📌</span> <span>Pin on Top (PiP)</span>
        </button>
        <div class="live-status">
          <div class="pulse-dot"></div>
          <span>LIVE (Updates every 2s)</span>
        </div>
      </div>
    </header>

    <!-- Quota Tiers Section -->
    <div class="section-title">
      <span>Antigravity Quota Tiers & Limits</span>
    </div>
    <div class="tiers-grid" id="tiers-container">
      <!-- Injected by JS -->
    </div>

    <div class="controls-row">
      <div class="pill-filters">
        <button class="pill-btn active" id="btn-all" onclick="setFilter('all')">All Time</button>
        <button class="pill-btn" id="btn-today" onclick="setFilter('today')">Today</button>
        <button class="pill-btn" id="btn-active" onclick="setFilter('active')">Active Session</button>
      </div>
      <div class="refresh-info" id="last-updated">Updated: ...</div>
    </div>

    <!-- Top Total Metric Cards -->
    <div class="stats-grid">
      <div class="stat-card c-primary">
        <div class="stat-label">Total Requests</div>
        <div class="stat-val" id="total-requests">0</div>
        <div class="stat-sub">Total model invocations</div>
      </div>
      <div class="stat-card c-accent">
        <div class="stat-label">Input Tokens</div>
        <div class="stat-val" id="total-input">0</div>
        <div class="stat-sub">Context & user prompts</div>
      </div>
      <div class="stat-card c-green">
        <div class="stat-label">Output Tokens</div>
        <div class="stat-val" id="total-output">0</div>
        <div class="stat-sub">Generated responses & tools</div>
      </div>
      <div class="stat-card c-purple">
        <div class="stat-label">Cache Read Tokens</div>
        <div class="stat-val" id="total-cache">0</div>
        <div class="stat-sub">Saved via prompt caching</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Grand Total Tokens</div>
        <div class="stat-val" id="grand-total">0</div>
        <div class="stat-sub">Input + Output + Cache</div>
      </div>
    </div>

    <!-- Per Model Breakdown -->
    <div class="section-title">
      <span>Usage by Model</span>
    </div>
    <div class="models-grid" id="models-container">
      <!-- Injected by JS -->
    </div>

    <!-- Tables Grid -->
    <div class="tables-grid">
      <!-- Conversations -->
      <div class="table-container">
        <div class="section-title" style="margin-bottom: 14px;">
          <span>Conversations & Tasks</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Conversation Title</th>
              <th>Calls</th>
              <th>Input</th>
              <th>Output</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody id="convos-tbody">
            <!-- Injected by JS -->
          </tbody>
        </table>
      </div>

      <!-- Recent Live Events -->
      <div class="table-container">
        <div class="section-title" style="margin-bottom: 14px;">
          <span>Recent Model Activity</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Model</th>
              <th>Tokens (In / Out / Cache)</th>
              <th>Conversation</th>
            </tr>
          </thead>
          <tbody id="events-tbody">
            <!-- Injected by JS -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    let currentFilter = 'all';
    let rawData = null;

    function formatNumber(num) {
      if (!num && num !== 0) return '0';
      return num.toLocaleString('en-US');
    }

    function formatTime(isoStr) {
      if (!isoStr) return '-';
      try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      } catch (e) {
        return isoStr;
      }
    }

    function setFilter(filter) {
      currentFilter = filter;
      document.querySelectorAll('.pill-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.getElementById('btn-' + filter);
      if (activeBtn) activeBtn.classList.add('active');
      if (rawData) render(rawData);
    }

    function getBadgeClass(name) {
      const lower = name.toLowerCase();
      if (lower.includes('gemini')) return 'badge-gemini';
      if (lower.includes('claude')) return 'badge-claude';
      return 'badge-other';
    }

    async function fetchUsage() {
      try {
        const res = await fetch('/api/usage');
        if (!res.ok) return;
        const data = await res.json();
        rawData = data;
        render(data);
      } catch (e) {
        console.error('Fetch error:', e);
      }
    }

    function render(data) {
      document.getElementById('last-updated').textContent = 'Last synced: ' + new Date().toLocaleTimeString('en-US', { hour12: false });

      // Render Quota Tiers
      const tiersContainer = document.getElementById('tiers-container');
      tiersContainer.innerHTML = '';
      (data.quota_tiers || []).forEach(tier => {
        const card = document.createElement('div');
        card.className = 'tier-card';
        let limitsHtml = '';
        tier.limits.forEach(lim => {
          const color = lim.remaining_pct >= 70 ? '#22c55e' : (lim.remaining_pct >= 40 ? '#f59e0b' : '#ef4444');
          limitsHtml += `
            <div class="tier-limit-row">
              <div class="tier-limit-top">
                <span style="font-weight:600;">${lim.name}</span>
                <span style="font-weight:700; color:${color};">${lim.remaining_pct}%</span>
              </div>
              <div class="tier-timer">${lim.timer}</div>
              <div class="bar-container">
                <div class="bar-segment" style="width:${lim.used_pct}%; background:${color};"></div>
              </div>
            </div>
          `;
        });

        card.innerHTML = `
          <div class="tier-header" style="color:${tier.color};">
            <span>✦</span> <span>${tier.title}</span>
          </div>
          ${limitsHtml}
        `;
        tiersContainer.appendChild(card);
      });

      const view = data.views[currentFilter] || data.views['all'];
      const totals = view.totals;
      const models = view.models;

      // Top Cards
      document.getElementById('total-requests').textContent = formatNumber(totals.requests);
      document.getElementById('total-input').textContent = formatNumber(totals.input);
      document.getElementById('total-output').textContent = formatNumber(totals.output);
      document.getElementById('total-cache').textContent = formatNumber(totals.cache);
      document.getElementById('grand-total').textContent = formatNumber(totals.total);

      // Models Cards
      const modelsContainer = document.getElementById('models-container');
      modelsContainer.innerHTML = '';

      if (!models || models.length === 0) {
        modelsContainer.innerHTML = '<div style="color:var(--text-dim); padding:24px;">No requests recorded for the selected filter.</div>';
      } else {
        models.forEach(m => {
          const inPct = m.total ? ((m.input / m.total) * 100).toFixed(1) : 0;
          const outPct = m.total ? ((m.output / m.total) * 100).toFixed(1) : 0;
          const cachePct = m.total ? ((m.cache / m.total) * 100).toFixed(1) : 0;

          const card = document.createElement('div');
          card.className = 'model-card';
          card.innerHTML = `
            <div class="model-header">
              <div>
                <div class="model-name">${m.name}</div>
                <div style="font-size:12px; color:var(--text-dim); margin-top:2px;">Last call: ${formatTime(m.last_used)}</div>
              </div>
              <span class="model-badge ${getBadgeClass(m.name)}">${m.requests} ${m.requests === 1 ? 'call' : 'calls'}</span>
            </div>
            
            <div>
              <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-dim); margin-bottom:4px;">
                <span>In: ${inPct}% | Out: ${outPct}% | Cache: ${cachePct}%</span>
              </div>
              <div class="bar-container">
                <div class="bar-segment bar-input" style="width: ${inPct}%;"></div>
                <div class="bar-segment bar-output" style="width: ${outPct}%;"></div>
                <div class="bar-segment bar-cache" style="width: ${cachePct}%;"></div>
              </div>
            </div>

            <div style="margin-top:4px;">
              <div class="token-breakdown-row">
                <span>Input tokens:</span>
                <span class="token-val" style="color:var(--primary-light);">${formatNumber(m.input)}</span>
              </div>
              <div class="token-breakdown-row">
                <span>Output tokens:</span>
                <span class="token-val" style="color:var(--accent-green);">${formatNumber(m.output)}</span>
              </div>
              <div class="token-breakdown-row">
                <span>Cache Read tokens:</span>
                <span class="token-val" style="color:var(--accent-purple);">${formatNumber(m.cache)}</span>
              </div>
              <div class="token-breakdown-row" style="font-weight:700; margin-top:6px; padding-top:6px; border-top:1px solid var(--card-border);">
                <span>Total tokens:</span>
                <span class="token-val">${formatNumber(m.total)}</span>
              </div>
            </div>
          `;
          modelsContainer.appendChild(card);
        });
      }

      // Conversations Table
      const convosTbody = document.getElementById('convos-tbody');
      convosTbody.innerHTML = '';
      (data.conversations || []).forEach(c => {
        const tr = document.createElement('tr');
        const activeBadge = c.is_active ? '<span class="active-convo-pill">Active</span>' : '';
        tr.innerHTML = `
          <td>
            <div class="convo-title" title="${c.title}">${c.title} ${activeBadge}</div>
            <div style="font-size:11px; color:var(--text-dim);">${formatTime(c.last_active)}</div>
          </td>
          <td><b>${c.requests}</b></td>
          <td>${formatNumber(c.input)}</td>
          <td>${formatNumber(c.output)}</td>
          <td><b>${formatNumber(c.total)}</b></td>
        `;
        convosTbody.appendChild(tr);
      });

      // Events Table
      const eventsTbody = document.getElementById('events-tbody');
      eventsTbody.innerHTML = '';
      (data.recent_events || []).slice(0, 15).forEach(e => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="white-space:nowrap; font-size:12px;">${formatTime(e.timestamp)}</td>
          <td><span class="event-pill">${e.model.replace(/\(.*?\)/, '').trim()}</span></td>
          <td style="font-size:12px;">
            <span style="color:var(--primary-light);">${formatNumber(e.input)}</span> / 
            <span style="color:var(--accent-green);">${formatNumber(e.output)}</span> / 
            <span style="color:var(--accent-purple);">${formatNumber(e.cache)}</span>
          </td>
          <td style="max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px;">${e.conversation_title}</td>
        `;
        eventsTbody.appendChild(tr);
      });
    }

    async function togglePiP() {
      if ('documentPictureInPicture' in window) {
        try {
          const pipWindow = await documentPictureInPicture.requestWindow({
            width: 360,
            height: 310,
          });
          const container = document.createElement('div');
          container.style.padding = '14px';
          container.style.background = '#090d16';
          container.style.color = '#f8fafc';
          container.style.minHeight = '100vh';
          container.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
          container.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <b style="font-size:13px; color:#38bdf8;">● AG Mini Monitor</b>
              <span style="font-size:11px; color:#94a3b8;" id="pip-time"></span>
            </div>
            <div id="pip-models" style="display:flex; flex-direction:column; gap:8px;"></div>
          `;
          pipWindow.document.body.style.margin = '0';
          pipWindow.document.body.appendChild(container);

          function updatePip() {
            if (!rawData) return;
            const view = rawData.views['all'];
            const mContainer = pipWindow.document.getElementById('pip-models');
            const tSpan = pipWindow.document.getElementById('pip-time');
            if (tSpan) tSpan.textContent = new Date().toLocaleTimeString('en-US', {hour12:false});
            if (mContainer && view.models) {
              mContainer.innerHTML = '';
              view.models.slice(0, 4).forEach(m => {
                const card = document.createElement('div');
                card.style.background = '#101626';
                card.style.border = '1px solid #1e283d';
                card.style.borderRadius = '8px';
                card.style.padding = '8px 10px';
                card.innerHTML = `
                  <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                    <b style="color:#f8fafc;">${m.name.replace(/\(.*?\)/, '').trim()}</b>
                    <span style="color:#60a5fa; font-weight:600;">${m.requests} calls</span>
                  </div>
                  <div style="display:flex; justify-content:space-between; font-size:11px; color:#94a3b8;">
                    <span>Total: ${(m.total / 1000).toFixed(0)}k tok</span>
                    <span>In: ${(m.input / 1000).toFixed(0)}k</span>
                  </div>
                `;
                mContainer.appendChild(card);
              });
            }
          }
          updatePip();
          const interval = setInterval(updatePip, 2000);
          pipWindow.addEventListener('pagehide', () => clearInterval(interval));
          return;
        } catch (e) {
          console.log('PiP failed, opening popup', e);
        }
      }
      window.open('/', 'AGMini', 'width=360,height=420,menubar=no,toolbar=no,location=no,status=no');
    }

    fetchUsage();
    setInterval(fetchUsage, 2000);
  </script>
</body>
</html>
"""

class TrackerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
        elif parsed.path == "/api/usage":
            data = parse_all_usage()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def main():
    open_browser = "--no-browser" not in sys.argv
    server = HTTPServer((HOST, PORT), TrackerHandler)
    url = f"http://{HOST}:{PORT}"
    print("=" * 65)
    print(f" Antigravity Model Usage Tracker running at: {url}")
    print(" Monitoring token usage and models in real-time.")
    print(" Press Ctrl+C to stop")
    print("=" * 65)

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTracker stopped.")
        server.server_close()

if __name__ == "__main__":
    main()
