"""
Reddit Ads MCP Server - Read-only access to Reddit Ads API v3.
"""

from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from reddit_client import RedditAdsClient

# Initialize MCP server
mcp = FastMCP("reddit-ads")

# Initialize Reddit client
client = RedditAdsClient()


def _get_date_range(days: int = 7) -> tuple[str, str]:
    """Get date range for the last N days."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def _resolve_account_id(account_id: str | None) -> str:
    """Resolve account ID, using default if not provided."""
    if account_id:
        return account_id
    default_id = client.get_default_account_id()
    if default_id:
        return default_id
    raise ValueError("No account_id provided and no default configured")


@mcp.tool()
def get_accounts() -> dict:
    """
    List all Reddit ad accounts accessible to this user.
    
    Returns:
        List of ad accounts with their IDs, names, and status.
    """
    return client.get_accounts()


@mcp.tool()
def get_campaigns(account_id: str = None) -> dict:
    """
    List all campaigns for a Reddit ad account.
    
    Args:
        account_id: The ad account ID. Uses default if not provided.
    
    Returns:
        List of campaigns with IDs, names, status, and objectives.
    """
    account_id = _resolve_account_id(account_id)
    return client.get_campaigns(account_id)


@mcp.tool()
def get_ad_groups(account_id: str = None, campaign_id: str = None) -> dict:
    """
    List ad groups for a Reddit ad account.
    
    Args:
        account_id: The ad account ID. Uses default if not provided.
        campaign_id: Optional - filter to a specific campaign.
    
    Returns:
        List of ad groups with IDs, names, status, bid info, and budgets.
    """
    account_id = _resolve_account_id(account_id)
    return client.get_ad_groups(account_id, campaign_id)


@mcp.tool()
def get_ads(account_id: str = None, ad_group_id: str = None) -> dict:
    """
    List ads for a Reddit ad account.
    
    Args:
        account_id: The ad account ID. Uses default if not provided.
        ad_group_id: Optional - filter to a specific ad group.
    
    Returns:
        List of ads with IDs, names, status, and creative details.
    """
    account_id = _resolve_account_id(account_id)
    return client.get_ads(account_id, ad_group_id)


@mcp.tool()
def get_performance_report(
    account_id: str = None,
    start_date: str = None,
    end_date: str = None,
    level: str = "CAMPAIGN",
    metrics: list[str] = None,
    breakdowns: list[str] = None
) -> dict:
    """
    Get a performance report for Reddit ads.
    
    Args:
        account_id: The ad account ID. Uses default if not provided.
        start_date: Start date (YYYY-MM-DD). Defaults to 7 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.
        level: Aggregation level - ACCOUNT, CAMPAIGN, AD_GROUP, or AD. Defaults to CAMPAIGN.
        metrics: List of metrics to include. Defaults to impressions, clicks, spend, ctr, cpc.
                 Available: impressions, reach, clicks, spend, ecpm, ctr, cpc,
                 video_viewable_impressions, video_watched_25/50/75/100_percent,
                 conversion_purchase_clicks, conversion_add_to_cart_clicks, etc.
        breakdowns: Optional breakdown dimensions: date, country, region, community, placement, device_os.
    
    Returns:
        Performance data with requested metrics broken down by the specified level.
    """
    account_id = _resolve_account_id(account_id)
    
    if not start_date or not end_date:
        start_date, end_date = _get_date_range(7)
    
    return client.get_report(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        level=level,
        metrics=metrics,
        breakdowns=breakdowns
    )


@mcp.tool()
def get_daily_performance(
    account_id: str = None,
    days: int = 7,
    level: str = "ACCOUNT"
) -> dict:
    """
    Get daily performance breakdown for the last N days.
    
    This is a convenience tool that returns spend, impressions, clicks, 
    CTR, and CPC broken down by day.
    
    Args:
        account_id: The ad account ID. Uses default if not provided.
        days: Number of days to look back. Defaults to 7.
        level: Aggregation level - ACCOUNT, CAMPAIGN, AD_GROUP, or AD. Defaults to ACCOUNT.
    
    Returns:
        Daily performance data for easy trend analysis.
    """
    account_id = _resolve_account_id(account_id)
    start_date, end_date = _get_date_range(days)
    
    return client.get_report(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        level=level,
        metrics=["impressions", "clicks", "spend", "ctr", "cpc"],
        breakdowns=["date"]
    )


# ---------------------------------------------------------------------------
# Write tools (require the adsedit scope). Creates default to PAUSED so nothing
# spends until explicitly activated. Money args are in DOLLARS (converted to the
# API's micro-currency internally).
# ---------------------------------------------------------------------------


@mcp.tool()
def get_funding_instruments(account_id: str = None) -> dict:
    """List funding instruments (payment sources) for an ad account."""
    account_id = _resolve_account_id(account_id)
    return client.get_funding_instruments(account_id)


@mcp.tool()
def create_campaign(
    name: str,
    objective: str = "CLICKS",
    status: str = "PAUSED",
    spend_cap_dollars: float = None,
    funding_instrument_id: str = None,
    account_id: str = None,
) -> dict:
    """
    Create a campaign. Defaults to PAUSED (no spend until activated).

    Args:
        name: Campaign name.
        objective: CLICKS (traffic), IMPRESSIONS, CONVERSIONS, VIDEO_VIEWS, LEAD_GENERATION, etc.
        status: PAUSED (default) or ACTIVE.
        spend_cap_dollars: Optional lifetime spend cap in dollars.
        funding_instrument_id: Payment source; auto-resolved from the account if omitted.
        account_id: Ad account ID. Uses default if not provided.
    """
    account_id = _resolve_account_id(account_id)
    return client.create_campaign(
        account_id, name, objective=objective, status=status,
        spend_cap_dollars=spend_cap_dollars, funding_instrument_id=funding_instrument_id,
    )


@mcp.tool()
def create_ad_group(
    campaign_id: str,
    name: str,
    daily_budget_dollars: float,
    communities: list[str] = None,
    keywords: list[str] = None,
    geolocations: list[str] = None,
    start_time: str = None,
    end_time: str = None,
    status: str = "PAUSED",
    account_id: str = None,
) -> dict:
    """
    Create an ad group under a campaign. Defaults to PAUSED.

    Args:
        campaign_id: Parent campaign ID.
        name: Ad group name.
        daily_budget_dollars: Daily spend cap in dollars (e.g. 50).
        communities: Subreddit names to target WITHOUT the r/ prefix (e.g. ["LLMDevs","LocalLLaMA"]).
        keywords: Keyword targets.
        geolocations: Geo codes (default ["US"]).
        start_time / end_time: ISO-8601 timestamps (e.g. 2026-06-20T00:00:00Z). Optional.
        status: PAUSED (default) or ACTIVE.
        account_id: Ad account ID. Uses default if not provided.
    """
    account_id = _resolve_account_id(account_id)
    return client.create_ad_group(
        account_id, campaign_id, name, daily_budget_dollars,
        communities=communities, keywords=keywords, geolocations=geolocations,
        start_time=start_time, end_time=end_time, status=status,
    )


@mcp.tool()
def create_ad(
    ad_group_id: str,
    campaign_id: str,
    name: str,
    post_id: str,
    click_url: str = None,
    profile_id: str = None,
    status: str = "PAUSED",
    account_id: str = None,
) -> dict:
    """
    Create an ad from an existing promoted Reddit post. Defaults to PAUSED.

    Note: the post must already exist (post_id like t3_xxxxx). This tool does not
    create the underlying Reddit post.

    Args:
        ad_group_id: Parent ad group ID.
        campaign_id: Parent campaign ID.
        name: Ad name.
        post_id: Reddit post fullname (t3_xxxxx) to promote.
        click_url: Destination URL (UTM-tagged) for link/image posts.
        profile_id: Posting profile (t2_xxxxx). Uses the post's profile if omitted.
        status: PAUSED (default) or ACTIVE.
        account_id: Ad account ID. Uses default if not provided.
    """
    account_id = _resolve_account_id(account_id)
    return client.create_ad(
        account_id, ad_group_id, campaign_id, name, post_id,
        click_url=click_url, profile_id=profile_id, status=status,
    )


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


@mcp.tool()
def update_campaign(
    campaign_id: str,
    name: str = None,
    configured_status: str = None,
    spend_cap_dollars: float = None,
    account_id: str = None,
) -> dict:
    """
    Update a campaign. Set configured_status to PAUSED or ACTIVE to pause/resume.
    Only provided fields are changed.
    """
    account_id = _resolve_account_id(account_id)
    fields = _clean({"name": name, "configured_status": configured_status})
    if spend_cap_dollars is not None:
        fields["spend_cap"] = int(round(spend_cap_dollars * 1_000_000))
    return client.update_campaign(account_id, campaign_id, **fields)


@mcp.tool()
def update_ad_group(
    ad_group_id: str,
    name: str = None,
    configured_status: str = None,
    daily_budget_dollars: float = None,
    account_id: str = None,
) -> dict:
    """
    Update an ad group (pause/resume via configured_status=PAUSED/ACTIVE, or change daily budget).
    Only provided fields are changed.
    """
    account_id = _resolve_account_id(account_id)
    fields = _clean({"name": name, "configured_status": configured_status})
    if daily_budget_dollars is not None:
        fields["goal_value"] = int(round(daily_budget_dollars * 1_000_000))
    return client.update_ad_group(account_id, ad_group_id, **fields)


@mcp.tool()
def update_ad(
    ad_id: str,
    name: str = None,
    configured_status: str = None,
    click_url: str = None,
    account_id: str = None,
) -> dict:
    """Update an ad (pause/resume via configured_status=PAUSED/ACTIVE). Only provided fields change."""
    account_id = _resolve_account_id(account_id)
    fields = _clean({"name": name, "configured_status": configured_status, "click_url": click_url})
    return client.update_ad(account_id, ad_id, **fields)


@mcp.tool()
def delete_campaign(campaign_id: str, account_id: str = None) -> dict:
    """Delete a campaign. Irreversible — prefer pausing (update_campaign configured_status=PAUSED)."""
    account_id = _resolve_account_id(account_id)
    return client.delete_entity(account_id, "campaigns", campaign_id)


@mcp.tool()
def delete_ad_group(ad_group_id: str, account_id: str = None) -> dict:
    """Delete an ad group. Irreversible — prefer pausing."""
    account_id = _resolve_account_id(account_id)
    return client.delete_entity(account_id, "ad_groups", ad_group_id)


@mcp.tool()
def delete_ad(ad_id: str, account_id: str = None) -> dict:
    """Delete an ad. Irreversible — prefer pausing."""
    account_id = _resolve_account_id(account_id)
    return client.delete_entity(account_id, "ads", ad_id)


if __name__ == "__main__":
    mcp.run()
