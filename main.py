import os
import re
import pathlib
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple, DefaultDict, Union

from dateutil import tz
from dotenv import load_dotenv
from espn_api.football import League

load_dotenv()

# Always display times in US Central Time (handles CST/CDT automatically)
CENTRAL_TIME = tz.gettz("America/Chicago")

# ---------- utils ----------
def get_env(name: str, required: bool = True, default: Union[str, None] = None) -> str:
    val = os.environ.get(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return val

def league_handle() -> League:
    return League(
        league_id=int(get_env("LEAGUE_ID")),
        year=int(get_env("YEAR")),
        swid=get_env("SWID"),
        espn_s2=get_env("ESPN_S2"),
    )

def normalize_action_tuple(t: Any) -> Tuple[Any, str, Any, Any]:
    """ESPN actions are usually (team, action, player, bid). Be defensive."""
    if isinstance(t, (list, tuple)) and len(t) >= 3:
        team, action, player = t[0], t[1], t[2]
        bid = t[3] if len(t) >= 4 else None
        return team, str(action).lower(), player, bid
    if isinstance(t, dict):
        return (
            t.get("team"),
            str(t.get("action", "")).lower(),
            t.get("player"),
            t.get("bid") or t.get("amount"),
        )
    return None, str(t).lower(), t, None

def classify_action(action_text: str) -> str:
    """Classify ESPN action text into categories."""
    a = action_text.lower()
    
    # Check for trades first (most specific)
    if "trade" in a or "traded" in a:
        return "Trades"
    
    # Check for drops
    if "drop" in a or "dropped" in a:
        return "Drops"
    
    # Check for adds (including waiver adds)
    if "add" in a:
        return "Adds"
    
    # Check for other specific actions
    if "waiver" in a or "claim" in a:
        return "Waivers"
    if "move" in a or "activated" in a or "reserve" in a:
        return "Roster Moves"
    
    return "Other"

def fmt_team(team_obj: Any) -> str:
    return getattr(team_obj, "team_name", None) or getattr(team_obj, "team_abbrev", None) or str(team_obj)

def fmt_player(player_obj: Any) -> str:
    if hasattr(player_obj, "name"):
        name = player_obj.name
        # Don't add position/proTeam info if name already includes "D/ST"
        if "D/ST" in name:
            return name
        pos = getattr(player_obj, "position", "")
        pro = getattr(player_obj, "proTeam", "")
        extras = ", ".join([p for p in [pos, pro] if p])
        return f"{name} ({extras})" if extras else name
    return str(player_obj)

def strip_html_tags(text: str) -> str:
    """Remove simple HTML tags like <strong> from a string for plain-text extraction."""
    if not isinstance(text, str):
        return str(text)
    return re.sub(r"<[^>]+>", "", text)

def fmt_local(dt_utc: datetime) -> str:
    return dt_utc.astimezone(CENTRAL_TIME).strftime("%Y-%m-%d %I:%M %p")

def format_individual_action(item: Dict[str, Any]) -> str:
    """Format individual action text with proper styling."""
    if item["action_type"] == "Adds":
        if "waiver added" in item["action"].lower():
            return f"Claimed <strong>{item['player']}</strong> for ${item['bid']}"
        else:
            return f"Added <strong>{item['player']}</strong>"
    elif item["action_type"] == "Drops":
        return f"Dropped <strong>{item['player']}</strong>"
    else:
        # Check if it's a waiver claim that wasn't classified as "Adds"
        if "waiver added" in item["action"].lower():
            return f"Claimed <strong>{item['player']}</strong> for ${item['bid']}"
        else:
            return item["action"]

# ---------- fetch ----------
def get_activity_since(league: League, since_utc: datetime) -> Dict[str, List[Dict[str, Any]]]:
    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    # Fetch recent activity (optionally dump raw output when DEBUG_ACTIVITY is set truthy)
    raw_activity = league.recent_activity(size=300)
    if os.environ.get("DEBUG_ACTIVITY", "").lower() in {"1", "true", "yes", "on"}:
        debug_file = pathlib.Path("debug_espn_raw.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(f"Raw ESPN API output (size={len(raw_activity)}):\n\n")
            for i, act in enumerate(raw_activity):
                f.write(f"Activity {i}:\n")
                f.write(f"  Date: {act.date}\n")
                f.write(f"  Actions: {getattr(act, 'actions', 'None')}\n")
                f.write(f"  Full object: {act}\n")
                f.write(f"  Object type: {type(act)}\n")
                f.write(f"  Object dir: {dir(act)}\n")
                f.write("-" * 80 + "\n")
        print(f"Debug: Raw ESPN API output saved to {debug_file}")
    
    # Process activities and handle related transactions within the same activity
    for act in raw_activity:
        ts_utc = datetime.fromtimestamp(act.date / 1000, tz=timezone.utc)
        if ts_utc < since_utc:
            continue
        
        actions = getattr(act, "actions", []) or []
        if not actions:
            continue
            
        # Categorize actions within this activity
        adds = []
        drops = []
        trades = []
        other_actions = []
        
        for tup in actions:
            team_obj, action_text, player_obj, bid = normalize_action_tuple(tup)
            action_type = classify_action(action_text)
            
            activity_item = {
                "when_utc": ts_utc,
                "team": fmt_team(team_obj),
                "player": fmt_player(player_obj),
                "action": action_text,
                "bid": bid or 0,
                "action_type": action_type,
            }
            
            # Categorize the action
            if action_type == "Adds":
                adds.append(activity_item)
            elif action_type == "Drops":
                drops.append(activity_item)
            elif action_type == "Trades":
                trades.append(activity_item)
            else:
                other_actions.append(activity_item)
        
        # Process transactions based on type
        if adds and drops:
            # Handle add/drop combinations
            # Try to pair them up - handle both orders
            paired_items = []
            remaining_adds = adds.copy()
            remaining_drops = drops.copy()
            
            # First, try to pair drops with adds (in case drops come first)
            for drop_item in drops:
                for add_item in adds:
                    if (drop_item not in [p[0] for p in paired_items] and 
                        add_item not in [p[1] for p in paired_items]):
                        paired_items.append((drop_item, add_item))
                        remaining_adds.remove(add_item)
                        remaining_drops.remove(drop_item)
                        break
            
            # Process paired items
            for drop_item, add_item in paired_items:
                # Check if this is a waiver claim
                is_waiver_claim = "waiver" in add_item["action"].lower()
                
                if is_waiver_claim:
                    # Format as "Dropped X to claim Y for $Z"
                    combined = {
                        "when_utc": ts_utc,
                        "team": add_item["team"],
                        "player": f"Dropped <strong>{drop_item['player']}</strong> to claim <strong>{add_item['player']}</strong> for ${add_item['bid']}",
                        "action": f"Dropped <strong>{drop_item['player']}</strong> to claim <strong>{add_item['player']}</strong> for ${add_item['bid']}",
                        "bid": add_item["bid"],
                        "action_type": "Combined",
                    }
                else:
                    # Format as regular add/drop
                    combined = {
                        "when_utc": ts_utc,
                        "team": add_item["team"],
                        "player": f"Dropped <strong>{drop_item['player']}</strong> for <strong>{add_item['player']}</strong>",
                        "action": f"Dropped <strong>{drop_item['player']}</strong> for <strong>{add_item['player']}</strong>",
                        "bid": max(add_item["bid"], drop_item["bid"]),
                        "action_type": "Combined",
                    }
                grouped["Combined"].append(combined)
            
            # Handle any remaining unpaired items as individual actions
            for item in remaining_adds + remaining_drops:
                formatted_action = format_individual_action(item)
                combined_item = {
                    "when_utc": item["when_utc"],
                    "team": item["team"],
                    "player": formatted_action,
                    "action": formatted_action,
                    "bid": item["bid"],
                    "action_type": "Combined",
                }
                grouped["Combined"].append(combined_item)
        elif trades:
            # Handle trades (single or multi-player)
            if len(trades) == 1:
                trade = trades[0]
                combined = {
                    "when_utc": ts_utc,
                    "team": trade["team"],
                    "player": f"Traded <strong>{trade['player']}</strong>",
                    "action": f"Traded <strong>{trade['player']}</strong>",
                    "bid": trade["bid"],
                    "action_type": "Combined",
                }
            else:
                # Multi-player trade
                trade_players = [f"<strong>{t['player']}</strong>" for t in trades]
                combined = {
                    "when_utc": ts_utc,
                    "team": trades[0]["team"],
                    "player": f"Traded {trade_players[0]} for {', '.join(trade_players[1:])}",
                    "action": f"Traded {trade_players[0]} for {', '.join(trade_players[1:])}",
                    "bid": max(t["bid"] for t in trades),
                    "action_type": "Combined",
                }
            grouped["Combined"].append(combined)
        else:
            # Handle individual actions
            for item in adds + drops + other_actions:
                formatted_action = format_individual_action(item)
                combined_item = {
                    "when_utc": item["when_utc"],
                    "team": item["team"],
                    "player": formatted_action,
                    "action": formatted_action,
                    "bid": item["bid"],
                    "action_type": "Combined",
                }
                grouped["Combined"].append(combined_item)
    
    for cat in grouped:
        grouped[cat].sort(key=lambda d: (d["when_utc"], d["team"], d["player"]))
    return grouped


# ---------- render ----------
CSS = """
:root { --bg:#0b1020; --card:#121a36; --text:#e9edf5; --muted:#a8b3cf; --accent:#6aa6ff; --border:#2a3560; }
* { box-sizing:border-box; }
body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:var(--bg); color:var(--text);}
header { padding:24px 20px; border-bottom:1px solid var(--border); background:linear-gradient(180deg, rgba(255,255,255,.03), transparent); position:sticky; top:0; backdrop-filter:saturate(140%) blur(6px); }
h1 { margin:0 0 6px; font-size:20px; }
h2 { margin:0; font-weight:600; color:var(--muted); font-size:14px; }
.container { max-width:1100px; margin:24px auto; padding:0 20px; }
.section { margin:18px 0 26px; }
.section h3 { margin:0 0 10px; font-size:16px; color:var(--accent); }
.card { background:var(--card); border:1px solid var(--border); border-radius:14px; overflow:hidden; box-shadow:0 10px 24px rgba(0,0,0,.25); }
table { width:100%; border-collapse:collapse; font-size:14px; table-layout:fixed; }
thead th { text-align:left; padding:10px 12px; background:rgba(255,255,255,.04); border-bottom:1px solid var(--border); }
tbody td { padding:10px 12px; border-bottom:1px solid var(--border); }
th:nth-child(1), td:nth-child(1) { width:20%; }
th:nth-child(2), td:nth-child(2) { width:25%; }
th:nth-child(3), td:nth-child(3) { width:55%; }
tbody tr:hover { background:rgba(255,255,255,.03); }
.empty { padding:14px 16px; color:var(--muted); }
.footer { color:var(--muted); font-size:12px; margin:30px 0; }
.badge { display:inline-block; padding:2px 8px; border-radius:999px; background:rgba(106,166,255,.15); color:#bcd6ff; border:1px solid rgba(106,166,255,.35); font-size:12px; margin-left:8px;}
.related-transaction { background:rgba(106,166,255,.08); border-left:3px solid var(--accent); }
.related-transaction td { padding:12px; }
.player-combo { font-weight:500; color:var(--accent); }
.action-combo { font-style:italic; color:var(--muted); }
"""


def render_html(grouped: Dict[str, List[Dict[str, Any]]], window_desc: str) -> str:
    # Get all combined actions and sort by time
    all_actions = grouped.get("Combined", [])
    all_actions.sort(key=lambda d: d["when_utc"])
    
    # Get dropped players for the separate table
    dropped_players = [action for action in all_actions if "Dropped" in action["player"]]
    
    sections = []
    
    # Add Players Dropped table if there are any
    if dropped_players:
        sections.append(render_dropped_players_table(dropped_players))
    
    # Add All Activity table
    if not all_actions:
        sections.append(f"<div class='card empty'>No activity {window_desc}.</div>")
    else:
        sections.append(render_combined_table(all_actions))
    
    now = datetime.now().astimezone(CENTRAL_TIME).strftime("%Y-%m-%d %I:%M %p %Z")
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESPN League Activity {window_desc}</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>ESPN League Activity</h1>
  <h2>{window_desc} • Generated {now}</h2>
</header>
<div class="container">
  {''.join(sections)}
</div>
</body></html>"""

def render_dropped_players_table(items: List[Dict[str, Any]]) -> str:
    """Render a simple list showing only dropped player names."""
    rows = []
    for i in items:
        # Extract just the player name from the action text
        # Handle "Dropped Player A", "Dropped Player A for Player B", and "Dropped Player A to claim Player B" formats
        action_text = strip_html_tags(i['player'])
        if "Dropped" in action_text and ("for" in action_text or "to claim" in action_text):
            # Extract the dropped player name (first player in "Dropped Player A for/to claim Player B")
            dropped_player = action_text.split("Dropped ")[1].split(" for ")[0].split(" to claim ")[0]
        elif "Dropped" in action_text:
            # Extract the dropped player name (from "Dropped Player A")
            dropped_player = action_text.split("Dropped ")[1]
        else:
            dropped_player = action_text
        
        rows.append(f"<tr><td>{dropped_player}</td></tr>")
    
    rows_html = "".join(rows)
    return (
        f"<div class='section'>"
        f"<h3>Dropped Players <span class='badge'>{len(items)}</span></h3>"
        f"<div class='card'><table>"
        f"<tbody>{rows_html}</tbody></table></div></div>"
    )

def render_combined_table(items: List[Dict[str, Any]]) -> str:
    """Render a single combined table with all actions sorted by time."""
    rows = []
    for i in items:
        rows.append(
            f"<tr>"
            f"<td>{fmt_local(i['when_utc'])}</td>"
            f"<td>{i['team']}</td>"
            f"<td>{i['player']}</td>"
            f"</tr>"
        )
    
    rows_html = "".join(rows)
    return (
        f"<div class='section'>"
        f"<h3>All Activity <span class='badge'>{len(items)}</span></h3>"
        f"<div class='card'><table>"
        f"<thead><tr><th>When ({datetime.now().astimezone(CENTRAL_TIME).tzname()})</th><th>Team</th><th>Action</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div></div>"
    )

# ---------- write file ----------
def write_html_file(html: str, auto_open: bool = True) -> str:
    reports_dir = pathlib.Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone(CENTRAL_TIME).strftime("%Y-%m-%d")
    path = reports_dir / f"activity-{ts}.html"
    path.write_text(html, encoding="utf-8")
    if auto_open:
        webbrowser.open(path.resolve().as_uri())
    return str(path)

# ---------- main ----------
def main():
    lookback_hours = int(os.environ.get("LOOKBACK_HOURS", "24"))
    since_utc = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    lg = league_handle()
    grouped = get_activity_since(lg, since_utc)

    central_now = datetime.now().astimezone(CENTRAL_TIME)
    window_desc = f"(last {lookback_hours}h ending {central_now.strftime('%Y-%m-%d %I:%M %p %Z')})"
    html = render_html(grouped, window_desc)
    out = write_html_file(html, auto_open=True)
    print(f"Wrote: {out}")

if __name__ == "__main__":
    main()
