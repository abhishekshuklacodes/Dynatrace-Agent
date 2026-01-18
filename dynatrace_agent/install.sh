#!/bin/bash

# ============================================================================
# DYNATRACE DAILY AGENT - INSTALLATION SCRIPT
# ============================================================================
# 
# This script will:
# 1. Create the agent directory structure
# 2. Install required Python packages
# 3. Set up the LaunchAgent for daily scheduling at 11 AM IST
# 4. Grant necessary permissions
#
# Run with: chmod +x install.sh && ./install.sh
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "=============================================="
echo "  Dynatrace Daily Agent Installer"
echo "=============================================="
echo -e "${NC}"

# Get current username
USERNAME=$(whoami)
HOME_DIR=$(eval echo ~$USERNAME)
INSTALL_DIR="$HOME_DIR/dynatrace_agent"
LAUNCH_AGENTS_DIR="$HOME_DIR/Library/LaunchAgents"

echo -e "${YELLOW}Installing for user: ${USERNAME}${NC}"
echo -e "${YELLOW}Install directory: ${INSTALL_DIR}${NC}"
echo ""

# Step 1: Create directory structure
echo -e "${BLUE}[1/6] Creating directory structure...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/reports"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$LAUNCH_AGENTS_DIR"
echo -e "${GREEN}✓ Directories created${NC}"

# Step 2: Copy files to install directory (if not already there)
echo -e "${BLUE}[2/6] Setting up agent files...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/dynatrace_daily_agent.py" ]; then
    cp "$SCRIPT_DIR/dynatrace_daily_agent.py" "$INSTALL_DIR/"
    echo -e "${GREEN}✓ Agent script copied${NC}"
fi

if [ -f "$SCRIPT_DIR/config.env" ] && [ ! -f "$INSTALL_DIR/config.env" ]; then
    cp "$SCRIPT_DIR/config.env" "$INSTALL_DIR/"
    echo -e "${GREEN}✓ Config template copied${NC}"
fi

# Make the agent script executable
chmod +x "$INSTALL_DIR/dynatrace_daily_agent.py"

# Step 3: Install Python dependencies
echo -e "${BLUE}[3/6] Installing Python dependencies...${NC}"
pip3 install --user requests 2>/dev/null || pip3 install requests
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Step 4: Update and install LaunchAgent
echo -e "${BLUE}[4/6] Setting up LaunchAgent for 11 AM IST schedule...${NC}"

# Create the plist with correct username
PLIST_FILE="$LAUNCH_AGENTS_DIR/com.observability.dynatrace-daily-agent.plist"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.observability.dynatrace-daily-agent</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${INSTALL_DIR}/dynatrace_daily_agent.py</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>11</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME_DIR}</string>
    </dict>
    
    <key>StandardOutPath</key>
    <string>${HOME_DIR}/Library/Logs/dynatrace_agent_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME_DIR}/Library/Logs/dynatrace_agent_stderr.log</string>
    
    <key>Nice</key>
    <integer>10</integer>
    
    <key>TimeOut</key>
    <integer>300</integer>
</dict>
</plist>
EOF

echo -e "${GREEN}✓ LaunchAgent plist created${NC}"

# Step 5: Load the LaunchAgent
echo -e "${BLUE}[5/6] Loading LaunchAgent...${NC}"

# Unload if already loaded
launchctl unload "$PLIST_FILE" 2>/dev/null || true

# Load the new plist
launchctl load "$PLIST_FILE"
echo -e "${GREEN}✓ LaunchAgent loaded - will run daily at 11:00 AM${NC}"

# Step 6: Permissions reminder
echo -e "${BLUE}[6/6] Checking permissions...${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Grant these permissions in System Settings:${NC}"
echo ""
echo "1. Go to: System Settings > Privacy & Security > Automation"
echo "   Grant 'Terminal' (or your terminal app) access to 'Messages'"
echo ""
echo "2. Go to: System Settings > Privacy & Security > Accessibility"
echo "   Add your terminal app if using the fallback iMessage method"
echo ""
echo -e "${YELLOW}Press Enter after granting permissions...${NC}"
read

# Final summary
echo ""
echo -e "${GREEN}=============================================="
echo "  Installation Complete!"
echo "==============================================${NC}"
echo ""
echo -e "Agent Location:     ${BLUE}${INSTALL_DIR}${NC}"
echo -e "Config File:        ${BLUE}${INSTALL_DIR}/config.env${NC}"
echo -e "LaunchAgent:        ${BLUE}${PLIST_FILE}${NC}"
echo -e "Log Files:          ${BLUE}${HOME_DIR}/Library/Logs/dynatrace_agent*.log${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Edit config file: nano ${INSTALL_DIR}/config.env"
echo "2. Add your Dynatrace credentials and phone number"
echo "3. Test manually: python3 ${INSTALL_DIR}/dynatrace_daily_agent.py"
echo ""
echo -e "${GREEN}The agent will run automatically every day at 11:00 AM IST!${NC}"
echo ""

# Offer to open config file
echo -e "Would you like to edit the config file now? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    if command -v nano &> /dev/null; then
        nano "$INSTALL_DIR/config.env"
    elif command -v vim &> /dev/null; then
        vim "$INSTALL_DIR/config.env"
    else
        open "$INSTALL_DIR/config.env"
    fi
fi

echo ""
echo -e "${GREEN}Done! Your Dynatrace agent is ready.${NC}"
