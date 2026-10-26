# app.py

import os
import json
import logging
from datetime import datetime, date
import pytz
import streamlit as st
import pandas as pd

# Tentativo di importazione dei moduli di backend (per rigenerazione live e DB)
try:
    from src.database import SupabaseManager
    from src.harvester import collect_all_morning_data
    from src.agent_brain import MorningAgentPipeline
    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False

st.set_page_config(
    page_title="Morning Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 1. UI & STYLING (Dark Mode Glassmorphism)
# ==========================================

CSS = """
<style>
/* Base Dark Theme Overrides */
.stApp {
    background-color: #0B0F19;
    color: #E2E8F0;
}
/* Hide Streamlit Branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Typography */
h1, h2, h3, h4 { color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.mono { font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace; }

/* Glassmorphism Cards */
.glass-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 18px;
    margin-bottom: 16px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

/* Badges */
.badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; letter-spacing: 0.5px; }
.badge-red { background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
.badge-green { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
.badge-amber { background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.3); }
.badge-blue { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }

/* Metrics */
.metric-val { font-size: 1.4rem; font-weight: 700; color: #FFFFFF; }
.metric-up { color: #34D399; font-weight: 600; font-size: 0.9rem; }
.metric-down { color: #F87171; font-weight: 600; font-size: 0.9rem; }

/* Scenario Matrix Boxes */
.scenario-box-red {
    border: 1px solid rgba(239, 68, 68, 0.4);
    background: rgba(239, 68, 68, 0.05);
    padding: 14px;
    border-radius: 8px;
    height: 100%;
}
.scenario-box-green {
    border: 1px solid rgba(16, 185, 129, 0.4);
    background: rgba(16, 185, 129, 0.05);
    padding: 14px;
    border-radius: 8px;
    height: 100%;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ==========================================
# 2. AUTHENTICATION
# ==========================================

def check_password():
    """Returns `True` if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Gestione in blocco centrale
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>🔒 Morning Desk Playbook</h3>", unsafe_allow_html=True)
        pwd = st.text_input("Institutional Password", type="password", key="pwd_input")
        if pwd:
            expected_pwd = st.secrets.get("APP_PASSWORD", "admin") # fallback a 'admin' se manca nei secrets
            if pwd == expected_pwd:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Access Denied.")
    return False

# ==========================================
# 3. DATA FETCHING LOGIC
# ==========================================

@st.cache_data(ttl=300)
def load_historical_dates():
    if BACKEND_AVAILABLE and os.environ.get("SUPABASE_URL"):
        try:
            db = SupabaseManager()
            return db.get_available_dates_and_regimes()
        except Exception:
            pass
    return []

@st.cache_data(ttl=300)
def load_playbook_data(target_date_str: str):
    # Prova su DB
    if BACKEND_AVAILABLE and os.environ.get("SUPABASE_URL"):
        try:
            db = SupabaseManager()
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            record = db.get_playbook_by_date(target_date)
            if record:
                return record.get("raw_harvester_data"), record.get("playbook_content")
        except Exception:
            pass
    
    # Fallback su file locale debug se DB non va o non è configurato
    if os.path.exists("latest_playbook_debug.json"):
        with open("latest_playbook_debug.json", "r") as f:
            data = json.load(f)
            return data.get("raw_payload"), data.get("playbook")
            
    return None, None

def get_badge_class(regime: str) -> str:
    regime_upper = regime.upper()
    if any(k in regime_upper for k in ['BEAR', 'SELL', 'INFLATION', 'HAWK']):
        return "badge-red"
    elif any(k in regime_upper for k in ['BULL', 'BUY', 'RISK', 'DOVE', 'EASING']):
        return "badge-green"
    elif any(k in regime_upper for k in ['WAIT', 'RANGE', 'STABLE', 'FLAT']):
        return "badge-amber"
    return "badge-blue"

def format_cet_time(utc_time_str: str) -> str:
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        cet_dt = utc_dt.astimezone(pytz.timezone('Europe/Rome'))
        return cet_dt.strftime("%H:%M")
    except:
        return utc_time_str

# ==========================================
# 4. MAIN APP LAYOUT
# ==========================================

def main():
    if not check_password():
        return

    # --- SIDEBAR STORICA ---
    with st.sidebar:
        st.markdown("### 🗄️ Storico Playbook")
        
        hist_data = load_historical_dates()
        
        # Filtro per regime di mercato (Backtesting qualitativo)
        available_regimes = ["Tutti"] + sorted(list(set([x.get("market_regime_badge", "") for x in hist_data]))) if hist_data else ["Tutti"]
        selected_regime = st.selectbox("🔍 Filtra per Regime", available_regimes)
        
        # Filtraggio
        if selected_regime != "Tutti":
            hist_data = [x for x in hist_data if x.get("market_regime_badge") == selected_regime]
            
        date_options = [x.get("report_date") for x in hist_data] if hist_data else [datetime.today().strftime("%Y-%m-%d")]
        selected_date = st.selectbox("📅 Seleziona Data", date_options)
        
        st.markdown("---")
        if st.button("⚡ Rigenera Playbook Live", use_container_width=True, type="primary"):
            if BACKEND_AVAILABLE:
                with st.spinner("Harvesting & AI Synthesis in corso..."):
                    try:
                        payload = collect_all_morning_data()
                        pipeline = MorningAgentPipeline()
                        new_pb = pipeline.execute_pipeline(payload)
                        # Salva o logga l'output in locale per render immediato
                        out_data = {"raw_payload": payload.model_dump(mode="json"), "playbook": new_pb.model_dump(mode="json")}
                        with open("latest_playbook_debug.json", "w") as f:
                            json.dump(out_data, f)
                        st.cache_data.clear() # reset cache
                        st.success("Playbook Rigenerato!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore generazione: {e}")
            else:
                st.error("Backend modules not found. Running in UI-only mode.")

    # --- FETCH DATA ---
    raw_data, playbook = load_playbook_data(selected_date)
    
    if not raw_data or not playbook:
        st.warning(f"⚠️ Nessun dato disponibile per il {selected_date}. Esegui la pipeline o controlla la connessione al DB.")
        return

    # --- HEADER & KPI STRIP ---
    regime = playbook.get('market_regime_classification', 'UNKNOWN')
    badge_cls = get_badge_class(regime)
    
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
            <h2 style="margin: 0;">Morning Desk Playbook</h2>
            <span class="badge {badge_cls}">{regime}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # KPI OVERNIGHT FLOWS
    moves = raw_data.get("market_moves", [])
    if moves:
        cols = st.columns(len(moves))
        for idx, move in enumerate(moves):
            ticker = move.get("ticker", "")
            price = move.get("close_price", 0)
            pct = move.get("percentage_change", 0)
            color_class = "metric-up" if pct > 0 else "metric-down"
            sign = "+" if pct > 0 else ""
            
            with cols[idx]:
                st.markdown(f"""
                    <div class="glass-card" style="padding: 10px; text-align: center;">
                        <div style="color: #94A3B8; font-size: 0.8rem; font-weight: 600;">{ticker}</div>
                        <div class="metric-val mono">{price:.4f}</div>
                        <div class="{color_class} mono">{sign}{pct:.2f}%</div>
                    </div>
                """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)

    # --- MAIN 2-COLUMN LAYOUT ---
    col_left, col_right = st.columns([1, 1.3], gap="large")

    with col_left:
        # OVERNIGHT COMMENTARY & BIAS
        st.markdown("### 🌐 European Opening Bias & MM")
        st.markdown(f"""
            <div class="glass-card">
                <p style="color: #cbd5e1; line-height: 1.6;">{playbook.get('causal_reasoning', 'N/A')}</p>
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <strong style="color: #60A5FA;">STIRs / ESTR Expectations:</strong>
                    <p style="margin-top: 5px; color: #94A3B8;">{playbook.get('money_market_expectations', 'N/A')}</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # SUPPLY & LIQUIDITY WATCH
        auctions = playbook.get("auction_supply_digestion", [])
        if auctions:
            st.markdown("### 🏛️ Primary Supply Watch")
            for auc in auctions:
                st.markdown(f"""
                    <div class="glass-card" style="border-left: 3px solid #F59E0B;">
                        <div style="font-weight: bold; color: #FCD34D;">{auc.get('sovereign', 'Auction')}</div>
                        <p style="margin: 8px 0; color: #E2E8F0; font-size: 0.9rem;">{auc.get('transmission_mechanism_reasoning', '')}</p>
                        <div class="mono" style="color: #94A3B8; font-size: 0.85rem;">➔ Impact: {auc.get('estimated_market_impact', '')}</div>
                    </div>
                """, unsafe_allow_html=True)

        # MACRO CHRONOLOGICAL TABLE
        events = raw_data.get("macro_events", [])
        if events:
            st.markdown("### ⏱️ Chronological Catalysts (CET)")
            # Costruiamo una tabella usando HTML/CSS inject o st.dataframe
            # HTML/CSS custom è più coerente col design
            table_html = """
            <div class="glass-card" style="padding: 0;">
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem;">
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: #94A3B8;">
                        <th style="padding: 10px;">Time</th>
                        <th style="padding: 10px;">Ctry</th>
                        <th style="padding: 10px;">Event</th>
                        <th style="padding: 10px;">Cons</th>
                        <th style="padding: 10px;">Prior</th>
                    </tr>
            """
            for ev in sorted(events, key=lambda x: x.get("timestamp")):
                t = format_cet_time(ev.get("timestamp"))
                c = ev.get("country", "")
                e = ev.get("event_name", "")
                cons = ev.get("consensus", "-") or "-"
                pr = ev.get("previous", "-") or "-"
                
                table_html += f"""
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td class="mono" style="padding: 10px; color: #60A5FA;">{t}</td>
                        <td style="padding: 10px; font-weight: bold;">{c}</td>
                        <td style="padding: 10px;">{e}</td>
                        <td class="mono" style="padding: 10px; color: #FCD34D;">{cons}</td>
                        <td class="mono" style="padding: 10px; color: #94A3B8;">{pr}</td>
                    </tr>
                """
            table_html += "</table></div>"
            st.markdown(table_html, unsafe_allow_html=True)
            
        # TRADE IDEAS
        ideas = playbook.get("actionable_trade_ideas", [])
        if ideas:
            st.markdown("### 🎯 Actionable Trade Ideas")
            for idea in ideas:
                st.markdown(f"- {idea}")

    with col_right:
        st.markdown("### 📉 Yield Curve Scenarios (Sensitivity Matrix)")
        
        curves = playbook.get("yield_curve_scenarios", [])
        for cv in curves:
            with st.expander(f"🔮 {cv.get('curve', 'Curve')} ➔ {cv.get('expected_shape_change', 'Unknown')}", expanded=True):
                st.markdown(f"<div style='color: #cbd5e1; margin-bottom: 15px; font-style: italic;'>{cv.get('transmission_mechanism_reasoning', '')}</div>", unsafe_allow_html=True)
                
                sc_col1, sc_col2 = st.columns(2)
                with sc_col1:
                    st.markdown(f"""
                        <div class="scenario-box-red">
                            <h4 style="color: #F87171; margin-top: 0; font-size: 1rem;">🔥 Hawkish Tail Risk</h4>
                            <p style="font-size: 0.9rem; color: #E2E8F0; margin-bottom: 0;">{cv.get('hawkish_risk_scenario', '')}</p>
                        </div>
                    """, unsafe_allow_html=True)
                with sc_col2:
                    st.markdown(f"""
                        <div class="scenario-box-green">
                            <h4 style="color: #34D399; margin-top: 0; font-size: 1rem;">🧊 Dovish Tail Risk</h4>
                            <p style="font-size: 0.9rem; color: #E2E8F0; margin-bottom: 0;">{cv.get('dovish_risk_scenario', '')}</p>
                        </div>
                    """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🦅 Sovereign Spreads Outlook")
        
        spreads = playbook.get("sovereign_spread_outlook", [])
        for sp in spreads:
            pair = sp.get('pair', '')
            direction = sp.get('expected_direction', '')
            dir_color = "#F87171" if "Widen" in direction else "#34D399" if "Tight" in direction else "#FBBF24"
            
            st.markdown(f"""
                <div class="glass-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <strong style="font-size: 1.1rem; color: #FFFFFF;">{pair}</strong>
                        <span class="mono" style="color: {dir_color}; font-weight: 600; font-size: 0.9rem;">➔ {direction}</span>
                    </div>
                    <p style="color: #94A3B8; font-size: 0.9rem;">{sp.get('causal_reasoning', '')}</p>
                    <ul style="color: #cbd5e1; font-size: 0.85rem; padding-left: 20px; margin-bottom: 0;">
                        {''.join([f"<li>{d}</li>" for d in sp.get('key_drivers', [])])}
                    </ul>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
