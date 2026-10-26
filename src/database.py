# src/database.py

import os
import logging
from datetime import date
from typing import List, Dict, Optional, Any

from supabase import create_client, Client
from src.schemas import HarvestedPayload, MorningPlaybookSchema

logger = logging.getLogger(__name__)

class SupabaseManager:
    """
    Handles data persistence for the Morning Market Intelligence system using Supabase.
    """
    
    def __init__(self):
        supabase_url: str = os.environ.get("https://qlpjeckpgmxyeghliejx.supabase.co", "")
        supabase_key: str = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFscGplY2twZ214eWVnaGxpZWp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwMDM0OTIsImV4cCI6MjEwODU3OTQ5Mn0.snmVXYjOcUApCBYQjKdT01-DvM-t43hZs-PDEjywhTc", "")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be configured.")
            
        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = "morning_playbooks"

    def save_daily_playbook(
        self, 
        report_date: date, 
        raw_data: HarvestedPayload, 
        playbook: MorningPlaybookSchema
    ) -> bool:
        """
        Upserts the generated morning playbook and raw harvested data into Supabase.
        """
        logger.info(f"Saving daily playbook to Supabase for date: {report_date}")
        
        try:
            # Pydantic v2 mode="json" handles datetime serialization safely
            raw_data_dict = raw_data.model_dump(mode="json")
            playbook_dict = playbook.model_dump(mode="json")
            
            # Construct a dynamic headline for the frontend
            headline = f"Fixed Income Playbook: {playbook.market_regime_classification}"
            
            payload = {
                "report_date": report_date.isoformat(),
                "market_regime_badge": playbook.market_regime_classification,
                "playbook_headline": headline,
                "raw_harvester_data": raw_data_dict,
                "playbook_content": playbook_dict
            }
            
            # upsert handles both INSERT (if new date) and UPDATE (if re-run on same date)
            response = self.client.table(self.table_name).upsert(payload).execute()
            
            if response.data:
                logger.info(f"Successfully upserted playbook for {report_date}.")
                return True
            else:
                logger.warning(f"Upsert returned no data for {report_date}.")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save daily playbook to Supabase: {e}")
            return False

    def get_playbook_by_date(self, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Retrieves the complete playbook payload for a specific date.
        """
        logger.info(f"Fetching playbook from Supabase for date: {target_date}")
        
        try:
            response = self.client.table(self.table_name) \
                .select("*") \
                .eq("report_date", target_date.isoformat()) \
                .execute()
                
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            logger.info(f"No playbook found for date {target_date}.")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve playbook for {target_date}: {e}")
            return None

    def get_available_dates_and_regimes(self, limit: int = 60) -> List[Dict[str, Any]]:
        """
        Fetches a lightweight list of historical playbooks for the Streamlit sidebar navigation.
        """
        logger.info(f"Fetching last {limit} available playbook dates and regimes.")
        
        try:
            response = self.client.table(self.table_name) \
                .select("report_date, playbook_headline, market_regime_badge") \
                .order("report_date", desc=True) \
                .limit(limit) \
                .execute()
                
            if response.data:
                return response.data
            return []
            
        except Exception as e:
            logger.error(f"Failed to retrieve available dates: {e}")
            return []
