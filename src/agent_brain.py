# src/agent_brain.py

import os
import logging
from typing import Optional

from google import genai
from google.genai import types
from tavily import TavilyClient

from src.schemas import (
    HarvestedPayload,
    TriageOutputSchema,
    MorningPlaybookSchema
)

# Configure structured logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ==========================================
# SYSTEM PROMPTS (XML FORMATTED)
# ==========================================

TRIAGE_SYSTEM_PROMPT = """\
<role>
You are an elite Financial News Triage Analyst on a European Fixed Income trading desk.
Your mandate is to process raw overnight data feeds, filter out market noise, and extract high-conviction macroeconomic signals.
</role>

<instructions>
1. Evaluate the provided `HarvestedPayload` (which includes overnight market moves, today's macro events, and recent institutional news).
2. Filter out irrelevant noise (e.g., single-stock equity news, crypto movements, or unrelated corporate announcements).
3. Isolate the top macroeconomic drivers and key institutional announcements (especially from the ECB, Fed, MEF, Bundesbank, or debt management agencies).
4. Perform Anomaly Detection: Compare the `market_moves` against the `news_items`. If there is a significant overnight market move (e.g., sudden yield spike, major FX swing) that is NOT explained by the provided news calendar, flag it as an anomaly.
5. If an anomaly is detected, formulate a highly targeted web search query (to be sent to Tavily) to uncover the hidden catalyst (e.g., overnight geopolitical event, unexpected Asian market intervention, unmapped central bank leak).
6. Detail your rationale thoroughly using the Rationale-First principle before stating your conclusion.
</instructions>

<constraints>
- Strict adherence to the provided JSON schema is mandatory.
- If no anomaly is detected, set `anomaly_detected` to false and `tavily_search_query` to null.
</constraints>
"""

STRATEGIST_SYSTEM_PROMPT = """\
<role>
You are the Lead Fixed Income & Macro Strategist for a top-tier European Government Bond (EGB) proprietary trading desk. 
Your expertise spans the BTP, Bund, and OAT yield curves, short-term interest rate (ESTR/Euribor) derivatives, and sovereign spread matrices.
</role>

<grounding_rules>
- ZERO HALLUCINATION: Never invent bond yields, consensus estimates, or economic figures. If a data point is missing from the input, state that it is unknown.
- FINANCIAL PHYSICS: Maintain absolute consistency. If yields are expected to rise, futures prices (e.g., FGBL, FBTP) must be projected down.
- AUCTION MECHANICS: When analyzing supply, explicitly account for pre-auction concessions, estimated bid-to-cover ratios, and potential syndication tail risks.
- SENSITIVITY MATRIX: Always evaluate incoming macro data symmetrically. Define the Hawkish risk scenario (hotter/higher than consensus) and Dovish risk scenario (colder/lower than consensus).
</grounding_rules>

<instructions>
Synthesize the provided triaged market intelligence, overnight data, and any deep-dive research into a cohesive, highly actionable Morning Playbook. 
Your playbook dictates the trading posture for the morning session.

1. Begin with an overarching macroeconomic rationale that defines today's market regime (e.g., Risk-On, Stagflationary Fear, Flight to Quality).
2. Assess money market expectations (ECB/Fed pricing).
3. Detail expected yield curve dynamics (flattening/steepening) using the Rationale-First approach.
4. Provide a granular sovereign spread outlook (e.g., BTP-Bund) based on flows, supply, and ECB signaling.
5. If government bond auctions are scheduled today, analyze their expected secondary market impact and digestion mechanics.
6. Conclude with specific, executable trade ideas (e.g., curve trades, spread trades, outright directional biases).
</instructions>
"""

RESEARCH_SYNTHESIS_PROMPT = """\
<role>Financial Intelligence Synthesizer</role>
<instructions>
You are given a set of search results gathered from the web to investigate an overnight market anomaly.
Synthesize the factual cause of the market movement in exactly 3 concise, highly analytical sentences.
Focus strictly on the macroeconomic catalyst, geopolitical shock, or institutional leak.
Do not offer trading advice here; just explain the facts of what happened.
</instructions>
"""


