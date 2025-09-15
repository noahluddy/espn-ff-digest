### ESPN Fantasy Foobtall Activity Digest

Generate a clean HTML digest of recent ESPN Fantasy Football league activity, with drops listed first. Outputs go to `reports/` and open in your default browser.

### Requirements
- Python 3.13+
- An ESPN Fantasy Football league

### Quick start
```bash
# From the project root, create and activate an isolated virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip inside the venv and install dependencies
pip install -r requirements.txt

# Create your .env file (copy the provided template)
cp .env.template .env
```

### Configure environment
Edit the `.env` file in the project root with the following variables:
```ini
LEAGUE_ID=1234567          # Your league ID (integer)
YEAR=2025                  # Season year (integer)
SWID={xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}  # Your SWID cookie value (including braces)
ESPN_S2=your_espn_s2_cookie_value            # Your espn_s2 cookie value

# Optional
LOOKBACK_HOURS=24          # Window for activity (default 24)
DEBUG=0                    # Just generate a local html file and write raw API output to debug_espn_raw.txt when 1/true
```

Tip: You can retrieve `LEAGUE_ID` from the URL and you can retrieve `SWID` and `ESPN_S2` from your browser's cookies while logged into `fantasy.espn.com`.

### Gmail API Setup (for email functionality)

To enable email sending functionality, you'll need to set up Gmail API credentials. This is a one-time setup process:

#### 1. Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top and select "New Project"
3. Enter a project name (e.g., "espn-ff-digest") and click "Create"

#### 2. Enable the Gmail API

1. In the left sidebar, go to "APIs & Services" > "Library"
2. Search for "Gmail API" and click on it
3. Click the "Enable" button

#### 3. Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" user type and click "Create"
3. Fill in the required fields:
   - App name: "ESPN Activity Digest" (or your preferred name)
   - User support email: your email
   - Developer contact information: your email
4. Click "Save and Continue"
5. On the "Scopes" page, click "Add or Remove Scopes"
6. Add the scope: `https://www.googleapis.com/auth/gmail.send`
7. Click "Update" then "Save and Continue"
8. Add yourself as a test user on the "Test users" page
9. Click "Save and Continue" to finish

#### 4. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Choose "Desktop application" as the application type
4. Give it a name (e.g., "ESPN Digest Desktop App")
5. Click "Create"
6. Click "Download JSON" to download the `credentials.json` file

#### 5. Generate Your Token

Create a temporary Python script to generate your token:

```python
# generate_token.py
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

with open('token.json', 'w') as token:
    token.write(creds.to_json())

print("Token saved to token.json")
```

Run the script:
```bash
python generate_token.py
```

This will open a browser window for you to authorize the application. After authorization, you'll have a `token.json` file.

#### 6. Base64 Encode the Token

Encode your token for use in environment variables:

```bash
# On macOS/Linux
base64 -i token.json -o token.json.b64

# On Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json")) | Out-File -FilePath "token.json.b64" -Encoding ASCII
```

#### 7. Add to Your .env File

Copy the contents of `token.json.b64` and add it to your `.env` file:

```ini
GMAIL_TOKEN_B64=your_base64_encoded_token_here
```

#### 8. Clean Up

You can now safely delete the temporary files:
```bash
rm credentials.json token.json token.json.b64 generate_token.py
```

**Important Notes:**
- The `credentials.json` file is only needed for the initial token generation
- For production/GitHub Actions, you only need the `GMAIL_TOKEN_B64` environment variable
- Keep your `.env` file secure and never commit it to version control
- **Token Refresh**: The access token expires after ~1 hour, but the refresh token (also in `token.json`) allows automatic renewal. The Google Auth library handles this automatically - no manual intervention needed in GitHub Actions
- **Long-term validity**: Refresh tokens can last months or years, so you won't need to regenerate the token frequently

### Run
```bash
python main.py
```

To enable debug logging of raw ESPN API activity (file is gitignored):
```bash
DEBUG=1 python main.py
```

The script writes an HTML file like `reports/activity-YYYY-MM-DD.html` and opens it automatically.

### Why a virtual environment is recommended
- Isolation: Keeps this project’s packages separate from system Python and other projects, avoiding version conflicts.
- Reproducibility: Everyone uses the same dependency versions (e.g., `urllib3<2`), so behavior is consistent.
- Safer installs: No `sudo`; you won’t modify system packages by accident.
- Predictable commands: Inside the venv, `python` and `pip` point to the project’s interpreter.

Handy commands:
- Activate: `source venv/bin/activate`
- Deactivate: `deactivate`
- Verify interpreter: `python -c 'import sys; print(sys.executable)'` (should show `.../venv/bin/python`)

### Notes and troubleshooting
- Dependencies are pinned for macOS compatibility (`urllib3<2`) to avoid LibreSSL warnings.
- Generated outputs (`reports/`) and debug logs (`debug_espn_raw.txt`) are ignored by Git via `.gitignore`.
- All credentials are read from environment variables; nothing sensitive is committed to the repo.
