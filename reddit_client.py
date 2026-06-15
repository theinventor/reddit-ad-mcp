"""
Reddit Ads API client with OAuth2 authentication.

Targets the real Reddit Ads API v3 surface:
  - ad accounts are discovered via /me/businesses -> /businesses/{id}/ad_accounts
  - resources live under /ad_accounts/{id}/...
  - reports POST to /ad_accounts/{id}/reports with a {"data": {...}} body using
    ISO-8601 starts_at/ends_at, uppercase `breakdowns`, and lowercase `fields`.

Note: money fields (spend, cpc, ecpm) are returned in micro-currency (value / 1e6 = dollars).
"""

import json
import os
import time
import requests
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timedelta
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional; env vars still work without it.
    load_dotenv = None


# Map the friendly aggregation level to the v3 breakdown dimension.
_LEVEL_BREAKDOWN = {
    "ACCOUNT": None,
    "CAMPAIGN": "CAMPAIGN_ID",
    "AD_GROUP": "AD_GROUP_ID",
    "AD": "AD_ID",
}

# Map friendly breakdown names to v3 enums (also accepts already-uppercase enums).
_BREAKDOWN_ALIASES = {
    "date": "DATE",
    "country": "COUNTRY",
    "region": "REGION",
    "community": "COMMUNITY",
    "placement": "PLACEMENT",
    "device_os": "DEVICE_OS",
    "campaign_id": "CAMPAIGN_ID",
    "ad_group_id": "AD_GROUP_ID",
    "ad_id": "AD_ID",
}


