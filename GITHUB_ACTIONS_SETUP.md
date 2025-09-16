# GitHub Actions Setup Guide

This guide explains how to set up the GitHub Action to run your ESPN Fantasy Football activity digest daily at 6am CT.

## Overview

The GitHub Action will:
- Run daily at 6:00 AM Central Time (12:00 PM UTC during CST)
- Fetch recent league activity from ESPN
- Generate an HTML report
- Send the report via Gmail to your configured recipients
- Clean up temporary files automatically

## Required GitHub Repository Secrets

You need to add the following secrets to your GitHub repository for the action to work:

### ESPN Fantasy Football Configuration
- `LEAGUE_ID`: Your ESPN Fantasy Football league ID (integer)
- `YEAR`: The fantasy football season year (integer, e.g., 2025)
- `SWID`: Your ESPN SWID cookie value (including braces: `{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}`)
- `ESPN_S2`: Your ESPN S2 cookie value

### Gmail Configuration
- `GMAIL_TOKEN_B64`: Your base64-encoded Gmail OAuth token (from `token.json.b64`)
- `EMAIL_FROM`: The sender email address (e.g., `your-email@gmail.com`)
- `EMAIL_TO`: Comma-separated list of primary recipients (e.g., `user1@example.com,user2@example.com`)
- `EMAIL_CC`: Comma-separated list of CC recipients (optional)
- `EMAIL_BCC`: Comma-separated list of BCC recipients (optional)

### Optional Configuration
- `LOOKBACK_HOURS`: Number of hours to look back for activity (default: 24)

## How to Add Secrets to GitHub

1. Go to your GitHub repository
2. Click on **Settings** (in the repository navigation)
3. In the left sidebar, click **Secrets and variables** > **Actions**
4. Click **New repository secret**
5. Add each secret with the exact name and value listed above
6. Click **Add secret** for each one

## Getting Your ESPN Cookie Values

1. Go to [fantasy.espn.com](https://fantasy.espn.com) and log in
2. Open your browser's Developer Tools (F12)
3. Go to the **Storage** tab (Safari), **Application** tab (Chrome), or **Storage** tab (Firefox)
4. Find **Cookies** and select `fantasy.espn.com`
5. Look for the `SWID` and `espn_s2` cookies
6. Copy their values (include the braces `{}` for SWID)

## Getting Your Gmail Token

If you haven't already set up your Gmail token, follow the Gmail API setup section in the main README.md file. The token should already be in `token.json.b64` format if you've completed that setup.

## Email Configuration

Make sure you have the following email settings configured:

- **EMAIL_FROM**: The email address that will send the digest (usually your Gmail address)
- **EMAIL_TO**: Primary recipients who will receive the digest (comma-separated)
- **EMAIL_CC**: Optional CC recipients (comma-separated)  
- **EMAIL_BCC**: Optional BCC recipients (comma-separated)

Example values:
```
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=league-member1@example.com,league-member2@example.com
EMAIL_CC=league-commissioner@example.com
EMAIL_BCC=backup-email@example.com
```

## Testing the Action

You can test the action manually:

1. Go to your GitHub repository
2. Click on **Actions** tab
3. Find the "Daily ESPN Fantasy Football Digest" workflow
4. Click **Run workflow** button
5. Select the main branch and click **Run workflow**

## Schedule Details

The action runs at:
- **6:00 AM Central Time** daily
- This translates to **12:00 PM UTC** (accounting for CST, which is typically when fantasy football season runs)

## Troubleshooting

### Common Issues

1. **Missing secrets**: Make sure all required secrets are added to your repository
2. **Invalid cookies**: ESPN cookies expire periodically - you may need to refresh them
3. **Gmail token expired**: The OAuth token may need to be regenerated if it's been a long time

### Viewing Logs

1. Go to **Actions** tab in your repository
2. Click on the latest workflow run
3. Click on the **send-digest** job
4. Review the logs for any error messages

### Debug Mode

If you need to debug issues, run the script locally with debug mode enabled:
```bash
DEBUG=1 python main.py
```

This will:
- Generate a local HTML file and open it in your browser
- Create a `debug_espn_raw.txt` file with raw ESPN API output
- Show detailed console output

**Note**: Don't enable debug mode in the GitHub Action - it's designed for local testing only and won't provide useful output in the cloud environment.

## Security Notes

- All sensitive data is stored as GitHub secrets (encrypted)
- The Gmail token is automatically cleaned up after each run
- No credentials are stored in the repository code
- The action runs in an isolated Ubuntu environment

## Cost Considerations

- GitHub Actions provides 2,000 free minutes per month for public repositories
- Each run takes approximately 1-2 minutes
- Daily runs = ~60 minutes per month (well within free limits)
- Private repositories have different limits

## Modifying the Schedule

To change when the action runs, edit the cron expression in `.github/workflows/daily-digest.yml`:

```yaml
schedule:
  - cron: '0 12 * * *'  # Current: 12:00 PM UTC (6:00 AM CT)
```

Common cron patterns:
- `'0 12 * * *'` - Daily at 12:00 PM UTC (6:00 AM CT)
- `'0 18 * * *'` - Daily at 6:00 PM UTC (12:00 PM CT)
- `'0 12 * * 1'` - Weekly on Mondays at 12:00 PM UTC
- `'0 12 1 * *'` - Monthly on the 1st at 12:00 PM UTC

Note: GitHub Actions uses UTC time, so you need to convert from your local timezone.
