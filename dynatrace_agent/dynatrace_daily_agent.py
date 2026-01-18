#!/usr/bin/env python3
"""
Dynatrace Daily Architecture Analysis Agent
============================================
Runs daily at 11 AM IST to:
1. Fetch latest Dynatrace release notes and updates
2. Perform architecture health analysis via API
3. Send summary notification via iMessage

Author: Built for Abhi's Observability Operations Team
"""

import os
import json
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path
import logging

# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================

CONFIG = {
    # Dynatrace Configuration
    "DYNATRACE_TENANT_URL": os.environ.get("DYNATRACE_TENANT_URL", "https://YOUR_TENANT.live.dynatrace.com"),
    "DYNATRACE_API_TOKEN": os.environ.get("DYNATRACE_API_TOKEN", "YOUR_API_TOKEN"),
    
    # iMessage Configuration - Your phone number or Apple ID email
    "IMESSAGE_RECIPIENT": os.environ.get("IMESSAGE_RECIPIENT", "+1234567890"),
    
    # Analysis Configuration
    "PROBLEM_LOOKBACK_HOURS": 24,
    "CHECK_ONEAGENT_HEALTH": True,
    "CHECK_ACTIVEGATE_HEALTH": True,
    "CHECK_SYNTHETIC_MONITORS": True,
    
    # Logging
    "LOG_FILE": os.path.expanduser("~/Library/Logs/dynatrace_agent.log"),
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    log_dir = os.path.dirname(CONFIG["LOG_FILE"])
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(CONFIG["LOG_FILE"]),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# IMESSAGE NOTIFICATION
# ============================================================================

def send_imessage(recipient: str, message: str) -> bool:
    """
    Send iMessage using AppleScript via osascript.
    
    Args:
        recipient: Phone number or Apple ID email
        message: Message content to send
    
    Returns:
        True if successful, False otherwise
    """
    # Escape special characters for AppleScript
    message = message.replace('"', '\\"').replace("'", "\\'")
    
    applescript = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{recipient}" of targetService
        send "{message}" to targetBuddy
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"iMessage sent successfully to {recipient}")
            return True
        else:
            logger.error(f"iMessage failed: {result.stderr}")
            # Fallback: Try alternative AppleScript method
            return send_imessage_fallback(recipient, message)
    except subprocess.TimeoutExpired:
        logger.error("iMessage send timed out")
        return False
    except Exception as e:
        logger.error(f"iMessage error: {e}")
        return False

