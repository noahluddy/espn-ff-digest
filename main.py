"""
ESPN Fantasy Football League Activity Digest

This script fetches recent activity from an ESPN Fantasy Football league
and generates an HTML report showing trades, adds, drops, and other transactions.
"""

import os
import re
import webbrowser
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dateutil import tz
from dotenv import load_dotenv
from espn_api.football import League
from gmail_send import send_gmail_html
from email_render import render_email_html

load_dotenv()

# Always display times in US Central Time (handles CST/CDT automatically)
CENTRAL_TIME = tz.gettz("America/Chicago")

@dataclass
class PlayerInfo:
    """Player information for activity tracking."""
    player_id: int | None = None
    position: str = ""
    pro_team: str = ""
    name: str = ""

@dataclass
class ActivityItem:
    """Activity item for fantasy football transactions."""
    when_utc: datetime
    team: str
    player: str
    action: str
    bid: int
    action_type: str
    player_id: int | None = None
    position: str = ""
    pro_team: str = ""
    added_player: PlayerInfo | None = None
    dropped_player: PlayerInfo | None = None

# ---------- utils ----------
def get_env(name: str, required: bool = True, default: str | None = None) -> str:
    """Get environment variable with optional validation.
    
    Args:
        name: Environment variable name
        required: Whether the variable is required
        default: Default value if not found
        
    Returns:
        Environment variable value
        
    Raises:
        RuntimeError: If required variable is missing or empty
    """
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

def debug() -> bool:
    """Check if DEBUG is enabled.
    
    Returns:
        True if DEBUG environment variable is set to a truthy value
    """
    debug_val = get_env("DEBUG", default="", required=False)
    return debug_val.lower() in {"1", "true", "yes", "on"}

def league_handle() -> League:
    """Create and return a League instance using environment variables.
    
    Returns:
        Configured League instance
        
    Raises:
        RuntimeError: If required environment variables are missing
        ValueError: If league_id or year cannot be converted to int
    """
    try:
        return League(
            league_id=int(get_env("LEAGUE_ID")),
            year=int(get_env("YEAR")),
            swid=get_env("SWID"),
            espn_s2=get_env("ESPN_S2"),
        )
    except ValueError as e:
        raise ValueError(f"Invalid league configuration: {e}") from e

def normalize_action_tuple(t: Any) -> tuple[Any, str, Any, Any]:
    """Normalize ESPN action tuple to consistent format.
    
    Args:
        t: Action data from ESPN API (list, tuple, dict, or other)
        
    Returns:
        Tuple of (team, action, player, bid) with normalized action text
    """
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
    """Classify ESPN action text into categories.
    
    Args:
        action_text: Raw action text from ESPN API
        
    Returns:
        Category string: "Trades", "Drops", "Adds", "Waivers", "Roster Moves", or "Other"
    """
    action_lower = action_text.lower()

    # Use match statement for cleaner pattern matching
    match action_lower:
        case action if "trade" in action or "traded" in action:
            return "Trades"
        case action if "drop" in action or "dropped" in action:
            return "Drops"
        case action if "add" in action:
            return "Adds"
        case action if "waiver" in action or "claim" in action:
            return "Waivers"
        case action if any(word in action for word in ("move", "activated", "reserve")):
            return "Roster Moves"
        case _:
            return "Other"

def fmt_team(team_obj: Any) -> str:
    """Format team object to string, trying team_name, team_abbrev, then str()."""
    return (getattr(team_obj, "team_name", None) or
            getattr(team_obj, "team_abbrev", None) or
            str(team_obj))

def fmt_player(player_obj: Any) -> str:
    """Format player object to string with position and team info."""
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
    """Format UTC datetime to local time string."""
    return dt_utc.astimezone(CENTRAL_TIME).strftime("%Y-%m-%d %I:%M %p")

def format_individual_action(item: dict[str, Any]) -> str:
    """Format individual action text with proper styling."""
    action_type = item["action_type"]
    action_text = item["action"].lower()
    player = item["player"]
    bid = item["bid"]
    
    match action_type:
        case "Adds":
            if "waiver added" in action_text:
                return f"Claimed <strong>{player}</strong> for ${bid}"
            return f"Added <strong>{player}</strong>"
        case "Drops":
            return f"Dropped <strong>{player}</strong>"
        case _:
            # Check if it's a waiver claim that wasn't classified as "Adds"
            if "waiver added" in action_text:
                return f"Claimed <strong>{player}</strong> for ${bid}"
            return item["action"]

