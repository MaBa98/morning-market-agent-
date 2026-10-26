# src/__init__.py

"""
Morning Market Intelligence Agent
=================================

Un modulo Python serverless per la raccolta, l'analisi agentica (tramite LLM) 
e la sintesi di dati macroeconomici e di mercato obbligazionario (Fixed Income).

Moduli principali:
- schemas.py: Contratti dati Pydantic v2.
- harvester.py: Raccolta resiliente di API REST, RSS e YFinance.
- agent_brain.py: Pipeline cognitiva basata su Google Gemini SDK.
- database.py: Persistenza cloud su Supabase.
"""

__version__ = "1.0.0"
__author__ = "Principal Quant Developer"

# Se lo desideri, puoi esporre le classi principali direttamente a livello di package
# per semplificare gli import nel main_worker.py, scommentando le righe seguenti:

# from .schemas import HarvestedPayload, MorningPlaybookSchema
# from .harvester import collect_all_morning_data
# from .agent_brain import MorningAgentPipeline
# from .database import SupabaseManager
