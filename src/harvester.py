# src/harvester.py

import logging
import requests
import feedparser
import yfinance as yf
import re
import html
from time import mktime
from datetime import datetime, timedelta, timezone
from typing import List, Dict

from src.schemas import (
    HarvestedPayload,
    RawMarketMove,
    RawMacroEvent,
    RawNewsItem
)

# Configure structured logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Constants & Configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HTTP_HEADERS = {"User-Agent": USER_AGENT}
HTTP_TIMEOUT = 10

MACRO_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TARGET_CURRENCIES = {"EUR", "USD", "IT", "DE", "FR", "GBP", "JPY"}
TARGET_IMPACTS = {"High", "Medium"}

RSS_FEEDS = {
    "MEF_Treasury": "https://www.dt.mef.gov.it/it/rss/news/dipartimento/index.jsp",
    "ECB_Press": "https://www.ecb.europa.eu/rss/press.html",
    "Fed_Monetary_Policy": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "Google_News_Macro_Bonds": "https://news.google.com/rss/search?q=macro+OR+bonds+OR+yields+when:1d&hl=en-US&gl=US&ceid=US:en"
}

MARKET_TICKERS = ["ZN=F", "ZT=F", "^TNX", "EURUSD=X", "USDJPY=X", "BZ=F", "^N225"]


def _clean_html(raw_html: str) -> str:
    """Removes HTML tags and unescapes HTML entities from a string."""
    if not raw_html:
        return ""
    clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
    clean_text = html.unescape(clean_text)
    return ' '.join(clean_text.split())