# ---------- fetch ----------
def _process_activity_actions(actions: list[Any],
                             ts_utc: datetime) -> dict[str, list[dict[str, Any]]]:
    """Process actions within a single activity and categorize them.

    Args:
        actions: List of action tuples from ESPN API
        ts_utc: UTC timestamp for the activity

    Returns:
        Dictionary with categorized actions
    """
    adds = []
    drops = []
    trades = []
    other_actions = []

    for tup in actions:
        team_obj, action_text, player_obj, bid = normalize_action_tuple(tup)
        action_type = classify_action(action_text)

        # Extract player details for headshot support
        player_id = getattr(player_obj, "playerId", None) if player_obj else None
        player_position = getattr(player_obj, "position", "") if player_obj else ""
        player_team = getattr(player_obj, "proTeam", "") if player_obj else ""
        
        activity_item = {
            "when_utc": ts_utc,
            "team": fmt_team(team_obj),
            "player": fmt_player(player_obj),
            "action": action_text,
            "bid": bid or 0,
            "action_type": action_type,
            "player_id": player_id,
            "position": player_position,
            "pro_team": player_team,
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

    return {
        "adds": adds,
        "drops": drops,
        "trades": trades,
        "other": other_actions
    }


def _process_add_drop_combinations(adds: list[dict[str, Any]],
                                  drops: list[dict[str, Any]],
                                  ts_utc: datetime) -> list[dict[str, Any]]:
    """Process add/drop combinations and return combined items.

    Args:
        adds: List of add actions
        drops: List of drop actions
        ts_utc: UTC timestamp for the activity

    Returns:
        List of combined action items
    """
    combined_items = []
    paired_items = []
    remaining_adds = adds.copy()
    remaining_drops = drops.copy()

    # Try to pair drops with adds
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
        is_waiver_claim = "waiver" in add_item["action"].lower()

        if is_waiver_claim:
            player_text = (f"Dropped <strong>{drop_item['player']}</strong> "
                          f"to claim <strong>{add_item['player']}</strong> "
                          f"for ${add_item['bid']}")
        else:
            player_text = (f"Dropped <strong>{drop_item['player']}</strong> "
                          f"for <strong>{add_item['player']}</strong>")

        combined = {
            "when_utc": ts_utc,
            "team": add_item["team"],
            "player": player_text,
            "bid": add_item["bid"] if is_waiver_claim else max(add_item["bid"], drop_item["bid"]),
            "action_type": "Combined",
            # Store both players' information
            "added_player": {
                "player_id": add_item.get("player_id"),
                "position": add_item.get("position", ""),
                "pro_team": add_item.get("pro_team", ""),
                "name": add_item.get("player", "").replace("<strong>", "").replace("</strong>", "")
            },
            "dropped_player": {
                "player_id": drop_item.get("player_id"),
                "position": drop_item.get("position", ""),
                "pro_team": drop_item.get("pro_team", ""),
                "name": drop_item.get("player", "").replace("<strong>", "").replace("</strong>", "")
            }
        }
        combined_items.append(combined)

    # Handle remaining unpaired items
    for item in remaining_adds + remaining_drops:
        formatted_action = format_individual_action(item)
        # For individual actions, determine if it's an add or drop
        is_drop = "Dropped" in formatted_action or "drop" in item.get("action", "").lower()
        
        combined_item = {
            "when_utc": item["when_utc"],
            "team": item["team"],
            "player": formatted_action,
            "bid": item["bid"],
            "action_type": "Combined",
            "added_player": {
                "player_id": item.get("player_id") if not is_drop else None,
                "position": item.get("position", "") if not is_drop else "",
                "pro_team": item.get("pro_team", "") if not is_drop else "",
                "name": item.get("player", "").replace("<strong>", "").replace("</strong>", "") if not is_drop else ""
            },
            "dropped_player": {
                "player_id": item.get("player_id") if is_drop else None,
                "position": item.get("position", "") if is_drop else "",
                "pro_team": item.get("pro_team", "") if is_drop else "",
                "name": item.get("player", "").replace("<strong>", "").replace("</strong>", "") if is_drop else ""
            }
        }
        combined_items.append(combined_item)

    return combined_items


def _process_trades(trades: list[dict[str, Any]], ts_utc: datetime) -> dict[str, Any]:
    """Process trade actions and return combined trade item.

    Args:
        trades: List of trade actions
        ts_utc: UTC timestamp for the activity

    Returns:
        Combined trade item
    """
    if len(trades) == 1:
        trade = trades[0]
        return {
            "when_utc": ts_utc,
            "team": trade["team"],
            "player": f"Traded <strong>{trade['player']}</strong>",
            "bid": trade["bid"],
            "action_type": "Combined",
            "added_player": {
                "player_id": trade.get("player_id"),
                "position": trade.get("position", ""),
                "pro_team": trade.get("pro_team", ""),
                "name": trade.get("player", "").replace("<strong>", "").replace("</strong>", "")
            },
            "dropped_player": {
                "player_id": None,
                "position": "",
                "pro_team": "",
                "name": ""
            }
        }

    # Multi-player trade
    trade_players = [f"<strong>{t['player']}</strong>" for t in trades]
    trade_text = (f"Traded {trade_players[0]} for "
                 f"{', '.join(trade_players[1:])}")
    return {
        "when_utc": ts_utc,
        "team": trades[0]["team"],
        "player": trade_text,
        "bid": max(t["bid"] for t in trades),
        "action_type": "Combined",
        "added_player": {
            "player_id": trades[0].get("player_id"),
            "position": trades[0].get("position", ""),
            "pro_team": trades[0].get("pro_team", ""),
            "name": trades[0].get("player", "").replace("<strong>", "").replace("</strong>", "")
        },
        "dropped_player": {
            "player_id": None,
            "position": "",
            "pro_team": "",
            "name": ""
        }
    }


def _process_single_activity(act: Any, since_utc: datetime) -> list[dict[str, Any]]:
    """Process a single activity and return combined items.

    Args:
        act: Activity object from ESPN API
        since_utc: UTC timestamp to filter activities

    Returns:
        List of combined action items
    """
    ts_utc = datetime.fromtimestamp(act.date / 1000, tz=timezone.utc)
    if ts_utc < since_utc:
        return []

    actions = getattr(act, "actions", []) or []
    if not actions:
        return []

    # Process and categorize actions
    categorized = _process_activity_actions(actions, ts_utc)
    adds = categorized["adds"]
    drops = categorized["drops"]
    trades = categorized["trades"]
    other_actions = categorized["other"]

    # Process transactions based on type
    if adds and drops:
        return _process_add_drop_combinations(adds, drops, ts_utc)
    if trades:
        return [_process_trades(trades, ts_utc)]

    # Handle individual actions
    combined_items = []
    for item in adds + drops + other_actions:
        formatted_action = format_individual_action(item)
        # For individual actions, determine if it's an add or drop
        is_drop = "Dropped" in formatted_action or "drop" in item.get("action", "").lower()
        
        combined_item = {
            "when_utc": item["when_utc"],
            "team": item["team"],
            "player": formatted_action,
            "bid": item["bid"],
            "action_type": "Combined",
            "added_player": {
                "player_id": item.get("player_id") if not is_drop else None,
                "position": item.get("position", "") if not is_drop else "",
                "pro_team": item.get("pro_team", "") if not is_drop else "",
                "name": item.get("player", "").replace("<strong>", "").replace("</strong>", "") if not is_drop else ""
            },
            "dropped_player": {
                "player_id": item.get("player_id") if is_drop else None,
                "position": item.get("position", "") if is_drop else "",
                "pro_team": item.get("pro_team", "") if is_drop else "",
                "name": item.get("player", "").replace("<strong>", "").replace("</strong>", "") if is_drop else ""
            }
        }
        combined_items.append(combined_item)
    return combined_items


def get_activity_since(league: League, since_utc: datetime) -> dict[str, list[dict[str, Any]]]:
    """Fetch and process league activity since the given UTC datetime."""
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    # Fetch recent activity (optionally dump raw output when DEBUG is set truthy)
    raw_activity = league.recent_activity(size=300)
    if debug():
        _debug_dump_activity(raw_activity)

    # Process activities
    for act in raw_activity:
        if combined_items := _process_single_activity(act, since_utc):
            grouped["Combined"].extend(combined_items)

    for cat in grouped:
        grouped[cat].sort(key=lambda d: (d["when_utc"], d["team"], d["player"]))
    return grouped


def _debug_dump_activity(raw_activity: list[Any]) -> None:
    """Dump raw activity data to debug file when DEBUG is enabled."""
    debug_file = Path("debug_espn_raw.txt")
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

# ---------- write file ----------
def write_html_file(html: str, auto_open: bool = True) -> str:
    """Write HTML content to a file and optionally open it in browser."""
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone(CENTRAL_TIME).strftime("%Y-%m-%d")
    path = reports_dir / f"activity-{ts}.html"
    path.write_text(html, encoding="utf-8")
    if auto_open:
        webbrowser.open(path.resolve().as_uri())
    return str(path)

# ---------- main ----------
def main():
    """Main function to generate and display league activity report."""
    lookback_hours = int(os.environ.get("LOOKBACK_HOURS", "24"))
    since_utc = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    lg = league_handle()
    grouped = get_activity_since(lg, since_utc)

    grouped_for_email = {}
    for cat, items in grouped.items():
        grouped_for_email[cat] = [
            {**i, "when_local": fmt_local(i["when_utc"])} for i in items
        ]

    central_now = datetime.now().astimezone(CENTRAL_TIME)
    window_desc = (f"(last {lookback_hours}h ending "
                   f"{central_now.strftime('%Y-%m-%d %I:%M %p %Z')})")
    league_title = f"ESPN Fantasy Football League: {lg.settings.name}"
    email_html = render_email_html(grouped_for_email, window_desc, league_title)

    if debug():
        out = write_html_file(email_html, auto_open=True)
        print(f"Wrote: {out}")
    else:
        send_gmail_html(f"Daily Digest for ESPN Fantasy Football League: "
                       f"{lg.settings.name}", email_html)
        print("Successfully sent email.")

if __name__ == "__main__":
    main()
