"""Email rendering module for ESPN Fantasy Football activity digest.

This module provides functions to render HTML email content for fantasy football
league activity reports.
"""

import re
from datetime import datetime
from typing import Dict, List, Any

def _get_email_styles():
    """Get CSS styles for email rendering."""
    base = "font-family:Arial,Helvetica,sans-serif; color:#111; line-height:1.4;"
    return {
        "h1": "margin:0 0 6px; font-size:20px; " + base,
        "h2": "margin:0 0 18px; font-size:13px; color:#555; " + base,
        "h3": "margin:18px 0 8px; font-size:16px; color:#0B5FFF; " + base,
        "card": ("border:1px solid #e5e7eb; border-radius:10px; padding:0; "
                 "overflow:hidden;"),
        "wrap": "max-width:760px; margin:0 auto; padding:16px;",
        "tbl": "width:100%; border-collapse:collapse; " + base,
        "th": ("text-align:left; font-size:13px; background:#f6f7fb; "
               "border-bottom:1px solid #e5e7eb; padding:10px 12px;"),
        "td": ("font-size:14px; border-bottom:1px solid #e5e7eb; "
               "padding:10px 12px;"),
        "pill": ("display:inline-block; font-size:12px; color:#0B5FFF; "
                 "border:1px solid #bcd6ff; background:#eef5ff; "
                 "border-radius:999px; padding:2px 8px; margin-left:6px;")
    }


def render_email_html(grouped: Dict[str, List[Dict[str, Any]]],
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

    def strip_html_tags(text: str) -> str:
        """Remove simple HTML tags like <strong> from a string for plain-text extraction."""
        if not isinstance(text, str):
            return str(text)
        return re.sub(r"<[^>]+>", "", text)

    def render_dropped_players_table(items):
        """Render a simple list showing only dropped player names."""
        if not items:
            return ""

        rows = []
        for i in items:
            # Extract just the player name from the action text
            # Handle "Dropped Player A", "Dropped Player A for Player B",
            # and "Dropped Player A to claim Player B" formats
            action_text = strip_html_tags(i['player'])
            if ("Dropped" in action_text and
                    ("for" in action_text or "to claim" in action_text)):
                # Extract the dropped player name (first player in
                # "Dropped Player A for/to claim Player B")
                dropped_player = (action_text.split("Dropped ")[1]
                                 .split(" for ")[0].split(" to claim ")[0])
            elif "Dropped" in action_text:
                # Extract the dropped player name (from "Dropped Player A")
                dropped_player = action_text.split("Dropped ")[1]
            else:
                dropped_player = action_text

            rows.append(f'<tr><td style="{styles["td"]}">'
                       f'<strong>{dropped_player}</strong></td></tr>')

        rows_html = "".join(rows)
        return (f'<h3 style="{styles["h3"]}">Dropped Players'
                f'  <span style="{styles["pill"]}">{len(items)}</span></h3>'
                f'<div style="{styles["card"]}"><table role="presentation" '
                f'style="{styles["tbl"]}" cellpadding="0" cellspacing="0">'
                f'<tbody>{rows_html}</tbody></table></div>')

    def render_all_activity_table(items):
        """Render a single combined table with all actions sorted by time."""
        if not items:
            return ""

        rows = []
        for i in items:
            rows.append(
                f'<tr>'
                f'<td style="{styles["td"]}">{i["when_local"]}</td>'
                f'<td style="{styles["td"]}">{i["team"]}</td>'
                f'<td style="{styles["td"]}">{i["player"]}</td>'
                f'</tr>'
            )

        rows_html = "".join(rows)
        return (f'<h3 style="{styles["h3"]}">All Activity'
                f'  <span style="{styles["pill"]}">{len(items)}</span></h3>'
                f'<div style="{styles["card"]}"><table role="presentation" '
                f'style="{styles["tbl"]}" cellpadding="0" cellspacing="0">'
                f'<thead><tr>'
                f'<th style="{styles["th"]}">When (CDT)</th>'
                f'<th style="{styles["th"]}">Team</th>'
                f'<th style="{styles["th"]}">Action</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table></div>')

    # Get all combined actions and sort by time
    all_actions = grouped.get("Combined", [])
    all_actions.sort(key=lambda d: d.get("when_utc", datetime.now()))

    # Get dropped players for the separate table
    dropped_players = [action for action in all_actions if "Dropped" in action.get("player", "")]

    sections = []

    # Add Players Dropped table if there are any
    if dropped_players:
        sections.append(render_dropped_players_table(dropped_players))

    # Add All Activity table
    if not all_actions:
        sections.append(f'<div style="{styles["card"]};padding:14px 16px;'
                       f'{styles["h1"].split(";")[1]}">'
                       f'No activity {window_desc}.</div>')
    else:
        sections.append(render_all_activity_table(all_actions))

    body = "".join(sections)
    return (f'<!doctype html><meta charset="utf-8">'
            f'<div style="{styles["wrap"]}">'
            f'<h1 style="{styles["h1"]}">Activity for {league_title}</h1>'
            f'<h2 style="{styles["h2"]}">{window_desc}</h2>'
            f'{body}</div>')