class RedditAdsClient:
    """Client for Reddit Ads API v3."""

    def __init__(self, config_path: str = "config.json"):
        if load_dotenv is not None:
            load_dotenv(Path(__file__).resolve().parent / ".env")
        self.config = self._load_config(config_path)
        self.base_url = self.config["reddit_api"]["base_url"]
        self.auth_config = self._resolve_auth()
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _resolve_auth(self) -> dict:
        """Resolve OAuth credentials, preferring environment variables (.env).

        Secrets belong in a gitignored .env file, never in committed config.
        Falls back to a config file's reddit_api.auth block for convenience.
        """
        cfg_auth = self.config.get("reddit_api", {}).get("auth", {})
        return {
            "client_id": os.getenv("REDDIT_CLIENT_ID") or cfg_auth.get("client_id", ""),
            "client_secret": os.getenv("REDDIT_CLIENT_SECRET") or cfg_auth.get("client_secret", ""),
            "refresh_token": os.getenv("REDDIT_REFRESH_TOKEN") or cfg_auth.get("refresh_token", ""),
            "user_agent": os.getenv("REDDIT_USER_AGENT") or cfg_auth.get("user_agent", "reddit-ad-mcp/1.0"),
        }

    def _load_config(self, config_path: str) -> dict:
        """Load configuration, preferring a local override (config.local.json).

        Paths are anchored to this module's directory so the server works no
        matter what working directory it is launched from (e.g. by an MCP host).
        """
        base = Path(__file__).resolve().parent
        candidate = Path(config_path)
        if not candidate.is_absolute():
            candidate = base / candidate
        local_path = candidate.with_name(Path(config_path).stem + ".local.json")
        chosen = local_path if local_path.exists() else candidate
        with open(chosen) as f:
            return json.load(f)

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        auth = (self.auth_config["client_id"], self.auth_config["client_secret"])
        headers = {"User-Agent": self.auth_config["user_agent"]}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.auth_config["refresh_token"],
        }

        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            headers=headers,
            data=data,
        )
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 3600)
        return self._access_token

    def _raw(self, method: str, path: str, params: dict = None, json_body: dict = None):
        """Make an authenticated request and return the raw requests.Response.

        `path` may be a relative API path or an absolute URL (the latter is used
        when following pagination cursors).
        """
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.auth_config["user_agent"],
            "Content-Type": "application/json",
        }
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        return requests.request(
            method=method, url=url, headers=headers, params=params, json=json_body
        )

    @staticmethod
    def _check(response):
        """Raise a descriptive error (status + body) on HTTP failure.

        Reddit's API returns a JSON error body explaining the failure (bad field,
        missing funding instrument, wrong enum). Surface it instead of a bare
        status line so callers — and the LLM driving the MCP — get something
        actionable.
        """
        if response.status_code >= 400:
            raise RuntimeError(
                f"Reddit Ads API {response.status_code} {response.request.method} "
                f"{response.url}: {response.text.strip()}"
            )
        return response

    def _request(self, method: str, path: str, params: dict = None, json_body: dict = None) -> dict:
        """Make an authenticated request to the Reddit Ads API (raises on error)."""
        return self._check(self._raw(method, path, params=params, json_body=json_body)).json()

    def _get_paged(self, path: str) -> dict:
        """GET a list endpoint, following pagination cursors and aggregating `data`.

        Without this, callers would silently see only the first page of results.
        """
        items = []
        url = path
        while url:
            page = self._request("GET", url)
            items.extend(page.get("data", []) or [])
            next_url = (page.get("pagination") or {}).get("next_url")
            url = urljoin(self.base_url + "/", next_url) if next_url else None
        return {"data": items}

    # --- identity / discovery -------------------------------------------------

    def get_me(self) -> dict:
        """Get authenticated user info."""
        return self._request("GET", "/me")

    def get_businesses(self) -> dict:
        """List businesses the authenticated user belongs to."""
        return self._request("GET", "/me/businesses")

    def get_accounts(self) -> dict:
        """
        List all ad accounts accessible to this user.

        There is no flat /accounts endpoint in v3 — ad accounts hang off
        businesses, so we walk /me/businesses then each business's ad_accounts.
        """
        businesses = self.get_businesses().get("data", []) or []
        accounts = []
        for biz in businesses:
            biz_id = biz.get("id")
            if not biz_id:
                continue
            resp = self._request("GET", f"/businesses/{biz_id}/ad_accounts")
            for acct in resp.get("data", []) or []:
                acct = dict(acct)
                acct["business_name"] = biz.get("name")
                accounts.append(acct)
        return {"data": accounts}

    def get_profiles(self, account_id: str) -> dict:
        """List posting profiles (Reddit users) available to an ad account (all pages)."""
        return self._get_paged(f"/ad_accounts/{account_id}/profiles")

    def _default_profile(self, account_id: str) -> str:
        """Return the account's posting profile when it is unambiguous.

        Raises if there are zero or multiple profiles. The id goes into a URL
        path, so returning None would post to a literal `/profiles/None/...`;
        the caller must pass profile_id explicitly in those cases.
        """
        data = self.get_profiles(account_id).get("data", []) or []
        if not data:
            raise ValueError(
                "No posting profile found for this account; pass profile_id explicitly."
            )
        if len(data) > 1:
            ids = ", ".join(f"{p.get('id')} ({p.get('name')})" for p in data)
            raise ValueError(
                f"Multiple profiles found ({ids}); pass profile_id explicitly."
            )
        return data[0].get("id")

    def get_posts(self, profile_id: str) -> dict:
        """List posts under a profile (all pages)."""
        return self._get_paged(f"/profiles/{profile_id}/posts")

    # --- entities -------------------------------------------------------------

    def get_campaigns(self, account_id: str) -> dict:
        """List campaigns for an ad account (all pages)."""
        return self._get_paged(f"/ad_accounts/{account_id}/campaigns")

    def get_campaign(self, account_id: str, campaign_id: str) -> dict:
        """Get a specific campaign. (Items are top-level in v3, not nested under the account.)"""
        return self._request("GET", f"/campaigns/{campaign_id}")

    def get_ad_groups(self, account_id: str, campaign_id: str = None) -> dict:
        """List ad groups for an ad account (all pages), optionally filtered by campaign."""
        resp = self._get_paged(f"/ad_accounts/{account_id}/ad_groups")
        if campaign_id:
            resp["data"] = [g for g in resp["data"] if g.get("campaign_id") == campaign_id]
        return resp

    def get_ads(self, account_id: str, ad_group_id: str = None) -> dict:
        """List ads for an ad account (all pages), optionally filtered by ad group."""
        resp = self._get_paged(f"/ad_accounts/{account_id}/ads")
        if ad_group_id:
            resp["data"] = [a for a in resp["data"] if a.get("ad_group_id") == ad_group_id]
        return resp

    # --- reporting ------------------------------------------------------------

    @staticmethod
    def _to_iso(date_str: str, end_of_day: bool = False) -> str:
        """Convert a YYYY-MM-DD string to an ISO-8601 instant (UTC).

        ends_at is exclusive in the v3 API, so for an inclusive end date we
        advance to the start of the following day.
        """
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        if end_of_day:
            d = d + timedelta(days=1)
        return d.strftime("%Y-%m-%dT00:00:00Z")

    def get_report(
        self,
        account_id: str,
        start_date: str,
        end_date: str,
        level: str = "CAMPAIGN",
        metrics: list = None,
        breakdowns: list = None,
    ) -> dict:
        """
        Generate a performance report.

        level   -> mapped to a v3 breakdown dimension (CAMPAIGN -> CAMPAIGN_ID, etc.)
        metrics -> v3 `fields` (lowercase, e.g. impressions, clicks, spend, ctr, cpc, ecpm)
        breakdowns -> extra v3 dimensions (date, country, community, placement, device_os, ...)

        Money fields come back in micro-currency (value / 1e6 = dollars).

        Note: dates are interpreted as UTC day boundaries. The Reddit dashboard
        reports in the ad account's own timezone, so daily figures can differ by
        a few hours' worth of activity near midnight.
        """
        if metrics is None:
            metrics = self.config["defaults"]["report_metrics"]

        dims = []
        level_dim = _LEVEL_BREAKDOWN.get((level or "").upper(), None)
        if level_dim:
            dims.append(level_dim)
        for b in breakdowns or []:
            enum = _BREAKDOWN_ALIASES.get(b.lower(), b.upper())
            if enum not in dims:
                dims.append(enum)
        # The API requires at least one breakdown; default to DATE for account-level.
        if not dims:
            dims.append("DATE")

        body = {
            "data": {
                "starts_at": self._to_iso(start_date),
                "ends_at": self._to_iso(end_date, end_of_day=True),
                "breakdowns": dims,
                "fields": list(metrics),
            }
        }
        return self._request("POST", f"/ad_accounts/{account_id}/reports", json_body=body)

    # --- funding --------------------------------------------------------------

    def get_funding_instruments(self, account_id: str) -> dict:
        """List funding instruments (payment sources) for an ad account."""
        return self._request("GET", f"/ad_accounts/{account_id}/funding_instruments")

    def _default_funding_instrument(self, account_id: str) -> Optional[str]:
        """Return the account's funding instrument when it is unambiguous.

        Raises if there is more than one candidate so a campaign is never silently
        charged to the wrong payment source — the caller must then pass an explicit
        funding_instrument_id.
        """
        data = self.get_funding_instruments(account_id).get("data", []) or []
        candidates = [f for f in data if f.get("is_active", True)] or data
        if not candidates:
            return None
        if len(candidates) > 1:
            ids = ", ".join(str(f.get("id")) for f in candidates)
            raise ValueError(
                f"Multiple funding instruments found ({ids}); "
                "pass funding_instrument_id explicitly."
            )
        return candidates[0].get("id")

    # --- writes (require the adsedit scope) -----------------------------------
    # Creates default to configured_status=PAUSED so nothing spends until a
    # human explicitly activates it.

    @staticmethod
    def _dollars_to_micro(amount) -> Optional[int]:
        return None if amount is None else int(round(float(amount) * 1_000_000))

    def create_campaign(
        self,
        account_id: str,
        name: str,
        objective: str = "CLICKS",
        funding_instrument_id: str = None,
        status: str = "PAUSED",
        special_ad_categories: list = None,
        spend_cap_dollars: float = None,
    ) -> dict:
        """Create a campaign (PAUSED by default). Auto-resolves a funding instrument if omitted."""
        if not funding_instrument_id:
            funding_instrument_id = self._default_funding_instrument(account_id)
        data = {
            "name": name,
            "objective": objective,
            "funding_instrument_id": funding_instrument_id,
            "configured_status": status,
            "special_ad_categories": special_ad_categories or [],
        }
        cap = self._dollars_to_micro(spend_cap_dollars)
        if cap is not None:
            data["spend_cap"] = cap
        return self._request("POST", f"/ad_accounts/{account_id}/campaigns", json_body={"data": data})

    def create_ad_group(
        self,
        account_id: str,
        campaign_id: str,
        name: str,
        daily_budget_dollars: float,
        communities: list = None,
        keywords: list = None,
        geolocations: list = None,
        start_time: str = None,
        end_time: str = None,
        status: str = "PAUSED",
        bid_strategy: str = "BIDLESS",
        bid_type: str = "CPC",
        locations: list = None,
        platforms: list = None,
        expand_targeting: bool = True,
    ) -> dict:
        """Create an ad group (PAUSED by default) with targeting + a daily budget (in dollars)."""
        targeting = {
            "communities": communities or [],
            "keywords": keywords or [],
            "geolocations": geolocations or ["US"],
            "locations": locations or ["FEED", "COMMENTS_PAGE"],
            "platforms": platforms or ["ALL"],
            "expand_targeting": expand_targeting,
        }
        data = {
            "campaign_id": campaign_id,
            "name": name,
            "configured_status": status,
            "bid_strategy": bid_strategy,
            "bid_type": bid_type,
            "goal_type": "DAILY_SPEND",
            "goal_value": self._dollars_to_micro(daily_budget_dollars),
            "targeting": targeting,
        }
        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time
        return self._request("POST", f"/ad_accounts/{account_id}/ad_groups", json_body={"data": data})

    def create_ad(
        self,
        account_id: str,
        ad_group_id: str,
        campaign_id: str,
        name: str,
        post_id: str,
        click_url: str = None,
        profile_id: str = None,
        status: str = "PAUSED",
    ) -> dict:
        """Create an ad (PAUSED by default) from an existing promoted post (post_id, e.g. t3_xxx)."""
        data = {
            "ad_group_id": ad_group_id,
            "campaign_id": campaign_id,
            "name": name,
            "post_id": post_id,
            "configured_status": status,
        }
        if click_url:
            data["click_url"] = click_url
        if profile_id:
            data["profile_id"] = profile_id
        return self._request("POST", f"/ad_accounts/{account_id}/ads", json_body={"data": data})

    def create_post(
        self,
        profile_id: str,
        headline: str,
        body: str = None,
        post_type: str = "TEXT",
        allow_comments: bool = False,
    ) -> dict:
        """Create a promoted post under a profile.

        Returns the created post (including its id, e.g. t3_xxxxx), which can then
        be promoted with create_ad. TEXT posts use `headline` + a markdown `body`.
        Reddit's standard submit API does not cover ad posts, so this is the path
        for building an ad's creative end-to-end.
        """
        if not headline or not headline.strip():
            raise ValueError("headline is required and cannot be empty.")
        data = {"type": post_type, "headline": headline, "allow_comments": allow_comments}
        if body is not None:
            data["body"] = body
        return self._request("POST", f"/profiles/{profile_id}/posts", json_body={"data": data})

    def _update(self, account_id: str, kind: str, entity_id: str, fields: dict) -> dict:
        """Partial-update an entity via PATCH.

        Falls back to PUT only if the server explicitly reports PATCH is not
        allowed (405). POST is never used — it is the create verb and could be
        misinterpreted as an upsert/replace. A 404 surfaces immediately as a real
        "not found" instead of being masked by trying other verbs.
        """
        if not fields:
            raise ValueError("No fields to update.")
        # Individual entities are top-level in v3 (/campaigns/{id}, /ad_groups/{id},
        # /ads/{id}) — NOT nested under /ad_accounts. account_id is unused here.
        path = f"/{kind}/{entity_id}"
        resp = self._raw("PATCH", path, json_body={"data": fields})
        if resp.status_code == 405:
            resp = self._raw("PUT", path, json_body={"data": fields})
        self._check(resp)
        body = resp.text.strip()
        return resp.json() if body else {"updated": True, "id": entity_id}

    def update_campaign(self, account_id: str, campaign_id: str, **fields) -> dict:
        return self._update(account_id, "campaigns", campaign_id, fields)

    def update_ad_group(self, account_id: str, ad_group_id: str, **fields) -> dict:
        return self._update(account_id, "ad_groups", ad_group_id, fields)

    def update_ad(self, account_id: str, ad_id: str, **fields) -> dict:
        return self._update(account_id, "ads", ad_id, fields)

    def delete_entity(self, account_id: str, kind: str, entity_id: str) -> dict:
        """Delete a campaign/ad_group/ad. `kind` is one of campaigns, ad_groups, ads.

        Entities are top-level in v3 (/{kind}/{id}); account_id is unused here.
        """
        resp = self._check(self._raw("DELETE", f"/{kind}/{entity_id}"))
        body = resp.text.strip()
        return resp.json() if body else {"deleted": True, "id": entity_id}

    def get_default_account_id(self) -> Optional[str]:
        """Get the default account ID (env REDDIT_AD_ACCOUNT_ID overrides config)."""
        return os.getenv("REDDIT_AD_ACCOUNT_ID") or self.config["defaults"].get("account_id") or None
