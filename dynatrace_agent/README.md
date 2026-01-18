# 🔔 Dynatrace Daily Architecture Analysis Agent

A macOS-native agent that runs daily at **11:00 AM IST** to analyze your Dynatrace environment and send you an iMessage notification with key insights.

## Features

- **📊 Architecture Health Analysis**
  - Problem summary (critical, warnings, total)
  - OneAgent fleet health and version distribution
  - ActiveGate connection status
  - Synthetic monitor overview

- **🔔 iMessage Notifications**
  - Daily summary delivered to your iPhone/Mac
  - Uses native macOS Messages app
  - No third-party services required

- **⏰ Automated Scheduling**
  - Runs daily at 11:00 AM IST
  - Uses macOS LaunchAgent (survives restarts)
  - Catches up if your Mac was asleep

## Quick Start

### 1. Download and Install

```bash
# Navigate to the agent folder
cd ~/Downloads/dynatrace_agent

# Make install script executable
chmod +x install.sh

# Run installer
./install.sh
```

### 2. Configure Credentials

Edit the config file:
```bash
nano ~/dynatrace_agent/config.env
```

Fill in your values:
```bash
# Your Dynatrace tenant
DYNATRACE_TENANT_URL=https://abc12345.live.dynatrace.com

# API Token (generate in Dynatrace)
DYNATRACE_API_TOKEN=dt0c01.XXXXXXXX.YYYYYYYY

# Your phone number (with country code)
IMESSAGE_RECIPIENT=+919876543210
```

### 3. Grant Permissions

Go to **System Settings > Privacy & Security > Automation**:
- Allow **Terminal** (or your terminal app) to control **Messages**

### 4. Test It

```bash
python3 ~/dynatrace_agent/dynatrace_daily_agent.py
```

You should receive an iMessage!

---

## Detailed Setup

### Creating a Dynatrace API Token

1. Open your Dynatrace environment
2. Go to **Settings** (gear icon) → **Integration** → **Dynatrace API**
3. Click **Generate token**
4. Name it: `Daily Agent`
5. Enable these scopes:
   - `problems.read` - Read problems
   - `entities.read` - Read entities  
   - `settings.read` - Read settings
   - `activeGates.read` - Read ActiveGates
   - `syntheticLocations.read` - Read synthetic monitors
6. Click **Generate** and copy the token

### iMessage Setup Requirements

For iMessage to work:
1. **Messages app** must be signed into your Apple ID
2. The recipient number must be in your **Contacts** OR have an **existing conversation**
3. **Terminal** must have **Automation** permissions for Messages

To add yourself to contacts (for self-notifications):
1. Open **Contacts** app
2. Add a new contact with your phone number
3. Open **Messages** and send yourself a test message first

### Understanding the Schedule

The agent uses macOS LaunchAgent, which:
- Runs at **11:00 AM local time** (your Mac's timezone)
- If your Mac is **asleep** at 11 AM, it runs when you wake it
- **Survives reboots** - no need to restart anything
- Runs in the **background** - no terminal window needed

---

## Managing the Agent

### Check Status
```bash
launchctl list | grep dynatrace
```

### View Logs
```bash
# Main log
tail -f ~/Library/Logs/dynatrace_agent.log

# System output
tail -f ~/Library/Logs/dynatrace_agent_stdout.log
tail -f ~/Library/Logs/dynatrace_agent_stderr.log
```

### Run Manually
```bash
python3 ~/dynatrace_agent/dynatrace_daily_agent.py
```

### Stop the Agent
```bash
launchctl unload ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
```

### Restart the Agent
```bash
launchctl unload ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
launchctl load ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
```

### Change Schedule

Edit the plist file:
```bash
nano ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
```

Find and modify:
```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>11</integer>  <!-- Change this for different hour -->
    <key>Minute</key>
    <integer>0</integer>   <!-- Change this for different minute -->
</dict>
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
launchctl load ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
```

### Uninstall

```bash
# Stop the agent
launchctl unload ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist

# Remove files
rm ~/Library/LaunchAgents/com.observability.dynatrace-daily-agent.plist
rm -rf ~/dynatrace_agent
```

---

## Sample Report

Here's what your daily iMessage will look like:

```
🔔 Dynatrace Daily Report
📅 2026-01-18 11:00 IST

🟢 Healthy | Score: 95/100

📊 PROBLEMS (24h)
• Critical: 0
• Warnings: 2
• Total: 3

🖥️ ONEAGENT FLEET
• Total Hosts: 247
• Versions in use: 2

🌐 ACTIVEGATES
• Connected: 5/5

📰 Check docs.dynatrace.com for latest updates
```

---

## Troubleshooting

### iMessage Not Sending

1. **Check permissions**: System Settings > Privacy & Security > Automation
2. **Verify recipient**: Must be in Contacts or have existing conversation
3. **Test AppleScript directly**:
   ```bash
   osascript -e 'tell application "Messages" to send "Test" to buddy "+1234567890" of (1st service whose service type = iMessage)'
   ```

### Agent Not Running at Scheduled Time

1. **Check if loaded**:
   ```bash
   launchctl list | grep dynatrace
   ```
2. **Check Mac wasn't asleep**: LaunchAgent runs when Mac wakes
3. **Check logs** for errors

### API Connection Errors

1. **Verify tenant URL** - include `/e/environment-id` for Managed
2. **Check token permissions** - needs read access
3. **Test API directly**:
   ```bash
   curl -X GET "https://YOUR_TENANT/api/v2/problems" \
     -H "Authorization: Api-Token YOUR_TOKEN"
   ```

---

## Customization

### Add More Analysis

Edit `dynatrace_daily_agent.py` to add custom checks:

```python
def _analyze_custom(self) -> dict:
    """Add your custom analysis here"""
    # Use self.client._get() to call any Dynatrace API endpoint
    data = self.client._get("your/endpoint")
    return {"result": data}
```

### Change Report Format

Modify the `generate_daily_report()` function to customize the message content.

### Add More Notification Channels

The architecture supports adding Slack, Teams, or email - just add a new function similar to `send_imessage()`.

---

## Files

```
~/dynatrace_agent/
├── dynatrace_daily_agent.py  # Main agent script
├── config.env                 # Your configuration
├── install.sh                 # Installation script
├── README.md                  # This file
└── reports/                   # Backup reports (if iMessage fails)

~/Library/LaunchAgents/
└── com.observability.dynatrace-daily-agent.plist  # Scheduler

~/Library/Logs/
├── dynatrace_agent.log        # Main application log
├── dynatrace_agent_stdout.log # System output
└── dynatrace_agent_stderr.log # System errors
```

---

## Support

Built for the Observability Operations team. For issues:
1. Check logs first
2. Test components individually
3. Verify permissions and credentials

---

*Happy Monitoring! 🚀*
