"""Utility functions for ESPN Fantasy Football activity digest."""

import os
import re
from datetime import datetime
from typing import Any

from dateutil import tz

# Always display times in US Central Time (handles CST/CDT automatically)
CENTRAL_TIME = tz.gettz("America/Chicago")


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
    # If the value is empty string and we have a default, use the default
    if not val and default is not None:
        val = default
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


def strip_html_tags(text: str) -> str:
    """Remove simple HTML tags like <strong> from a string for plain-text extraction."""
    if not isinstance(text, str):
        return str(text)
    return re.sub(r"<[^>]+>", "", text)


def fmt_team(team_obj: Any) -> str:
    """Format team object to string with manager name in parentheses."""
    # Get the base team name
    team_name = (getattr(team_obj, "team_name", None) or
                 getattr(team_obj, "team_abbrev", None) or
                 str(team_obj))
    
    # Try to get the first manager's name
    manager_name = get_team_manager_name(team_obj)
    
    # Add manager name in brackets and italicized on a new line if available
    if manager_name and manager_name != "Unknown Manager":
        return f"{team_name}<br><i>[{manager_name}]</i>"
    
    return team_name


def get_team_manager_name(team_obj: Any) -> str:
    """Get all team manager names, deduplicated.
    
    Args:
        team_obj: Team object from ESPN API
        
    Returns:
        Comma-separated list of all unique manager names, or "Unknown Manager" if not available
    """
    if hasattr(team_obj, 'owners') and team_obj.owners:
        manager_names = []
        
        for owner in team_obj.owners:
            first_name = owner.get('firstName', '')
            last_name = owner.get('lastName', '')
            
            if first_name and last_name:
                full_name = f"{first_name} {last_name}"
            elif first_name:
                full_name = first_name
            elif last_name:
                full_name = last_name
            else:
                # Fallback to display name if first/last names aren't available
                full_name = owner.get('displayName', '')
            
            if full_name and full_name not in manager_names:
                manager_names.append(full_name)
        
        if manager_names:
            return ", ".join(manager_names)
    
    return "Unknown Manager"


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


def is_dst_player(player_name: str) -> bool:
    """Check if a player name represents a Defense/Special Teams unit."""
    return "D/ST" in player_name or "DST" in player_name


def get_player_headshot_url(player_id: int) -> str:
    """Get ESPN headshot URL for a player.

    Args:
        player_id: ESPN player ID

    Returns:
        URL string for the player's headshot image
    """
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{player_id}.png"


def get_team_logo_url(team_abbrev: str) -> str:
    """Get ESPN team logo URL.

    Args:
        team_abbrev: Team abbreviation (e.g., 'GB', 'KC')

    Returns:
        URL string for the team's logo image
    """
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{team_abbrev.lower()}.png"


def fmt_local(dt_utc: datetime) -> str:
    """Format UTC datetime to local time string."""
    return dt_utc.astimezone(CENTRAL_TIME).strftime("%Y-%m-%d %I:%M %p")
