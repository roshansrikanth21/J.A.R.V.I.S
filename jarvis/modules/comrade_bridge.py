import requests
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ComradeBridge:
    """
    Bridge module for interacting with the COMRADE Terminal.
    Assumes COMRADE exposes an API or shared interface.
    """
    def __init__(self, config=None):
        self.config = config.get("comrade", {}) if config else {}
        # Default to localhost if not specified
        self.api_url = self.config.get("api_url", "http://localhost:5050")
        self.api_key = self.config.get("api_key", "")

    def send_command(self, command: str, args: Dict[str, Any] = None) -> str:
        """Sends a command to the COMRADE trading terminal."""
        logger.info(f"Connecting to COMRADE with command: {command}")
        
        # Check if it's a specific action we can map to an endpoint
        lower_cmd = command.lower()
        if "status" in lower_cmd:
            return str(self.get_status())
        if "analysis" in lower_cmd or "setup" in lower_cmd:
            ticker = args.get("ticker", "^NSEI") if args else "^NSEI"
            return str(self.get_analysis(ticker))
        
        try:
            response = requests.post(
                f"{self.api_url}/api/execute", # Assuming this endpoint exists or we use a general one
                json={"command": command, "args": args or {}},
                timeout=5
            )
            return f"COMRADE Response: {response.json().get('message', 'Success')}"
        except Exception:
            return f"Could not send command to COMRADE. Terminal at {self.api_url} is likely offline."

    def get_status(self) -> Dict[str, Any]:
        """Polls COMRADE for current trading status/positions."""
        try:
            res = requests.get(f"{self.api_url}/api/system/status", timeout=2)
            return res.json().get("data", {"status": "connected"})
        except:
            return {"status": "disconnected", "reason": "COMRADE API unreachable"}

    def get_analysis(self, ticker: str = "^NSEI") -> Dict[str, Any]:
        """Gets the latest trading analysis from COMRADE for a ticker."""
        try:
            res = requests.get(f"{self.api_url}/api/regime?ticker={ticker}", timeout=3)
            return res.json()
        except:
            return {"status": "error", "message": "Failed to fetch regime analysis"}

    def get_market_data(self, ticker: str, interval: str = "5m") -> Optional[Dict[str, Any]]:
        """Fetches real-time market data from COMRADE's providers."""
        try:
            res = requests.get(f"{self.api_url}/api/intraday?ticker={ticker}&interval={interval}", timeout=4)
            data = res.json()
            if "error" in data:
                return None
            return data
        except:
            return None
