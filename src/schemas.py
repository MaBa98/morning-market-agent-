# src/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# ==========================================
# 1. INGESTION SCHEMAS (RAW DATA)
# ==========================================

class RawMarketMove(BaseModel):
    ticker: str = Field(
        ..., 
        description="The financial ticker symbol, e.g., 'GC=F' (Gold), 'EURUSD=X', 'FGBL=X' (Bund Futures)"
    )
    close_price: float = Field(
        ..., 
        description="The latest closing price or current spot price from the overnight session"
    )
    percentage_change: float = Field(
        ..., 
        description="The percentage change from the previous session's close"
    )
    volume: Optional[int] = Field(
        None, 
        description="Trading volume if available from the data source"
    )

class RawMacroEvent(BaseModel):
    timestamp: datetime = Field(
        ..., 
        description="The scheduled time for the macroeconomic data release (UTC)"
    )
    country: str = Field(
        ..., 
        description="The country or economic zone (e.g., 'US', 'EZ', 'IT', 'DE')"
    )
    event_name: str = Field(
        ..., 
        description="The name of the economic indicator (e.g., 'US CPI YoY', 'EZ Retail Sales')"
    )
    consensus: Optional[str] = Field(
        None, 
        description="Market consensus expectation prior to the release"
    )
    previous: Optional[str] = Field(
        None, 
        description="Previous period's released figure"
    )

class RawNewsItem(BaseModel):
    source: str = Field(
        ..., 
        description="The institutional source of the news (e.g., 'ECB', 'MEF', 'Fed', 'Bundesbank')"
    )
    published_at: datetime = Field(
        ..., 
        description="Publication timestamp of the press release or news item"
    )
    title: str = Field(
        ..., 
        description="Headline of the press release or news item"
    )
    summary: str = Field(
        ..., 
        description="Short excerpt, bullet points, or description of the release content"
    )
    url: str = Field(
        ..., 
        description="URL linking directly to the original institutional release"
    )

class HarvestedPayload(BaseModel):
    market_moves: List[RawMarketMove] = Field(
        ..., 
        description="List of overnight market movements harvested from market data APIs"
    )
    macro_events: List[RawMacroEvent] = Field(
        ..., 
        description="List of today's scheduled macroeconomic events harvested from the calendar API"
    )
    news_items: List[RawNewsItem] = Field(
        ..., 
        description="List of overnight institutional press releases harvested from RSS feeds"
    )

# ==========================================
# 2. TRIAGE SCHEMA (NODE 1)
# ==========================================

class TriageOutputSchema(BaseModel):
    transmission_mechanism_reasoning: str = Field(
        ..., 
        description="Rationale-First: Step-by-step reasoning evaluating the harvested data for conflicting signals, anomalies, or overnight macroeconomic shocks"
    )
    anomaly_detected: bool = Field(
        ..., 
        description="True if there is an unexplained overnight market move, unexpected institutional release, or geopolitical event requiring deeper external web research"
    )
    tavily_search_query: Optional[str] = Field(
        None, 
        description="Highly optimized search query for the Tavily API to investigate the anomaly. Must be None if anomaly_detected is False."
    )
    key_themes: List[str] = Field(
        ..., 
        description="Primary macroeconomic themes identified for today's session (e.g., 'ECB dovish pivot momentum', 'BTP supply digestion pipeline')"
    )

# ==========================================
# 3. STRATEGIST SCHEMA (NODE 3 - PLAYBOOK)
# ==========================================

class SovereignSpreadScenario(BaseModel):
    causal_reasoning: str = Field(
        ..., 
        description="Rationale-First: Explanation of the expected spread movement based on current flows, ECB signaling, or local fiscal data"
    )
    pair: str = Field(
        ..., 
        description="The sovereign spread pair, e.g., 'BTP-Bund 10Y' or 'OAT-Bund 10Y'"
    )
    expected_direction: str = Field(
        ..., 
        description="Expected trajectory: 'Widening', 'Tightening', or 'Rangebound'"
    )
    key_drivers: List[str] = Field(
        ..., 
        description="Bullet points of the main factors driving this specific spread movement today"
    )

class YieldCurveScenario(BaseModel):
    transmission_mechanism_reasoning: str = Field(
        ..., 
        description="Rationale-First: Causal reasoning for the expected yield curve dynamic based on central bank expectations and supply pressures"
    )
    curve: str = Field(
        ..., 
        description="The specific yield curve, e.g., 'Bund 2s10s', 'BTP 2s10s', 'OIS 1y1y'"
    )
    expected_shape_change: str = Field(
        ..., 
        description="Classification of the curve shift: 'Bull Flattener', 'Bear Flattener', 'Bull Steepener', 'Bear Steepener', or 'Unchanged'"
    )
    hawkish_risk_scenario: str = Field(
        ..., 
        description="How the curve is expected to react if today's incoming data is hotter/more hawkish than consensus"
    )
    dovish_risk_scenario: str = Field(
        ..., 
        description="How the curve is expected to react if today's incoming data is colder/more dovish than consensus"
    )

class AuctionImpact(BaseModel):
    transmission_mechanism_reasoning: str = Field(
        ..., 
        description="Rationale-First: Reasoning on how the market will absorb this specific debt issuance, factoring in pre-auction concessions and redemptions"
    )
    sovereign: str = Field(
        ..., 
        description="The issuing sovereign or agency entity (e.g., 'Italy MEF', 'France AFT', 'Germany Finanzagentur')"
    )
    estimated_market_impact: str = Field(
        ..., 
        description="Expected pressure on secondary market yields (e.g., 'Heavy concession building', 'Easily digested via syndication demand')"
    )

class MorningPlaybookSchema(BaseModel):
    causal_reasoning: str = Field(
        ..., 
        description="Rationale-First: High-level, overarching macroeconomic rationale dictating today's European Fixed Income market regime"
    )
    market_regime_classification: str = Field(
        ..., 
        description="Classification of the current trading regime (e.g., 'Risk-On / Disinflation', 'Stagflationary Fear', 'Flight to Quality')"
    )
    money_market_expectations: str = Field(
        ..., 
        description="Shift in ECB/Fed rate cut expectations currently priced into STIRs (ESTR/Euribor/OIS) based on overnight data"
    )
    yield_curve_scenarios: List[YieldCurveScenario] = Field(
        ..., 
        description="Detailed scenario analysis for major European sovereign yield curves"
    )
    sovereign_spread_outlook: List[SovereignSpreadScenario] = Field(
        ..., 
        description="Outlook and directional bias for intra-EMU sovereign spreads"
    )
    auction_supply_digestion: List[AuctionImpact] = Field(
        ..., 
        description="Analysis of today's government bond auctions and their anticipated secondary market impact"
    )
    actionable_trade_ideas: List[str] = Field(
        ..., 
        description="Specific, executable Fixed Income trade ideas (e.g., 'Receive 2Y EUR OIS vs Pay 10Y', 'Sell BTP 10Y on pre-auction concession')"
    )
