"""
ESPN Fantasy Football League Activity Digest

This script fetches recent activity from an ESPN Fantasy Football league
and generates an HTML report showing trades, adds, drops, and other transactions.
"""

import time
import webbrowser
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from espn_api.football import League

from email_render import render_email_html
from gmail_send import send_gmail_html
from utils import CENTRAL_TIME, debug, fmt_local, fmt_player, fmt_team, get_env

load_dotenv()


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

def _extract_player_info(player_obj: Any) -> dict[str, Any]:
    """Extract standardized player information from player object.

    Args:
        player_obj: Player object from ESPN API

    Returns:
        Dictionary with player_id, position, pro_team, and name
    """
    if not player_obj:
        return {
            "player_id": None,
            "position": "",
            "pro_team": "",
            "name": ""
        }

    return {
        "player_id": getattr(player_obj, "playerId", None),
        "position": getattr(player_obj, "position", ""),
        "pro_team": getattr(player_obj, "proTeam", ""),
        "name": getattr(player_obj, "name", str(player_obj))
    }

def _extract_player_info_from_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Extract player information from activity item dictionary.

    Args:
        item: Activity item dictionary

    Returns:
        Dictionary with player_id, position, pro_team, and name
    """
    return {
        "player_id": item.get("player_id"),
        "position": item.get("position", ""),
        "pro_team": item.get("pro_team", ""),
        "name": item.get("player", "").replace("<strong>", "").replace("</strong>", "")
    }

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
        player_info = _extract_player_info(player_obj)

        activity_item = {
            "when_utc": ts_utc,
            "team": fmt_team(team_obj),
            "player": fmt_player(player_obj),
            "action": action_text,
            "bid": bid or 0,
            "action_type": action_type,
            **player_info
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
    used_adds = set()
    used_drops = set()

    # Try to pair drops with adds - O(n*m) instead of O(n²)
    for i, drop_item in enumerate(drops):
        if i in used_drops:
            continue
        for j, add_item in enumerate(adds):
            if j in used_adds:
                continue
            # Found a pair - process immediately
            used_adds.add(j)
            used_drops.add(i)

            is_waiver_claim = "waiver" in add_item["action"].lower()

            if is_waiver_claim:
                player_text = (f"Dropped <strong>{drop_item['player']}</strong> "
                              f"to claim <strong>{add_item['player']}</strong> "
                              f"for ${add_item['bid']}")
            else:
                player_text = (f"Dropped <strong>{drop_item['player']}</strong> "
                              f"for <strong>{add_item['player']}</strong>")

            # Use helper function for player info
            added_player_info = _extract_player_info_from_dict(add_item)
            dropped_player_info = _extract_player_info_from_dict(drop_item)

            combined = {
                "when_utc": ts_utc,
                "team": add_item["team"],
                "player": player_text,
                "bid": (add_item["bid"] if is_waiver_claim
                       else max(add_item["bid"], drop_item["bid"])),
                "action_type": "Combined",
                "added_player": added_player_info,
                "dropped_player": dropped_player_info
            }
            combined_items.append(combined)
            break

    # Handle remaining unpaired items - use generators to avoid memory copies
    remaining_adds = (adds[i] for i in range(len(adds)) if i not in used_adds)
    remaining_drops = (drops[i] for i in range(len(drops)) if i not in used_drops)

    # Process remaining adds
    for item in remaining_adds:
        formatted_action = format_individual_action(item)
        combined_item = {
            "when_utc": item["when_utc"],
            "team": item["team"],
            "player": formatted_action,
            "bid": item["bid"],
            "action_type": "Combined",
            "added_player": _extract_player_info_from_dict(item),
            "dropped_player": {
                "player_id": None,
                "position": "",
                "pro_team": "",
                "name": ""
            }
        }
        combined_items.append(combined_item)

    # Process remaining drops
    for item in remaining_drops:
        formatted_action = format_individual_action(item)
        combined_item = {
            "when_utc": item["when_utc"],
            "team": item["team"],
            "player": formatted_action,
            "bid": item["bid"],
            "action_type": "Combined",
            "added_player": {
                "player_id": None,
                "position": "",
                "pro_team": "",
                "name": ""
            },
            "dropped_player": _extract_player_info_from_dict(item)
        }
        combined_items.append(combined_item)

    return combined_items


def _process_trades(trades: list[dict[str, Any]], ts_utc: datetime) -> list[dict[str, Any]]:
    """Process trade actions and return combined trade items for each team.

    Args:
        trades: List of trade actions
        ts_utc: UTC timestamp for the activity

    Returns:
        List of combined trade items, one for each team involved
    """
    if len(trades) == 1:
        # Single trade action - create one entry
        trade = trades[0]
        return [{
            "when_utc": ts_utc,
            "team": trade["team"],
            "player": f"Traded <strong>{trade['player']}</strong>",
            "bid": trade["bid"],
            "action_type": "Combined",
            "added_player": _extract_player_info_from_dict(trade),
            "dropped_player": {
                "player_id": None,
                "position": "",
                "pro_team": "",
                "name": ""
            }
        }]

    # Group trades by team - ESPN only supports two-team trades
    team_trades = defaultdict(list)
    for trade in trades:
        team_trades[trade["team"]].append(trade)

    # Get the two teams involved
    teams = list(team_trades.keys())
    if len(teams) != 2:
        # Fallback for unexpected multi-team scenario
        team1, team2 = teams[0], teams[1]
    else:
        team1, team2 = teams

    # Get players for each team
    team1_players = [f"<strong>{t['player']}</strong>" for t in team_trades[team1]]
    team2_players = [f"<strong>{t['player']}</strong>" for t in team_trades[team2]]

    # Create trade entries for both teams
    trade_items = []

    # Team 1 entry (what they gave up for what they received)
    team1_trade_text = f"Traded {', '.join(team1_players)} for {', '.join(team2_players)}"
    trade_items.append({
        "when_utc": ts_utc,
        "team": team1,
        "player": team1_trade_text,
        "bid": max(t["bid"] for t in trades),
        "action_type": "Combined",
        "added_player": _extract_player_info_from_dict(team_trades[team1][0]),
        "dropped_player": {
            "player_id": None,
            "position": "",
            "pro_team": "",
            "name": ""
        }
    })

    # Team 2 entry (what they gave up for what they received)
    team2_trade_text = f"Traded {', '.join(team2_players)} for {', '.join(team1_players)}"
    trade_items.append({
        "when_utc": ts_utc,
        "team": team2,
        "player": team2_trade_text,
        "bid": max(t["bid"] for t in trades),
        "action_type": "Combined",
        "added_player": _extract_player_info_from_dict(team_trades[team2][0]),
        "dropped_player": {
            "player_id": None,
            "position": "",
            "pro_team": "",
            "name": ""
        }
    })

    return trade_items


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
        return _process_trades(trades, ts_utc)

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
            "added_player": _extract_player_info_from_dict(item) if not is_drop else {
                "player_id": None,
                "position": "",
                "pro_team": "",
                "name": ""
            },
            "dropped_player": _extract_player_info_from_dict(item) if is_drop else {
                "player_id": None,
                "position": "",
                "pro_team": "",
                "name": ""
            }
        }
        combined_items.append(combined_item)
    return combined_items


def _fetch_activity_with_retry(league: League,
                              max_retries: int = 3,
                              delay: float = 1.0) -> list[Any]:
    """Fetch league activity with retry logic for robustness.

    Args:
        league: League instance
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds

    Returns:
        List of raw activity data

    Raises:
        RuntimeError: If all retry attempts fail
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            raw_activity = league.recent_activity(size=300)
            return raw_activity
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                print(f"All API retry attempts failed. Last error: {e}")

    raise RuntimeError(f"Failed to fetch activity after {max_retries + 1} attempts: {last_error}")

def get_activity_since(league: League, since_utc: datetime) -> dict[str, list[dict[str, Any]]]:
    """Fetch and process league activity since the given UTC datetime."""
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    # Fetch recent activity with retry logic
    try:
        raw_activity = _fetch_activity_with_retry(league)
    except RuntimeError as e:
        print(f"Error fetching activity: {e}")
        return grouped

    if debug():
        _debug_dump_activity(raw_activity)

    # Process activities
    for act in raw_activity:
        if combined_items := _process_single_activity(act, since_utc):
            grouped["Combined"].extend(combined_items)

    def _get_sort_key(item: dict[str, Any]) -> tuple[datetime, int, str, str]:
        """Get sort key for activity items to avoid repeated lookups."""
        return (item["when_utc"], -item.get("bid", 0), item["team"], item["player"])

    for cat in grouped:
        grouped[cat].sort(key=_get_sort_key)
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
    lookback_hours = int(get_env(name="LOOKBACK_HOURS", required=False, default="24"))
    since_utc = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    lg = league_handle()
    grouped = get_activity_since(lg, since_utc)

    grouped_for_email = {
        cat: [{**i, "when_local": fmt_local(i["when_utc"])} for i in items]
        for cat, items in grouped.items()
    }

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