class MorningAgentPipeline:
    """
    Agentic pipeline that processes raw market data through a 3-node cognitive architecture
    to produce a structured Fixed Income Morning Playbook.
    """

    def __init__(self):
        # Initialize the Google GenAI client using the new SDK
        self._client = genai.Client(api_key=os.environ.get("_API_KEY"))
        
        # Initialize Tavily client for deep research
        tavily_key = os.environ.get("TAVILY_API_KEY")
        self.tavily_client = TavilyClient(api_key=tavily_key) if tavily_key else None
        
        if not tavily_key:
            logger.warning("TAVILY_API_KEY is not set. Node 2 (Deep Research) will be skipped if anomalies are detected.")

    def _run_node_1_triage(self, payload: HarvestedPayload) -> TriageOutputSchema:
        """
        NODE 1: Triage and Anomaly Detection.
        Evaluates raw payload, filters noise, and decides if external research is needed.
        """
        logger.info("Starting Node 1: Triage & Anomaly Detection...")
        
        config = types.GenerateContentConfig(
            system_instruction=TRIAGE_SYSTEM_PROMPT,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=TriageOutputSchema
        )
        
        prompt_content = f"Harvested Morning Data:\n{payload.model_dump_json(indent=2)}"
        
        response = self._client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_content,
            config=config
        )
        
        triage_output = TriageOutputSchema.model_validate_json(response.text)
        logger.info(f"Node 1 Complete. Anomaly detected: {triage_output.anomaly_detected}")
        return triage_output

    def _run_node_2_deep_research(self, triage_output: TriageOutputSchema) -> Optional[str]:
        """
        NODE 2: Conditional Deep Dive via Tavily.
        Executes a targeted web search if an anomaly was detected and synthesizes the findings.
        """
        if not triage_output.anomaly_detected or not triage_output.tavily_search_query:
            logger.info("Node 2 Skipped: No anomaly detected.")
            return None
            
        if not self.tavily_client:
            logger.warning("Node 2 Skipped: Tavily API key missing despite anomaly detection.")
            return "Web research skipped due to missing Tavily API key."

        logger.info(f"Starting Node 2: Tavily Search for query: '{triage_output.tavily_search_query}'")
        
        try:
            search_results = self.tavily_client.search(
                query=triage_output.tavily_search_query,
                search_depth="advanced",
                max_results=3
            )
            
            # Synthesize search results with a quick Gemini Flash call
            config = types.GenerateContentConfig(
                system_instruction=RESEARCH_SYNTHESIS_PROMPT,
                temperature=0.1
            )
            
            synthesis_prompt = f"Search Query: {triage_output.tavily_search_query}\n\nSearch Results:\n{search_results}"
            
            synthesis_response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=synthesis_prompt,
                config=config
            )
            
            logger.info("Node 2 Complete: Research synthesized.")
            return synthesis_response.text
            
        except Exception as e:
            logger.error(f"Node 2 Failed during Tavily search or synthesis: {e}")
            return f"Deep research failed due to an error: {e}"

    def _run_node_3_strategist(
        self, 
        payload: HarvestedPayload, 
        triage_output: TriageOutputSchema, 
        research_synthesis: Optional[str]
    ) -> MorningPlaybookSchema:
        """
        NODE 3: Strategist Synthesizer.
        Generates the final structured Morning Playbook using a more powerful model.
        """
        logger.info("Starting Node 3: Lead Strategist Synthesis...")
        
        config = types.GenerateContentConfig(
            system_instruction=STRATEGIST_SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=MorningPlaybookSchema
        )
        
        # Construct the unified context for the Strategist
        context_parts = [
            "--- RAW HARVESTED DATA ---",
            payload.model_dump_json(indent=2),
            "\n--- TRIAGE ANALYST REPORT ---",
            triage_output.model_dump_json(indent=2)
        ]
        
        if research_synthesis:
            context_parts.extend([
                "\n--- DEEP RESEARCH (ANOMALY INVESTIGATION) ---",
                research_synthesis
            ])
            
        full_context = "\n".join(context_parts)
        
        response = self.gemini_client.models.generate_content(
            model="gemini-1.5-pro",
            contents=full_context,
            config=config
        )
        
        playbook_output = MorningPlaybookSchema.model_validate_json(response.text)
        logger.info("Node 3 Complete: Morning Playbook generated.")
        return playbook_output

    def execute_pipeline(self, payload: HarvestedPayload) -> MorningPlaybookSchema:
        """
        Orchestrates the entire 3-node agentic pipeline.
        """
        logger.info("=== BEGIN AGENTIC PIPELINE EXECUTION ===")
        
        # Node 1
        triage_result = self._run_node_1_triage(payload)
        
        # Node 2 (Conditional)
        research_result = self._run_node_2_deep_research(triage_result)
        
        # Node 3
        playbook = self._run_node_3_strategist(payload, triage_result, research_result)
        
        logger.info("=== PIPELINE EXECUTION COMPLETE ===")
        return playbook

# Example local execution block
if __name__ == "__main__":
    import json
    
    # Simple mock payload to test the pipeline initialization and structure
    mock_payload_json = {
        "market_moves": [
            {"ticker": "^TNX", "close_price": 4.15, "percentage_change": 2.5, "volume": None},
            {"ticker": "EURUSD=X", "close_price": 1.085, "percentage_change": -0.8, "volume": None}
        ],
        "macro_events": [],
        "news_items": []
    }
    
    try:
        mock_payload = HarvestedPayload.model_validate(mock_payload_json)
        pipeline = MorningAgentPipeline()
        
        print("Pipeline initialized successfully. Ready for execution.")
        # Note: Actual execution requires valid GEMINI_API_KEY environment variable
        # result = pipeline.execute_pipeline(mock_payload)
        # print(result.model_dump_json(indent=2))
        
    except Exception as e:
        logger.error(f"Test block failed: {e}")
