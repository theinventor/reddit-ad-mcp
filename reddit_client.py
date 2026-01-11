"""
Reddit Ads API client with OAuth2 authentication.
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


class RedditAdsClient:
    """Client for Reddit Ads API v3."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.base_url = self.config["reddit_api"]["base_url"]
        self.auth_config = self.config["reddit_api"]["auth"]
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        # Check for local override first
        local_path = Path(config_path).stem + ".local.json"
        if Path(local_path).exists():
            config_path = local_path
        
        with open(config_path) as f:
            return json.load(f)
    
    def _get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary."""
        # Return cached token if still valid (with 60s buffer)
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token
        
        # Refresh the token
        auth = (self.auth_config["client_id"], self.auth_config["client_secret"])
        headers = {"User-Agent": self.auth_config["user_agent"]}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.auth_config["refresh_token"]
        }
        
        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            headers=headers,
            data=data
        )
        response.raise_for_status()
        
        token_data = response.json()
        self._access_token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 3600)
        
        return self._access_token
    
    def _request(self, method: str, path: str, params: dict = None, json_body: dict = None) -> dict:
        """Make authenticated request to Reddit Ads API."""
        token = self._get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.auth_config["user_agent"],
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{path}"
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body
        )
        response.raise_for_status()
        
        return response.json()
    
    def get_me(self) -> dict:
        """Get authenticated user info."""
        return self._request("GET", "/me")
    
    def get_accounts(self) -> dict:
        """List all ad accounts."""
        return self._request("GET", "/accounts")
    
    def get_campaigns(self, account_id: str) -> dict:
        """List campaigns for an account."""
        return self._request("GET", f"/accounts/{account_id}/campaigns")
    
    def get_campaign(self, account_id: str, campaign_id: str) -> dict:
        """Get a specific campaign."""
        return self._request("GET", f"/accounts/{account_id}/campaigns/{campaign_id}")
    
    def get_ad_groups(self, account_id: str, campaign_id: str = None) -> dict:
        """List ad groups for an account, optionally filtered by campaign."""
        params = {}
        if campaign_id:
            params["campaign_id"] = campaign_id
        return self._request("GET", f"/accounts/{account_id}/ad_groups", params=params)
    
    def get_ads(self, account_id: str, ad_group_id: str = None) -> dict:
        """List ads for an account, optionally filtered by ad group."""
        params = {}
        if ad_group_id:
            params["ad_group_id"] = ad_group_id
        return self._request("GET", f"/accounts/{account_id}/ads", params=params)
    
    def get_report(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        level: str = "CAMPAIGN",
        metrics: list = None,
        breakdowns: list = None
    ) -> dict:
        """
        Generate a performance report.
        
        Args:
            account_id: The ad account ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            level: Aggregation level (ACCOUNT, CAMPAIGN, AD_GROUP, AD)
            metrics: List of metrics to include
            breakdowns: Optional list of breakdown dimensions
        """
        if metrics is None:
            metrics = self.config["defaults"]["report_metrics"]
        
        body = {
            "start_date": start_date,
            "end_date": end_date,
            "level": level,
            "metrics": metrics
        }
        
        if breakdowns:
            body["breakdowns"] = breakdowns
        
        return self._request("POST", f"/accounts/{account_id}/reports", json_body=body)
    
    def get_default_account_id(self) -> Optional[str]:
        """Get the default account ID from config."""
        return self.config["defaults"].get("account_id") or None
