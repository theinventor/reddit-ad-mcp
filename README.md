# Reddit Ads MCP Server

A Model Context Protocol (MCP) server that provides read-only access to the Reddit Ads API v3.

## Features

- List ad accounts, campaigns, ad groups, and ads
- Generate performance reports with flexible metrics and breakdowns
- Daily performance trends
- OAuth2 authentication with automatic token refresh
- Configurable defaults for account ID and metrics

## Setup

### 1. Create a Reddit Developer App

1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app..."
3. Fill in:
   - **name**: reddit-ad-mcp (or your preference)
   - **type**: Select "script"
   - **redirect uri**: http://localhost:8080 (won't be used but required)
4. Click "create app"
5. Note your **client_id** (under the app name) and **client_secret**

### 2. Get a Refresh Token

You need to do a one-time OAuth flow to get a refresh token:

```bash
# 1. Open this URL in your browser (replace CLIENT_ID):
https://www.reddit.com/api/v1/authorize?client_id=CLIENT_ID&response_type=code&state=random&redirect_uri=http://localhost:8080&duration=permanent&scope=adsread

# 2. Authorize the app - you'll be redirected to localhost with a ?code= parameter

# 3. Exchange the code for tokens (replace CLIENT_ID, CLIENT_SECRET, and CODE):
curl -X POST https://www.reddit.com/api/v1/access_token \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=authorization_code&code=CODE&redirect_uri=http://localhost:8080"

# 4. Save the refresh_token from the response
```

### 3. Configure the MCP Server

Create `config.local.json` (copy from `config.json`):

```json
{
  "reddit_api": {
    "base_url": "https://ads-api.reddit.com/api/v3",
    "auth": {
      "client_id": "YOUR_CLIENT_ID",
      "client_secret": "YOUR_CLIENT_SECRET",
      "refresh_token": "YOUR_REFRESH_TOKEN",
      "user_agent": "reddit-ad-mcp/1.0"
    }
  },
  ...
  "defaults": {
    "account_id": "YOUR_AD_ACCOUNT_ID"
  }
}
```

### 4. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Add to Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "reddit-ads": {
      "command": "/path/to/reddit-ad-mcp/.venv/bin/python",
      "args": ["/path/to/reddit-ad-mcp/server.py"]
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `get_accounts` | List all accessible ad accounts |
| `get_campaigns` | List campaigns for an account |
| `get_ad_groups` | List ad groups (optionally filtered by campaign) |
| `get_ads` | List ads (optionally filtered by ad group) |
| `get_performance_report` | Generate a performance report with custom metrics and breakdowns |
| `get_daily_performance` | Convenience tool for daily trend analysis |

## Example Queries

Once connected to Claude, you can ask things like:

- "Show me my Reddit ad accounts"
- "What campaigns do I have running?"
- "How did my ads perform last week?"
- "Show me daily spend for the last 30 days"
- "Break down campaign performance by country"

## Report Metrics

Available metrics for performance reports:

**Core:** impressions, reach, clicks, spend, ecpm, ctr, cpc

**Video:** video_viewable_impressions, video_fully_viewable_impressions, video_watched_25/50/75/100_percent

**Conversions:** conversion_purchase_clicks, conversion_purchase_views, conversion_add_to_cart_clicks, conversion_lead_clicks, conversion_sign_up_clicks, conversion_page_visit_clicks

## Report Breakdowns

Available breakdown dimensions: date, country, region, community, placement, device_os
