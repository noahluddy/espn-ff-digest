"""Email rendering module for ESPN Fantasy Football activity digest.

This module provides functions to render HTML email content for fantasy football
league activity reports.
"""

import re
from io import StringIO
from typing import Any

from utils import get_player_headshot_url, get_team_logo_url, is_dst_player, strip_html_tags

def _get_email_styles() -> dict[str, str]:
    """Get CSS styles for email rendering - enhanced and email-safe.

    Returns:
        Dictionary mapping style names to CSS strings
    """
    base = "font-family:Arial,Helvetica,sans-serif; color:#1a1a1a; line-height:1.5;"
    return {
        "h1": "margin:0 0 8px; font-size:24px; font-weight:bold; color:#1a1a1a; " + base,
        "h2": "margin:0 0 24px; font-size:14px; color:#666; font-weight:normal; " + base,
        "h3": "margin:24px 0 12px; font-size:18px; color:#1e40af; font-weight:600; " + base,
        "card": ("border:1px solid #d1d5db; border-radius:12px; padding:0; "
                 "overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); "
                 "background:#ffffff;"),
        "wrap": "max-width:800px; margin:0 auto; padding:20px; background:#f9fafb;",
        "tbl": "width:100%; border-collapse:collapse; " + base,
        "th": ("text-align:left; font-size:13px; font-weight:600; background:#f8fafc; "
               "border-bottom:2px solid #e5e7eb; padding:12px 16px; color:#374151;"),
        "td": ("font-size:14px; border-bottom:1px solid #f3f4f6; "
               "padding:12px 16px; vertical-align:top;"),
        "pill": ("display:inline-block; font-size:11px; font-weight:600; color:#1e40af; "
                 "border:1px solid #93c5fd; background:#dbeafe; "
                 "border-radius:12px; padding:3px 10px; margin-left:8px;"),
        "player_row": "padding:8px 0; border-bottom:1px solid #f3f4f6;",
        "player_name": ("font-weight:600; color:#1a1a1a; font-size:15px; "
                       "display:block; line-height:1.3; word-break:break-word;"),
        "player_details": "color:#6b7280; font-size:13px; margin-top:2px;",
        "headshot": ("display:block; width:64px; height:48px; border-radius:50%; "
                    "vertical-align:middle;"),
        "team_logo": ("display:block; width:48px; height:48px; border-radius:50%; "
                     "vertical-align:middle; padding-right:9px;"),
        "media_tbl": "border-collapse:collapse; border-spacing:0; width:100%;",
        "media_img_cell": "width:64px; padding:0 12px 0 0; vertical-align:middle;",
        "media_img_cell_dst": "width:64px; padding:0 12px 0 7px; vertical-align:middle;",
        "media_text_cell": "vertical-align:middle; width:100%;",
        "action_text": "color:#1a1a1a; font-size:14px;",
        "team_name": "font-weight:600; color:#374151; font-size:14px;",
        "timestamp": "color:#6b7280; font-size:13px; font-family:monospace;"
    }


def extract_player_info_from_action(action_text: str) -> tuple[str, int | None]:
    """Extract player name and ID from action text.

    Returns:
        Tuple of (player_name, player_id) where player_id may be None
    """
    # This is a simplified extraction - in practice, you'd need to pass
    # the actual player objects with IDs from the main processing
    player_name = re.sub(r'<[^>]+>', '', action_text)  # Remove HTML tags
    return player_name, None


def format_player_with_headshot(player_name: str, player_id: int | None = None,
                               team_abbrev: str = "") -> str:
    """Format player with headshot image for email display (simplified - no redundant info)."""
    styles = _get_email_styles()
    output = StringIO()

    # Check if this is a D/ST team
    if is_dst_player(player_name) and team_abbrev:
        # Use team logo for D/ST (square)
        logo_url = get_team_logo_url(team_abbrev)
        output.write(f'<div style="{styles["player_row"]}">')
        output.write(f'<table role="presentation" style="{styles["media_tbl"]}" cellpadding="0" cellspacing="0">')
        output.write(f'<tr>')
        output.write(f'<td style="{styles["media_img_cell_dst"]}">')
        output.write(f'<img src="{logo_url}" alt="{player_name}" style="{styles["team_logo"]}" />')
        output.write(f'</td>')
        output.write(f'<td style="{styles["media_text_cell"]}">')
        output.write(f'<span style="{styles["player_name"]}">{player_name}</span>')
        output.write(f'</td>')
        output.write(f'</tr>')
        output.write(f'</table>')
        output.write(f'</div>')
    elif player_id:
        # Use player headshot for regular players
        headshot_url = get_player_headshot_url(player_id)
        output.write(f'<div style="{styles["player_row"]}">')
        output.write(f'<table role="presentation" style="{styles["media_tbl"]}" cellpadding="0" cellspacing="0">')
        output.write(f'<tr>')
        output.write(f'<td style="{styles["media_img_cell"]}">')
        output.write(f'<img src="{headshot_url}" alt="{player_name}" style="{styles["headshot"]}" />')
        output.write(f'</td>')
        output.write(f'<td style="{styles["media_text_cell"]}">')
        output.write(f'<span style="{styles["player_name"]}">{player_name}</span>')
        output.write(f'</td>')
        output.write(f'</tr>')
        output.write(f'</table>')
        output.write(f'</div>')
    else:
        # No image available
        output.write(f'<div style="{styles["player_row"]}">')
        output.write(f'<table role="presentation" style="{styles["media_tbl"]}" cellpadding="0" cellspacing="0">')
        output.write(f'<tr>')
        output.write(f'<td style="{styles["media_text_cell"]}">')
        output.write(f'<span style="{styles["player_name"]}">{player_name}</span>')
        output.write(f'</td>')
        output.write(f'</tr>')
        output.write(f'</table>')
        output.write(f'</div>')

    return output.getvalue()


