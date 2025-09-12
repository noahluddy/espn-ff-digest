### ESPN Fantasy Foobtall Activity Digest

Generate a clean HTML digest of recent ESPN Fantasy Football league activity, with drops listed first. Outputs go to `reports/` and open in your default browser.

### Requirements
- Python 3.9+
- An ESPN Fantasy Football league

### Quick start
```bash
# From the project root, create and activate an isolated virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip inside the venv and install dependencies
pip install -r requirements.txt

# Create your .env file (copy the provided template)
cp ENV.template .env
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
DEBUG_ACTIVITY=0           # Write raw API output to debug_espn_raw.txt when 1/true
```

Tip: You can retrieve `LEAGUE_ID` from the URL and you can retrieve `SWID` and `ESPN_S2` from your browser’s cookies while logged into `fantasy.espn.com`.

### Run
```bash
python main.py
```

To enable debug logging of raw ESPN API activity (file is gitignored):
```bash
DEBUG_ACTIVITY=1 python main.py
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

### Optional: pre-commit hook
To prevent committing generated reports and debug logs, you can add a simple Git hook:
```bash
cat > .git/hooks/pre-commit <<'SH'
#!/bin/sh
blocked=$(git diff --cached --name-only | grep -E '^(reports/.*\.html|debug_.*\.txt)$')
if [ -n "$blocked" ]; then
  echo "Blocked generated files in commit:" >&2
  echo "$blocked" >&2
  exit 1
fi
SH
chmod +x .git/hooks/pre-commit
```


