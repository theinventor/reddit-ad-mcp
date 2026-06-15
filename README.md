# Reddit Ads MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for the
**Reddit Ads API v3** — read reporting **and** create / edit / pause campaigns,
ad groups, and ads from an MCP client like Claude.

> Fork of [sbmeaper/reddit-ad-mcp](https://github.com/sbmeaper/reddit-ad-mcp),
> updated to the real v3 endpoints and extended with write support.

## Features

- **Read:** list ad accounts, campaigns, ad groups, ads; flexible performance
  reports with metrics + breakdowns; daily trends.
- **Write:** create campaigns, ad groups, and ads; update budgets, names, and
  status (pause / resume); delete entities.
- OAuth2 with automatic token refresh.
- Secrets in a gitignored `.env`; non-secret defaults in `config.json`.

> **Safety:** every create defaults to `configured_status = PAUSED`, so nothing
> spends until you explicitly activate it. Money arguments are in **dollars**
> and converted to the API's micro-currency internally.

## Setup

### 1. Create a Reddit "script" app

1. Go to <https://www.reddit.com/prefs/apps> → **create another app...**
2. Set **type** to `script` and **redirect uri** to `http://localhost:8080`
   (only used during the one-time OAuth flow below).
3. Note the **client_id** (under the app name) and **client_secret**.

### 2. Get a refresh token (one-time OAuth)

Choose your scope: `adsread` for read-only, or `adsread adsedit` to also
create / edit ads.

```bash
# 1. Open in a browser logged into your Reddit Ads account, then click Allow.
#    (URL-encode the space in the scope as %20.)
https://www.reddit.com/api/v1/authorize?client_id=CLIENT_ID&response_type=code&state=random&redirect_uri=http://localhost:8080&duration=permanent&scope=adsread%20adsedit

# 2. You'll be redirected to http://localhost:8080/?code=CODE  (the page won't
#    load — that's fine; copy CODE from the address bar).

# 3. Exchange the code for tokens:
curl -X POST https://www.reddit.com/api/v1/access_token \
  -A "reddit-ad-mcp/1.0" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=authorization_code&code=CODE&redirect_uri=http://localhost:8080"

# 4. Save the refresh_token from the JSON response.
```

### 3. Configure credentials (`.env`)

```bash
cp .env.example .env
```

Fill in `.env` (this file is gitignored — never commit it):

```ini
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_REFRESH_TOKEN=your_refresh_token
REDDIT_USER_AGENT=reddit-ad-mcp/1.0
REDDIT_AD_ACCOUNT_ID=a2_xxxxxxxx   # optional default; tools also accept account_id
```

To find your ad account id, ask the server `get_accounts` once it's running, or
it is the `a2_...` id shown in the Reddit Ads dashboard.

### 4. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Register with your MCP client

**Claude Code:**

```bash
claude mcp add reddit-ads -s user -- /abs/path/to/reddit-ad-mcp/.venv/bin/python /abs/path/to/reddit-ad-mcp/server.py
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "reddit-ads": {
      "command": "/abs/path/to/reddit-ad-mcp/.venv/bin/python",
      "args": ["/abs/path/to/reddit-ad-mcp/server.py"]
    }
  }
}
```

## Tools

### Read

| Tool | Description |
|------|-------------|
| `get_accounts` | List accessible ad accounts (via your businesses). |
| `get_campaigns` | List campaigns for an account. |
| `get_ad_groups` | List ad groups (optionally filtered by campaign). |
| `get_ads` | List ads (optionally filtered by ad group). |
| `get_performance_report` | Performance report with custom metrics + breakdowns. |
| `get_daily_performance` | Convenience daily trend report. |
| `get_funding_instruments` | List payment sources for an account. |

### Write (requires the `adsedit` scope)

| Tool | Description |
|------|-------------|
| `create_campaign` | Create a campaign (PAUSED by default). |
| `create_ad_group` | Create an ad group with targeting + daily budget. |
| `create_ad` | Promote an existing Reddit post (`post_id`) as an ad. |
| `update_campaign` | Rename, change spend cap, pause/resume. |
| `update_ad_group` | Rename, change daily budget, pause/resume. |
| `update_ad` | Rename, change click URL, pause/resume. |
| `delete_campaign` / `delete_ad_group` / `delete_ad` | Delete an entity (prefer pausing). |

Pause/resume is `update_*` with `configured_status` = `PAUSED` / `ACTIVE`.

> `create_ad` promotes a post that already exists — this server does not create
> the underlying Reddit post.

## Example prompts

- "Show me my Reddit ad accounts and which campaigns are running."
- "How did my ads perform last week? Break it down by ad."
- "Create a paused CLICKS campaign called 'Q3 Prospecting'."
- "Add an ad group targeting r/LLMDevs and r/LocalLLaMA with a $50/day budget."
- "Pause the campaign that's over budget."

## Report reference

**Levels:** `ACCOUNT`, `CAMPAIGN`, `AD_GROUP`, `AD`

**Metrics (fields):** `impressions`, `reach`, `clicks`, `spend`, `ecpm`, `ctr`,
`cpc`, video metrics (`video_watched_25/50/75/100_percent`, …), and conversion
metrics (`conversion_lead_clicks`, `conversion_sign_up_clicks`,
`conversion_page_visit_clicks`, …).

**Breakdowns:** `date`, `country`, `region`, `community`, `placement`, `device_os`.

> Money fields (`spend`, `cpc`, `ecpm`) are returned in **micro-currency** —
> divide by 1,000,000 for dollars.

## License

MIT (inherited from upstream).