def send_imessage_fallback(recipient: str, message: str) -> bool:
    """
    Fallback method using System Events for iMessage.
    Works better for new conversations.
    """
    applescript = f'''
    tell application "Messages"
        activate
        delay 0.5
    end tell
    
    tell application "System Events"
        tell process "Messages"
            keystroke "n" using command down
            delay 0.3
            keystroke "{recipient}"
            delay 0.3
            key code 36
            delay 0.3
            keystroke "{message}"
            delay 0.2
            key code 36
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Fallback iMessage error: {e}")
        return False

# ============================================================================
# DYNATRACE API CLIENT
# ============================================================================

class DynatraceClient:
    """Client for interacting with Dynatrace API v2"""
    
    def __init__(self, tenant_url: str, api_token: str):
        self.base_url = tenant_url.rstrip('/')
        self.headers = {
            "Authorization": f"Api-Token {api_token}",
            "Content-Type": "application/json"
        }
    
    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to Dynatrace API"""
        url = f"{self.base_url}/api/v2/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {}
    
    def get_problems(self, hours: int = 24) -> dict:
        """Get problems from the last N hours"""
        from_time = datetime.utcnow() - timedelta(hours=hours)
        params = {
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "problemSelector": "status(\"open\")"
        }
        return self._get("problems", params)
    
    def get_hosts(self) -> dict:
        """Get all monitored hosts"""
        params = {"entitySelector": "type(HOST)", "fields": "+properties.monitoringMode,+properties.state"}
        return self._get("entities", params)
    
    def get_oneagent_info(self) -> dict:
        """Get OneAgent deployment status"""
        params = {
            "entitySelector": "type(HOST)",
            "fields": "+properties.installerVersion,+properties.monitoringMode"
        }
        return self._get("entities", params)
    
    def get_activegates(self) -> dict:
        """Get ActiveGate status"""
        return self._get("activeGates")
    
    def get_synthetic_monitors(self) -> dict:
        """Get synthetic monitor status"""
        return self._get("synthetic/monitors")
    
    def get_settings(self, schema_id: str) -> dict:
        """Get settings by schema ID"""
        params = {"schemaIds": schema_id}
        return self._get("settings/objects", params)

# ============================================================================
# ARCHITECTURE ANALYSIS
# ============================================================================

class ArchitectureAnalyzer:
    """Analyzes Dynatrace environment architecture health"""
    
    def __init__(self, client: DynatraceClient):
        self.client = client
        self.issues = []
        self.metrics = {}
    
    def analyze_all(self) -> dict:
        """Run all architecture analysis checks"""
        logger.info("Starting architecture analysis...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "problems": self._analyze_problems(),
            "oneagent": self._analyze_oneagent(),
            "activegate": self._analyze_activegate(),
            "synthetic": self._analyze_synthetic(),
            "summary": {}
        }
        
        # Generate summary
        results["summary"] = self._generate_summary(results)
        
        return results
    
    def _analyze_problems(self) -> dict:
        """Analyze current problems"""
        data = self.client.get_problems(CONFIG["PROBLEM_LOOKBACK_HOURS"])
        problems = data.get("problems", [])
        
        critical = [p for p in problems if p.get("severityLevel") == "ERROR"]
        warnings = [p for p in problems if p.get("severityLevel") == "WARNING"]
        
        if len(critical) > 0:
            self.issues.append(f"🔴 {len(critical)} critical problems detected")
        
        return {
            "total": len(problems),
            "critical": len(critical),
            "warnings": len(warnings),
            "details": [{"title": p.get("title"), "severity": p.get("severityLevel")} 
                       for p in problems[:5]]  # Top 5 problems
        }
    
    def _analyze_oneagent(self) -> dict:
        """Analyze OneAgent fleet health"""
        if not CONFIG["CHECK_ONEAGENT_HEALTH"]:
            return {"skipped": True}
        
        data = self.client.get_oneagent_info()
        entities = data.get("entities", [])
        
        total_hosts = len(entities)
        monitoring_modes = {}
        versions = {}
        
        for entity in entities:
            props = entity.get("properties", {})
            mode = props.get("monitoringMode", "unknown")
            version = props.get("installerVersion", "unknown")
            
            monitoring_modes[mode] = monitoring_modes.get(mode, 0) + 1
            versions[version] = versions.get(version, 0) + 1
        
        # Check for version fragmentation
        if len(versions) > 3:
            self.issues.append(f"⚠️ OneAgent version fragmentation: {len(versions)} different versions")
        
        return {
            "total_hosts": total_hosts,
            "monitoring_modes": monitoring_modes,
            "version_count": len(versions),
            "top_versions": dict(sorted(versions.items(), key=lambda x: x[1], reverse=True)[:3])
        }
    
    def _analyze_activegate(self) -> dict:
        """Analyze ActiveGate health"""
        if not CONFIG["CHECK_ACTIVEGATE_HEALTH"]:
            return {"skipped": True}
        
        data = self.client.get_activegates()
        activegates = data.get("activeGates", [])
        
        total = len(activegates)
        connected = sum(1 for ag in activegates if ag.get("connected", False))
        offline = total - connected
        
        if offline > 0:
            self.issues.append(f"🔴 {offline} ActiveGate(s) offline")
        
        return {
            "total": total,
            "connected": connected,
            "offline": offline
        }
    
    def _analyze_synthetic(self) -> dict:
        """Analyze synthetic monitors"""
        if not CONFIG["CHECK_SYNTHETIC_MONITORS"]:
            return {"skipped": True}
        
        data = self.client.get_synthetic_monitors()
        monitors = data.get("monitors", [])
        
        enabled = sum(1 for m in monitors if m.get("enabled", False))
        disabled = len(monitors) - enabled
        
        return {
            "total": len(monitors),
            "enabled": enabled,
            "disabled": disabled
        }
    
    def _generate_summary(self, results: dict) -> dict:
        """Generate overall health summary"""
        health_score = 100
        
        # Deduct points for issues
        problems = results["problems"]
        health_score -= problems.get("critical", 0) * 10
        health_score -= problems.get("warnings", 0) * 2
        
        # Deduct for offline ActiveGates
        ag = results.get("activegate", {})
        health_score -= ag.get("offline", 0) * 15
        
        health_score = max(0, min(100, health_score))
        
        if health_score >= 90:
            status = "🟢 Healthy"
        elif health_score >= 70:
            status = "🟡 Needs Attention"
        else:
            status = "🔴 Critical"
        
        return {
            "health_score": health_score,
            "status": status,
            "issues_count": len(self.issues),
            "issues": self.issues
        }

# ============================================================================
# DYNATRACE NEWS FETCHER
# ============================================================================

def fetch_dynatrace_updates() -> str:
    """
    Fetch latest Dynatrace product updates.
    Note: This uses web scraping as there's no official news API.
    For production, consider RSS feeds or official changelog APIs.
    """
    updates = []
    
    # Key URLs to check for updates
    sources = [
        {
            "name": "Release Notes",
            "url": "https://docs.dynatrace.com/docs/whats-new/release-notes",
            "type": "changelog"
        },
        {
            "name": "Product News",
            "url": "https://www.dynatrace.com/news/category/product-news/",
            "type": "blog"
        }
    ]
    
    # For now, return a placeholder - in production, implement actual scraping
    # or use RSS feeds
    updates.append("📰 Check docs.dynatrace.com/docs/whats-new for latest updates")
    
    return "\n".join(updates)

# ============================================================================
# MAIN REPORT GENERATOR
# ============================================================================

def generate_daily_report() -> str:
    """Generate the daily report message"""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    
    # Check if API credentials are configured
    if "YOUR_" in CONFIG["DYNATRACE_TENANT_URL"] or "YOUR_" in CONFIG["DYNATRACE_API_TOKEN"]:
        # Demo mode - generate sample report
        report = f"""
🔔 Dynatrace Daily Report
📅 {timestamp}

⚠️ SETUP REQUIRED
Configure your Dynatrace credentials in:
~/dynatrace_agent/config.env

Once configured, you'll receive:
• Problem summary
• OneAgent fleet health  
• ActiveGate status
• Architecture analysis
• Latest DT updates

📚 Setup guide in README.md
"""
    else:
        # Real mode - fetch actual data
        try:
            client = DynatraceClient(
                CONFIG["DYNATRACE_TENANT_URL"],
                CONFIG["DYNATRACE_API_TOKEN"]
            )
            
            analyzer = ArchitectureAnalyzer(client)
            results = analyzer.analyze_all()
            
            summary = results["summary"]
            problems = results["problems"]
            oneagent = results["oneagent"]
            activegate = results["activegate"]
            
            report = f"""
🔔 Dynatrace Daily Report
📅 {timestamp}

{summary['status']} | Score: {summary['health_score']}/100

📊 PROBLEMS (24h)
• Critical: {problems['critical']}
• Warnings: {problems['warnings']}
• Total: {problems['total']}

🖥️ ONEAGENT FLEET
• Total Hosts: {oneagent.get('total_hosts', 'N/A')}
• Versions in use: {oneagent.get('version_count', 'N/A')}

🌐 ACTIVEGATES
• Connected: {activegate.get('connected', 'N/A')}/{activegate.get('total', 'N/A')}

"""
            
            # Add issues if any
            if summary['issues']:
                report += "⚠️ ISSUES:\n"
                for issue in summary['issues'][:5]:
                    report += f"• {issue}\n"
            
            # Add latest updates
            report += f"\n{fetch_dynatrace_updates()}"
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            report = f"""
🔔 Dynatrace Daily Report
📅 {timestamp}

❌ Error fetching data
{str(e)[:100]}

Check logs: ~/Library/Logs/dynatrace_agent.log
"""
    
    return report.strip()

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    logger.info("=" * 50)
    logger.info("Dynatrace Daily Agent Started")
    logger.info("=" * 50)
    
    # Load config from environment file if exists
    config_file = os.path.expanduser("~/dynatrace_agent/config.env")
    if os.path.exists(config_file):
        logger.info(f"Loading config from {config_file}")
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")
        
        # Reload config values
        CONFIG["DYNATRACE_TENANT_URL"] = os.environ.get("DYNATRACE_TENANT_URL", CONFIG["DYNATRACE_TENANT_URL"])
        CONFIG["DYNATRACE_API_TOKEN"] = os.environ.get("DYNATRACE_API_TOKEN", CONFIG["DYNATRACE_API_TOKEN"])
        CONFIG["IMESSAGE_RECIPIENT"] = os.environ.get("IMESSAGE_RECIPIENT", CONFIG["IMESSAGE_RECIPIENT"])
    
    # Generate report
    report = generate_daily_report()
    logger.info(f"Report generated:\n{report}")
    
    # Send via iMessage
    recipient = CONFIG["IMESSAGE_RECIPIENT"]
    if "1234567890" in recipient:
        logger.warning("iMessage recipient not configured - printing report only")
        print("\n" + "=" * 50)
        print(report)
        print("=" * 50)
        print("\n⚠️  Configure IMESSAGE_RECIPIENT in config.env to receive iMessage notifications")
    else:
        success = send_imessage(recipient, report)
        if success:
            logger.info("Daily report sent successfully!")
        else:
            logger.error("Failed to send daily report via iMessage")
            # Save to file as backup
            backup_file = os.path.expanduser(f"~/dynatrace_agent/reports/{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            with open(backup_file, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {backup_file}")
    
    logger.info("Dynatrace Daily Agent Completed")

if __name__ == "__main__":
    main()