def fetch_macro_calendar() -> List[RawMacroEvent]:
    """
    Fetches the weekly macroeconomic calendar and filters for today's high/medium impact events.
    Returns an empty list in case of failure to maintain system resilience.
    """
    logger.info("Starting macro calendar harvest...")
    events: List[RawMacroEvent] = []
    
    try:
        response = requests.get(MACRO_CALENDAR_URL, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        calendar_data = response.json()
        
        now_utc = datetime.now(timezone.utc)
        today_date_str = now_utc.strftime("%Y-%m-%d")
        
        for item in calendar_data:
            # Expected date format in JSON: "2026-10-26T10:46:00-04:00"
            event_date_str = item.get("date", "")
            if not event_date_str:
                continue
                
            try:
                # Python 3.11 fromisoformat handles standard ISO 8601 with tz
                event_dt = datetime.fromisoformat(event_date_str).astimezone(timezone.utc)
            except ValueError:
                continue
                
            is_today = event_dt.strftime("%Y-%m-%d") == today_date_str
            is_target_currency = item.get("country") in TARGET_CURRENCIES
            is_target_impact = item.get("impact") in TARGET_IMPACTS
            
            if is_today and is_target_currency and is_target_impact:
                events.append(
                    RawMacroEvent(
                        timestamp=event_dt,
                        country=item.get("country", "Unknown"),
                        event_name=item.get("title", "Unknown Event"),
                        consensus=item.get("forecast", ""),
                        previous=item.get("previous", "")
                    )
                )
        logger.info(f"Successfully harvested {len(events)} macro events for today.")
        
    except requests.RequestException as e:
        logger.error(f"HTTP Error fetching macro calendar: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing macro calendar: {e}")
        
    return events


def fetch_institutional_and_market_rss() -> List[RawNewsItem]:
    """
    Fetches RSS feeds from central banks and news sources, filtering for the last 16 hours.
    Resilient to individual feed failures.
    """
    logger.info("Starting RSS feed harvest...")
    news_items: List[RawNewsItem] = []
    
    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc - timedelta(hours=16)
    
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            logger.info(f"Fetching RSS feed: {source_name}")
            feed = feedparser.parse(feed_url)
            
            if feed.bozo and hasattr(feed, 'bozo_exception'):
                logger.warning(f"Malformed feed {source_name}: {feed.bozo_exception}")
                # We still attempt to process entries if available despite bozo bit
            
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed') or entry.published_parsed is None:
                    continue
                    
                # published_parsed is a struct_time in UTC
                entry_dt = datetime.fromtimestamp(mktime(entry.published_parsed), timezone.utc)
                
                if entry_dt >= cutoff_time:
                    title = _clean_html(getattr(entry, 'title', 'No Title'))
                    summary = _clean_html(getattr(entry, 'summary', getattr(entry, 'description', '')))
                    link = getattr(entry, 'link', '')
                    
                    news_items.append(
                        RawNewsItem(
                            source=source_name,
                            published_at=entry_dt,
                            title=title,
                            summary=summary,
                            url=link
                        )
                    )
        except Exception as e:
            logger.error(f"Error processing RSS feed '{source_name}': {e}")
            continue
            
    # Sort by descending publication time
    news_items.sort(key=lambda x: x.published_at, reverse=True)
    logger.info(f"Successfully harvested {len(news_items)} recent news items.")
    return news_items


def fetch_overnight_market_snapshot() -> List[RawMarketMove]:
    """
    Fetches latest price and 1-day percentage change for defined tickers using yfinance.
    Resilient to individual ticker lookup failures.
    """
    logger.info("Starting overnight market snapshot harvest...")
    market_moves: List[RawMarketMove] = []
    
    for ticker in MARKET_TICKERS:
        try:
            yt = yf.Ticker(ticker)
            # Fetch 5 days to ensure we get at least 2 valid trading days avoiding weekends/holidays
            hist = yt.history(period="5d") 
            
            if hist.empty or len(hist) < 2:
                logger.warning(f"Insufficient historical data for {ticker}. Skipping.")
                continue
                
            prev_close = float(hist['Close'].iloc[-2])
            current_close = float(hist['Close'].iloc[-1])
            volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else None
            
            if prev_close == 0:
                pct_change = 0.0
            else:
                pct_change = ((current_close - prev_close) / prev_close) * 100.0
                
            market_moves.append(
                RawMarketMove(
                    ticker=ticker,
                    close_price=current_close,
                    percentage_change=pct_change,
                    volume=volume if volume and volume > 0 else None
                )
            )
        except Exception as e:
            logger.error(f"Error fetching market data for {ticker}: {e}")
            continue
            
    logger.info(f"Successfully harvested {len(market_moves)} market ticker movements.")
    return market_moves


def collect_all_morning_data() -> HarvestedPayload:
    """
    Orchestrator function that aggregates all data sources into the final HarvestedPayload schema.
    """
    logger.info("=== BEGIN MORNING DATA HARVEST ===")
    
    market_moves = fetch_overnight_market_snapshot()
    macro_events = fetch_macro_calendar()
    news_items = fetch_institutional_and_market_rss()
    
    payload = HarvestedPayload(
        market_moves=market_moves,
        macro_events=macro_events,
        news_items=news_items
    )
    
    logger.info("=== MORNING DATA HARVEST COMPLETE ===")
    return payload


if __name__ == "__main__":
    # Test execution
    print("Testing Harvester Module...")
    payload = collect_all_morning_data()
    
    print("\n--- MARKET MOVES ---")
    for move in payload.market_moves:
        print(f"{move.ticker}: {move.close_price:.4f} ({move.percentage_change:+.2f}%)")
        
    print("\n--- MACRO EVENTS ---")
    for event in payload.macro_events:
        print(f"[{event.timestamp.strftime('%H:%M')} UTC] {event.country} {event.event_name} (Cons: {event.consensus})")
        
    print("\n--- NEWS ITEMS (Top 5) ---")
    for news in payload.news_items[:5]:
        print(f"[{news.source}] {news.title}")
        
    print("\nTotal Market Moves:", len(payload.market_moves))
    print("Total Macro Events:", len(payload.macro_events))
    print("Total News Items:", len(payload.news_items))
