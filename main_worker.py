# main_worker.py

import sys
import json
import logging
import argparse
from datetime import datetime, timezone

from src.harvester import collect_all_morning_data
from src.agent_brain import MorningAgentPipeline
from src.database import SupabaseManager

# Configure structured logging for the orchestrator
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MorningOrchestrator")


def main() -> None:
    parser = argparse.ArgumentParser(description="Morning Market Intelligence Agent Worker")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Run the pipeline and save output locally to a JSON file instead of Supabase."
    )
    args = parser.parse_args()

    logger.info("=== STARTING MORNING MARKET INTELLIGENCE WORKER ===")
    
    try:
        # Step 1: Harvest Raw Data
        logger.info("Phase 1: Harvesting data...")
        raw_payload = collect_all_morning_data()
        
        # Step 2: Agentic Synthesis (Nodes 1, 2, and 3)
        logger.info("Phase 2: Executing Agentic Pipeline...")
        agent_pipeline = MorningAgentPipeline()
        playbook = agent_pipeline.execute_pipeline(raw_payload)
        
        # Step 3: Persistence
        if args.dry_run:
            logger.info("Phase 3 (Dry-Run): Saving payload and playbook locally...")
            debug_output = {
                "raw_payload": raw_payload.model_dump(mode="json"),
                "playbook": playbook.model_dump(mode="json")
            }
            with open("latest_playbook_debug.json", "w", encoding="utf-8") as f:
                json.dump(debug_output, f, indent=4, ensure_ascii=False)
            logger.info("Saved to latest_playbook_debug.json")
        else:
            logger.info("Phase 3 (Production): Persisting to Supabase...")
            db_manager = SupabaseManager()
            today_date = datetime.now(timezone.utc).date()
            
            success = db_manager.save_daily_playbook(
                report_date=today_date,
                raw_data=raw_payload,
                playbook=playbook
            )
            
            if not success:
                logger.error("Failed to save playbook to Supabase.")
                sys.exit(1)
                
        logger.info("=== WORKER EXECUTION COMPLETED SUCCESSFULLY ===")

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in Worker Pipeline: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
