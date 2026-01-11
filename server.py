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


if __name__ == "__main__":
    mcp.run()
