"""Gmail sending module for ESPN Fantasy Football activity digest.

This module provides functions to send HTML emails via Gmail API for fantasy
football league activity reports.
"""

import base64
import json
from typing import Any
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from utils import get_env

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
load_dotenv()  # pulls EMAIL_* from .env

def _parse_list(env_value: str | None) -> list[str]:
    """Parse comma or semicolon separated email addresses from environment variable.
    
    Args:
        env_value: String containing email addresses separated by commas or semicolons
        
    Returns:
        List of cleaned email addresses
    """
    if not env_value:
        return []
    parts = [p.strip() for p in env_value.replace(";", ",").split(",")]
    return [p for p in parts if p]

def _get_service():
    """Get authenticated Gmail service instance.
    
    Returns:
        Gmail service instance for sending emails
        
    Raises:
        ValueError: If token is missing or invalid
    """
    # Read token from environment variable (base64 encoded)
    token_b64 = get_env("GMAIL_TOKEN_B64")
    
    # Decode base64 token (strip whitespace including newlines)
    try:
        token_data = json.loads(base64.b64decode(token_b64.strip()).decode('utf-8'))
    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Failed to decode base64 token: {e}") from e
    
    # Create credentials object from token data
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    
    # Refresh token if needed
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # If we can't refresh, we need to re-authenticate using the credentials
            # This shouldn't happen in GitHub Actions if token is valid
            raise ValueError("Invalid or expired token and no refresh token available")
    
    return build("gmail", "v1", credentials=creds)

def send_gmail_html(subject: str, html: str) -> None:
    """Send HTML email via Gmail API.
    
    Args:
        subject: Email subject line
        html: HTML content of the email
        
    Raises:
        ValueError: If no recipients are specified or service fails
    """
    from_addr = get_env("EMAIL_FROM")
    to_list = _parse_list(get_env("EMAIL_TO", required=False, default="")) or []
    cc_list = _parse_list(get_env("EMAIL_CC", required=False, default="")) or []
    bcc_list = _parse_list(get_env("EMAIL_BCC", required=False, default="")) or []

    if not to_list and not bcc_list:
        raise ValueError("Need at least one recipient in TO or BCC.")

    msg = MIMEText(html, "html")
    if to_list:
        msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if bcc_list:
        msg["Bcc"] = ", ".join(bcc_list)
    msg["Subject"] = subject
    msg["From"] = from_addr or (to_list[0] if to_list else "")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc = _get_service()
    # pylint: disable=no-member
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