def render_email_html(grouped: dict[str, list[dict[str, Any]]],
                     window_desc: str, league_title: str) -> str:
    """Render HTML email content for fantasy football league activity.

    Args:
        grouped: Dictionary of activity categories with their items
        window_desc: Description of the time window for the activity
        league_title: Title of the fantasy football league

    Returns:
        HTML string for the email content
    """
    styles = _get_email_styles()

    def render_dropped_players_table(items):
        """Render a simple list showing only dropped player names with enhanced styling."""
        if not items:
            return ""

        output = StringIO()
        output.write(f'<h3 style="{styles["h3"]}">Dropped Players')
        output.write(f'  <span style="{styles["pill"]}">{len(items)}</span></h3>')
        output.write(f'<div style="{styles["card"]}"><table role="presentation" ')
        output.write(f'style="{styles["tbl"]}" cellpadding="0" cellspacing="0">')
        output.write(f'<tbody>')

        for i in items:
            # Extract dropped player information from the new data structure
            dropped_player_info = i.get('dropped_player', {})
            dropped_player_name = dropped_player_info.get('name', '')
            dropped_player_id = dropped_player_info.get('player_id')

            # If no dropped player info in new structure, fall back to parsing action text
            if not dropped_player_name:
                action_text = strip_html_tags(i['player'])
                if ("Dropped" in action_text and
                        ("for" in action_text or "to claim" in action_text)):
                    # Extract the dropped player name (first player in
                    # "Dropped Player A for/to claim Player B")
                    dropped_player_name = (action_text.split("Dropped ")[1]
                                         .split(" for ")[0].split(" to claim ")[0])
                elif "Dropped" in action_text:
                    # Extract the dropped player name (from "Dropped Player A")
                    dropped_player_name = action_text.split("Dropped ")[1]
                else:
                    dropped_player_name = action_text

            # Get team abbreviation for D/ST teams
            team_abbrev = dropped_player_info.get('pro_team', '')

            # Format player with headshot
            player_html = format_player_with_headshot(dropped_player_name, dropped_player_id, team_abbrev)
            output.write(f'<tr><td style="{styles["td"]}">{player_html}</td></tr>')

        output.write(f'</tbody></table></div>')
        return output.getvalue()

    def render_all_activity_table(items):
        """Render a single combined table with all actions sorted by time with enhanced styling."""
        if not items:
            return ""

        output = StringIO()
        output.write(f'<h3 style="{styles["h3"]}">All Activity')
        output.write(f'  <span style="{styles["pill"]}">{len(items)}</span></h3>')
        output.write(f'<div style="{styles["card"]}"><table role="presentation" ')
        output.write(f'style="{styles["tbl"]}" cellpadding="0" cellspacing="0">')
        output.write(f'<thead><tr>')
        output.write(f'<th style="{styles["th"]}">When (CDT)</th>')
        output.write(f'<th style="{styles["th"]}">Team</th>')
        output.write(f'<th style="{styles["th"]}">Action</th>')
        output.write(f'</tr></thead><tbody>')

        for i in items:
            # Enhanced row with better styling
            output.write(f'<tr>')
            output.write(f'<td style="{styles["td"]}; {styles["timestamp"]}">{i["when_local"]}</td>')
            output.write(f'<td style="{styles["td"]}; {styles["team_name"]}">{i["team"]}</td>')
            output.write(f'<td style="{styles["td"]}; {styles["action_text"]}">{i["player"]}</td>')
            output.write(f'</tr>')

        output.write(f'</tbody></table></div>')
        return output.getvalue()

    # Get all combined actions (already sorted by main.py)
    all_actions = grouped.get("Combined", [])

    # Get dropped players for the separate table
    dropped_players = [action for action in all_actions if "Dropped" in action.get("player", "")]

    output = StringIO()
    output.write(f'<!doctype html><meta charset="utf-8">')
    output.write(f'<div style="{styles["wrap"]}">')
    output.write(f'<h1 style="{styles["h1"]}">Digest for {league_title}</h1>')
    output.write(f'<h2 style="{styles["h2"]}">{window_desc}</h2>')

    # Add Players Dropped table if there are any
    if dropped_players:
        output.write(render_dropped_players_table(dropped_players))

    # Add All Activity table
    if not all_actions:
        output.write(f'<div style="{styles["card"]};padding:14px 16px;'
                    f'{styles["h1"].split(";")[1]}">'
                    f'No activity {window_desc}.</div>')
    else:
        output.write(render_all_activity_table(all_actions))

    output.write(f'</div>')
    return output.getvalue()
