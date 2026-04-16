# “””

# PRODUCT MANAGEMENT COMMAND CENTER
Fund Administration Operations Intelligence Platform

A local-first, SQLite-backed Streamlit application for tracking BAU issues,
strategic projects, commercial data, and operational friction in a fund
administration environment.

# Author: PM Command Center
Stack: Python 3.x · Streamlit · SQLite3 · Pandas

“””

import streamlit as st
import sqlite3
import pandas as pd
import json
import subprocess
import tempfile
import textwrap
from datetime import datetime, date, timedelta
from pathlib import Path

# =============================================================================

# CONFIGURATION

# =============================================================================

DB_PATH = Path(“command_center.db”)
APP_TITLE = “PM Command Center”
APP_ICON = “🏛️”

# Refined monotone slate palette — colour appears only where it carries meaning

THEME = {
# Base neutrals (light mode — easier on the eyes for long reading sessions)
“bg_primary”: “#f8fafc”,       # near-white app background
“bg_card”: “#ffffff”,           # card surfaces
“bg_card_hover”: “#f1f5f9”,     # subtle hover
“bg_elevated”: “#e2e8f0”,       # elevated surfaces (tabs, badges)
“border”: “#e2e8f0”,            # hairline borders
“border_strong”: “#cbd5e1”,     # emphasised borders

```
# Text hierarchy
"text_primary": "#0f172a",      # near-black for body
"text_secondary": "#475569",    # muted labels
"text_muted": "#94a3b8",        # captions, metadata

# Single neutral accent — slate-900 — used for buttons, links, emphasis
"accent": "#1e293b",            # primary interactive colour
"accent_soft": "#334155",       # hover state

# Signal colours — ONLY for semantic meaning, never decoration
"signal_risk": "#991b1b",       # risk / overdue / blocked
"signal_warn": "#92400e",       # warning / near miss / attention
"signal_ok": "#166534",         # healthy / on track / mitigated
"signal_info": "#1e40af",       # informational only

# Backward-compat aliases so existing references still resolve
"accent_cyan": "#1e293b",       # was cyan — now slate
"accent_amber": "#92400e",      # was amber — now warn
"accent_red": "#991b1b",        # was red — now risk
"accent_green": "#166534",      # was green — now ok
"accent_purple": "#475569",     # was purple — now muted slate
```

}

# =============================================================================

# DATABASE LAYER

# =============================================================================

def get_connection() -> sqlite3.Connection:
“”“Create a new database connection. Each call = fresh connection.”””
conn = sqlite3.connect(str(DB_PATH))
conn.execute(“PRAGMA journal_mode=WAL”)
conn.execute(“PRAGMA foreign_keys=ON”)
return conn

def run_query(query: str, params: tuple = (), fetch: bool = False):
“””
Safe database helper. Opens, executes, commits, closes.
If fetch=True, returns rows as list of tuples.
“””
conn = get_connection()
try:
cur = conn.cursor()
cur.execute(query, params)
if fetch:
result = cur.fetchall()
conn.close()
return result
conn.commit()
finally:
conn.close()

def run_query_df(query: str, params: tuple = ()) -> pd.DataFrame:
“”“Execute a SELECT and return a Pandas DataFrame.”””
conn = get_connection()
try:
df = pd.read_sql_query(query, conn, params=params)
finally:
conn.close()
return df

def init_database():
“””
Idempotent schema initialisation.
Creates all six operational tables if they do not already exist.
“””
conn = get_connection()
cur = conn.cursor()

```
cur.execute("""
    CREATE TABLE IF NOT EXISTS client_roster (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        fee_bps REAL DEFAULT 0.0,
        manual_tasks INTEGER DEFAULT 0,
        last_reprice_date TEXT,
        margin_status TEXT DEFAULT 'Sweet Spot'
            CHECK(margin_status IN ('Sweet Spot', 'Leaking'))
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS active_rfps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_name TEXT NOT NULL,
        due_date TEXT,
        status TEXT DEFAULT 'Draft'
            CHECK(status IN ('Draft', 'In Progress', 'Submitted', 'Won', 'Lost')),
        probability REAL DEFAULT 0.0,
        lead_owner TEXT
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS rfp_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        standard_question TEXT,
        golden_answer TEXT
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS change_pipeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        type TEXT DEFAULT 'Change Request'
            CHECK(type IN ('Onboarding', 'Change Request')),
        stage TEXT DEFAULT 'Intake',
        blocker_dept TEXT DEFAULT 'None'
            CHECK(blocker_dept IN ('Legal', 'Ops', 'Tech', 'None')),
        blocked_since TEXT
    )
""")

# --- Audit log: timestamped record of every data change ---
cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        table_name TEXT NOT NULL,
        action TEXT NOT NULL
            CHECK(action IN ('INSERT', 'UPDATE', 'DELETE')),
        record_summary TEXT,
        field_changes TEXT
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS incidents_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_date TEXT,
        type TEXT DEFAULT 'Error'
            CHECK(type IN ('Error', 'Near Miss', 'Service Issue')),
        impact_level TEXT DEFAULT 'Low'
            CHECK(impact_level IN ('Low', 'Medium', 'High', 'Critical')),
        root_cause TEXT,
        mitigation_status TEXT DEFAULT 'Open'
            CHECK(mitigation_status IN ('Open', 'In Progress', 'Mitigated', 'Closed'))
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS ops_friction (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_name TEXT NOT NULL,
        manual_hours_per_week REAL DEFAULT 0.0,
        affected_client TEXT,
        systemic_fix_idea TEXT
    )
""")

# --- Action Items: task-level tracking with ownership & linkage ---
cur.execute("""
    CREATE TABLE IF NOT EXISTS action_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        owner TEXT,
        due_date TEXT,
        source TEXT DEFAULT 'Ad Hoc',
        linked_table TEXT,
        linked_record TEXT,
        priority TEXT DEFAULT 'Medium'
            CHECK(priority IN ('Low', 'Medium', 'High', 'Critical')),
        status TEXT DEFAULT 'Open'
            CHECK(status IN ('Open', 'In Progress', 'Done', 'Cancelled')),
        created_date TEXT
    )
""")

# --- Meeting Notes: institutional memory of governance & client calls ---
cur.execute("""
    CREATE TABLE IF NOT EXISTS meeting_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_date TEXT NOT NULL,
        meeting_type TEXT DEFAULT 'Internal'
            CHECK(meeting_type IN ('Internal', 'Client Call', 'Governance', 'Steering Committee', 'Vendor', 'Other')),
        title TEXT NOT NULL,
        attendees TEXT,
        key_decisions TEXT,
        discussion_notes TEXT,
        actions_generated TEXT
    )
""")

# --- Stakeholder Tracker: political landscape & relationship management ---
cur.execute("""
    CREATE TABLE IF NOT EXISTS stakeholders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        department TEXT,
        organisation TEXT DEFAULT 'Internal',
        disposition TEXT DEFAULT 'Neutral'
            CHECK(disposition IN ('Sponsor', 'Advocate', 'Neutral', 'Sceptic', 'Blocker')),
        influence_level TEXT DEFAULT 'Medium'
            CHECK(influence_level IN ('Low', 'Medium', 'High', 'Key Decision Maker')),
        jersey_number INTEGER,
        last_interaction_date TEXT,
        interaction_notes TEXT,
        preferred_channel TEXT DEFAULT 'Email'
            CHECK(preferred_channel IN ('Email', 'Teams', 'In Person', 'Phone', 'Slack')),
        topics_of_interest TEXT
    )
""")

conn.commit()

# --- Schema migration: days_stuck → blocked_since for existing DBs ---
cur.execute("PRAGMA table_info(change_pipeline)")
columns = [row[1] for row in cur.fetchall()]
if "days_stuck" in columns and "blocked_since" not in columns:
    cur.execute("ALTER TABLE change_pipeline ADD COLUMN blocked_since TEXT")
    # Back-fill: convert days_stuck into an approximate blocked_since date
    cur.execute("""
        UPDATE change_pipeline
        SET blocked_since = date('now', '-' || days_stuck || ' days')
        WHERE days_stuck > 0 AND blocker_dept != 'None'
    """)
    conn.commit()

# --- FTS5 full-text search index for the RFP library ---
cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS rfp_library_fts USING fts5(
        category, standard_question, golden_answer,
        content='rfp_library', content_rowid='id'
    )
""")
conn.commit()

conn.close()
```

# =============================================================================

# DATA ACCESS — cached loaders (cache clears on DB write)

# =============================================================================

def load_table(table_name: str) -> pd.DataFrame:
“”“Load full table into DataFrame. Called fresh after every write.”””
return run_query_df(f”SELECT * FROM {table_name}”)

def rebuild_rfp_fts():
“”“Rebuild the FTS5 index from the rfp_library source table.”””
conn = get_connection()
try:
# For external-content FTS5 tables, use the rebuild command
conn.execute(“INSERT INTO rfp_library_fts(rfp_library_fts) VALUES(‘rebuild’)”)
conn.commit()
finally:
conn.close()

def search_rfp_library(query: str) -> pd.DataFrame:
“””
Full-text search against the RFP library using SQLite FTS5.
Returns matching rows with BM25-ranked relevance.
“””
if not query or not query.strip():
return pd.DataFrame()

```
# Rebuild index before searching to ensure freshness
rebuild_rfp_fts()

# FTS5 query — wrap terms for prefix matching
fts_query = " OR ".join(f'"{t}"*' for t in query.strip().split() if t)

sql = """
    SELECT r.id, r.category, r.standard_question, r.golden_answer,
           rank AS relevance_score
    FROM rfp_library_fts fts
    JOIN rfp_library r ON r.id = fts.rowid
    WHERE rfp_library_fts MATCH ?
    ORDER BY rank
"""
return run_query_df(sql, (fts_query,))
```

def write_table(table_name: str, df: pd.DataFrame):
“””
Audit-aware write strategy:
1. Snapshot current state (before).
2. Diff against incoming DataFrame to detect inserts, updates, deletes.
3. Log every change to audit_log with timestamp and field-level detail.
4. Full-replace the table with the new data.
“””
conn = get_connection()
cur = conn.cursor()
try:
# –– Step 1: snapshot before-state keyed by id ––
before_df = pd.read_sql_query(f”SELECT * FROM {table_name}”, conn)
before_map = {}
if not before_df.empty and “id” in before_df.columns:
before_map = {
int(row[“id”]): row.to_dict()
for _, row in before_df.iterrows()
if pd.notna(row[“id”])
}

```
    # ---- Step 2: compute diffs ----
    now_iso = datetime.now().isoformat()
    audit_entries = []

    after_map = {}
    if not df.empty and "id" in df.columns:
        after_map = {
            int(row["id"]): row.to_dict()
            for _, row in df.iterrows()
            if pd.notna(row.get("id"))
        }

    # Detect DELETES: ids in before but not after
    for old_id, old_row in before_map.items():
        if old_id not in after_map:
            summary = _row_summary(table_name, old_row)
            audit_entries.append((now_iso, table_name, "DELETE", summary, ""))

    # Detect INSERTS and UPDATES
    data_cols = [c for c in df.columns if c != "id"]
    for _, row in df.iterrows():
        row_id = row.get("id")
        if pd.isna(row_id) or int(row_id) not in before_map:
            # INSERT — new row (no id or id not in before)
            summary = _row_summary(table_name, row.to_dict())
            audit_entries.append((now_iso, table_name, "INSERT", summary, ""))
        else:
            # Potential UPDATE — compare field by field
            old_row = before_map[int(row_id)]
            changes = []
            for col in data_cols:
                old_val = old_row.get(col)
                new_val = row[col]
                # Normalise NaN/None
                old_val = None if pd.isna(old_val) else old_val
                new_val = None if pd.isna(new_val) else new_val
                if str(old_val) != str(new_val):
                    changes.append(f"{col}: '{old_val}' → '{new_val}'")
            if changes:
                summary = _row_summary(table_name, row.to_dict())
                audit_entries.append(
                    (now_iso, table_name, "UPDATE", summary, "; ".join(changes))
                )

    # ---- Step 3: write audit entries ----
    for ts, tbl, action, summary, field_changes in audit_entries:
        cur.execute(
            "INSERT INTO audit_log (timestamp, table_name, action, record_summary, field_changes) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, tbl, action, summary, field_changes),
        )

    # ---- Step 4: full-replace the table ----
    cur.execute(f"DELETE FROM {table_name}")

    if not df.empty:
        cols = [c for c in df.columns if c != "id"]
        if cols:
            placeholders = ", ".join(["?"] * len(cols))
            col_str = ", ".join(cols)
            for _, row in df.iterrows():
                vals = tuple(
                    None if pd.isna(row[c]) else row[c] for c in cols
                )
                cur.execute(
                    f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})",
                    vals,
                )
    conn.commit()
finally:
    conn.close()
```

def _row_summary(table_name: str, row: dict) -> str:
“””
Generate a human-readable one-line summary of a row for audit display.
Uses the most identifiable field per table.
“””
label_fields = {
“client_roster”: “client_name”,
“active_rfps”: “prospect_name”,
“rfp_library”: “category”,
“change_pipeline”: “project_name”,
“incidents_log”: “root_cause”,
“ops_friction”: “process_name”,
“action_items”: “task”,
“meeting_notes”: “title”,
“stakeholders”: “name”,
}
field = label_fields.get(table_name, “”)
label = row.get(field, “unknown”) if field else “unknown”
return f”{table_name} → {label}”

# =============================================================================

# STYLING

# =============================================================================

def inject_css():
“”“Inject custom CSS for a refined monotone slate aesthetic optimised for readability.”””
st.markdown(
f”””
<style>
/* — Global overrides — */
.stApp {{
background-color: {THEME[‘bg_primary’]};
}}

```
    /* Body text — system serif/sans for legibility */
    html, body, [class*="css"] {{
        color: {THEME['text_primary']};
    }}

    /* Metric cards — clean, bordered, generous padding */
    [data-testid="stMetric"] {{
        background: {THEME['bg_card']};
        border: 1px solid {THEME['border']};
        border-radius: 6px;
        padding: 18px 20px;
        transition: border-color 0.15s ease;
    }}
    [data-testid="stMetric"]:hover {{
        border-color: {THEME['border_strong']};
    }}
    [data-testid="stMetricValue"] {{
        color: {THEME['text_primary']};
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-weight: 500;
    }}
    [data-testid="stMetricLabel"] {{
        color: {THEME['text_secondary']};
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        font-weight: 500;
    }}
    [data-testid="stMetricDelta"] {{
        color: {THEME['text_muted']};
        font-size: 0.78rem;
    }}

    /* Section headers — subtle, not shouty */
    .section-header {{
        color: {THEME['text_secondary']};
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        font-weight: 500;
        border-bottom: 1px solid {THEME['border']};
        padding-bottom: 8px;
        margin-bottom: 16px;
        margin-top: 8px;
    }}

    /* Signal badges — only for semantic meaning */
    .badge-leaking, .badge-risk {{
        background: {THEME['signal_risk']}15;
        color: {THEME['signal_risk']};
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid {THEME['signal_risk']}33;
    }}
    .badge-sweet, .badge-ok {{
        background: {THEME['signal_ok']}15;
        color: {THEME['signal_ok']};
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid {THEME['signal_ok']}33;
    }}
    .badge-near-miss, .badge-warn {{
        background: {THEME['signal_warn']}15;
        color: {THEME['signal_warn']};
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid {THEME['signal_warn']}33;
    }}

    /* Sidebar — subtle separation from main area */
    [data-testid="stSidebar"] {{
        background: {THEME['bg_card']};
        border-right: 1px solid {THEME['border']};
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label {{
        padding: 4px 0;
    }}

    /* Data editor / dataframe */
    .stDataFrame {{
        border: 1px solid {THEME['border']};
        border-radius: 6px;
    }}

    /* Buttons — subtle, functional */
    .stButton > button {{
        border: 1px solid {THEME['border_strong']};
        color: {THEME['text_primary']};
        background: {THEME['bg_card']};
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        font-weight: 500;
        letter-spacing: 0.03em;
        transition: all 0.15s ease;
        padding: 6px 16px;
    }}
    .stButton > button:hover {{
        background: {THEME['accent']};
        border-color: {THEME['accent']};
        color: {THEME['bg_card']};
    }}
    .stButton > button:focus {{
        box-shadow: 0 0 0 3px {THEME['accent']}22;
    }}

    /* Download buttons match */
    .stDownloadButton > button {{
        border: 1px solid {THEME['border_strong']};
        color: {THEME['text_primary']};
        background: {THEME['bg_card']};
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
    }}
    .stDownloadButton > button:hover {{
        background: {THEME['accent']};
        border-color: {THEME['accent']};
        color: {THEME['bg_card']};
    }}

    /* Dividers — hairline only */
    hr {{
        border-color: {THEME['border']};
        margin: 1rem 0;
    }}

    /* Toast / info / warning / error — muted, not loud */
    .stAlert {{
        border-radius: 6px;
        border-width: 1px;
        font-size: 0.88rem;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid {THEME['border']};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        color: {THEME['text_secondary']};
    }}
    .stTabs [aria-selected="true"] {{
        color: {THEME['text_primary']};
        font-weight: 600;
    }}

    /* Headings — tighter, more refined */
    h1, h2, h3, h4, h5, h6 {{
        color: {THEME['text_primary']};
        font-weight: 600;
        letter-spacing: -0.01em;
    }}

    /* Captions */
    .stCaption, small {{
        color: {THEME['text_muted']};
    }}

    /* Text inputs — cleaner */
    .stTextInput input, .stTextArea textarea {{
        background: {THEME['bg_card']};
        border: 1px solid {THEME['border_strong']};
        color: {THEME['text_primary']};
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {THEME['accent']};
        box-shadow: 0 0 0 3px {THEME['accent']}15;
    }}

    /* Selectbox */
    [data-baseweb="select"] {{
        font-size: 0.88rem;
    }}

    /* Code blocks */
    code {{
        background: {THEME['bg_elevated']};
        color: {THEME['text_primary']};
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 0.86em;
    }}
</style>
""",
    unsafe_allow_html=True,
)
```

def section_header(text: str):
“”“Render a styled section header.”””
st.markdown(f’<div class="section-header">{text}</div>’, unsafe_allow_html=True)

# =============================================================================

# MODULE 1 — EXECUTIVE DASHBOARD

# =============================================================================

def render_executive_dashboard():
“”“High-level KPI overview pulling live from all tables.”””
section_header(“Executive Dashboard · Live Metrics”)

```
# — Revenue at risk: clients with margin_status = 'Leaking'
clients = load_table("client_roster")
leaking = clients[clients["margin_status"] == "Leaking"] if not clients.empty else pd.DataFrame()
leaking_count = len(leaking)
total_clients = len(clients)

# — Open incidents
incidents = load_table("incidents_log")
open_incidents = incidents[
    incidents["mitigation_status"].isin(["Open", "In Progress"])
] if not incidents.empty else pd.DataFrame()

# — Active change requests
changes = load_table("change_pipeline")
active_changes = changes[
    ~changes["stage"].isin(["Complete", "Cancelled"])
] if not changes.empty else pd.DataFrame()

# — Active RFPs
rfps = load_table("active_rfps")
active_rfps = rfps[
    rfps["status"].isin(["Draft", "In Progress", "Submitted"])
] if not rfps.empty else pd.DataFrame()

# KPI row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clients Leaking Margin", leaking_count, delta=f"of {total_clients} total")
c2.metric("Open Incidents", len(open_incidents))
c3.metric("Active Change Requests", len(active_changes))
c4.metric("Active RFPs", len(active_rfps))

st.divider()

# — Secondary metrics row
ops = load_table("ops_friction")
total_manual_hrs = ops["manual_hours_per_week"].sum() if not ops.empty else 0

blocked = changes[changes["blocker_dept"] != "None"] if not changes.empty else pd.DataFrame()

# Compute days_stuck dynamically from blocked_since
def _calc_stuck(row):
    if pd.isna(row.get("blocked_since")) or row.get("blocker_dept") == "None":
        return 0
    try:
        return (date.today() - pd.to_datetime(row["blocked_since"]).date()).days
    except Exception:
        return 0

if not changes.empty and "blocked_since" in changes.columns:
    changes = changes.copy()
    changes["days_stuck"] = changes.apply(_calc_stuck, axis=1)
elif not changes.empty:
    changes = changes.copy()
    changes["days_stuck"] = 0

stuck_gt_5 = changes[changes["days_stuck"] > 5] if not changes.empty else pd.DataFrame()

near_misses = incidents[incidents["type"] == "Near Miss"] if not incidents.empty else pd.DataFrame()

c5, c6, c7, c8 = st.columns(4)
c5.metric("Manual Hours / Week", f"{total_manual_hrs:.1f}h")
c6.metric("Blocked Projects", len(blocked))
c7.metric("Stuck > 5 Days", len(stuck_gt_5))
c8.metric("Near Misses (Leading)", len(near_misses))

# — Third metrics row: actions & stakeholders
actions = load_table("action_items")
open_actions = actions[actions["status"].isin(["Open", "In Progress"])] if not actions.empty else pd.DataFrame()
overdue_actions = pd.DataFrame()
if not open_actions.empty and "due_date" in open_actions.columns:
    open_actions_c = open_actions.copy()
    open_actions_c["due_parsed"] = pd.to_datetime(open_actions_c["due_date"], errors="coerce")
    overdue_actions = open_actions_c[open_actions_c["due_parsed"] < pd.Timestamp(date.today())]

stakeholders = load_table("stakeholders")
blockers_sh = stakeholders[stakeholders["disposition"] == "Blocker"] if not stakeholders.empty else pd.DataFrame()
sponsors_sh = stakeholders[stakeholders["disposition"].isin(["Sponsor", "Advocate"])] if not stakeholders.empty else pd.DataFrame()

c9, c10, c11, c12 = st.columns(4)
c9.metric("Open Actions", len(open_actions))
c10.metric("Overdue Actions", len(overdue_actions))
c11.metric("Sponsors/Advocates", len(sponsors_sh))
c12.metric("Known Blockers", len(blockers_sh))

st.divider()

# — Quick tables
col_left, col_right = st.columns(2)

with col_left:
    section_header("Leaking Clients")
    if not leaking.empty:
        st.dataframe(
            leaking[["client_name", "fee_bps", "manual_tasks", "last_reprice_date"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No clients flagged as leaking. Portfolio is healthy.")

with col_right:
    section_header("Near Misses — Leading Risk Indicators")
    if not near_misses.empty:
        st.dataframe(
            near_misses[["event_date", "impact_level", "root_cause", "mitigation_status"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No near misses recorded. Good operational hygiene.")
```

# =============================================================================

# MODULE 2 — COMMERCIALS & REPRICING

# =============================================================================

def render_commercials():
“”“Client roster management with margin status tracking.”””
section_header(“Commercials & Repricing · Client Roster”)

```
st.caption(
    "Edit directly in the table below. Add rows with the ＋ button at the bottom. "
    "Press **Commit Changes** to persist."
)

df = load_table("client_roster")

# Provide column config for constrained choices
edited = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "client_name": st.column_config.TextColumn("Client Name"),
        "fee_bps": st.column_config.NumberColumn("Fee (bps)", min_value=0, format="%.2f"),
        "manual_tasks": st.column_config.NumberColumn("Manual Tasks", min_value=0),
        "last_reprice_date": st.column_config.DateColumn("Last Reprice"),
        "margin_status": st.column_config.SelectboxColumn(
            "Margin Status", options=["Sweet Spot", "Leaking"], required=True
        ),
    },
    key="editor_client_roster",
)

if st.button("💾  Commit Changes", key="save_clients"):
    write_table("client_roster", edited)
    st.success("Client roster updated.")
    st.rerun()

# Summary
if not df.empty:
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        section_header("Margin Distribution")
        counts = df["margin_status"].value_counts()
        st.bar_chart(counts, color=THEME["accent_cyan"])
    with col2:
        section_header("Fee bps Spread")
        if "fee_bps" in df.columns and df["fee_bps"].notna().any():
            st.bar_chart(df.set_index("client_name")["fee_bps"], color=THEME["accent_amber"])
```

# =============================================================================

# MODULE 3 — RFP & PIPELINE MANAGEMENT

# =============================================================================

def render_rfp_pipeline():
“”“Active RFPs and the reusable RFP question library.”””

```
tab_active, tab_library, tab_search = st.tabs(["📋 Active RFPs", "📚 RFP Library", "🔍 Library Search"])

# --- Active RFPs ---
with tab_active:
    section_header("Active RFP Pipeline")
    df_rfps = load_table("active_rfps")
    edited_rfps = st.data_editor(
        df_rfps,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "prospect_name": st.column_config.TextColumn("Prospect"),
            "due_date": st.column_config.DateColumn("Due Date"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["Draft", "In Progress", "Submitted", "Won", "Lost"],
            ),
            "probability": st.column_config.NumberColumn(
                "Win %", min_value=0, max_value=100, format="%.0f%%"
            ),
            "lead_owner": st.column_config.TextColumn("Lead Owner"),
        },
        key="editor_rfps",
    )
    if st.button("💾  Commit Changes", key="save_rfps"):
        write_table("active_rfps", edited_rfps)
        st.success("RFP pipeline updated.")
        st.rerun()

    # Pipeline summary
    if not df_rfps.empty:
        st.divider()
        section_header("Pipeline Snapshot")
        status_counts = df_rfps["status"].value_counts()
        st.bar_chart(status_counts, color=THEME["accent_purple"])

# --- RFP Library ---
with tab_library:
    section_header("Golden Answer Library")
    st.caption("Build a reusable knowledge base of standard RFP Q&As.")
    df_lib = load_table("rfp_library")
    edited_lib = st.data_editor(
        df_lib,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "category": st.column_config.TextColumn("Category"),
            "standard_question": st.column_config.TextColumn("Question", width="large"),
            "golden_answer": st.column_config.TextColumn("Golden Answer", width="large"),
        },
        key="editor_rfp_lib",
    )
    if st.button("💾  Commit Changes", key="save_rfp_lib"):
        write_table("rfp_library", edited_lib)
        st.success("RFP library updated.")
        st.rerun()

# --- FTS5 Library Search ---
with tab_search:
    section_header("Full-Text Search · RFP Golden Answers")
    st.caption(
        "Search across categories, questions, and answers using SQLite FTS5. "
        "Supports prefix matching and multi-word queries."
    )

    search_query = st.text_input(
        "Search the library",
        placeholder="e.g. NAV reconciliation, AIFMD reporting, transfer agency...",
        key="rfp_fts_search",
    )

    if search_query:
        results = search_rfp_library(search_query)
        if not results.empty:
            st.success(f"Found {len(results)} matching entries")
            for _, row in results.iterrows():
                with st.expander(
                    f"**[{row.get('category', 'N/A')}]** {row.get('standard_question', '')}",
                    expanded=False,
                ):
                    st.markdown(f"**Answer:** {row.get('golden_answer', '')}")
                    st.caption(f"Library ID: {row.get('id', '')} · Relevance: {row.get('relevance_score', 0):.4f}")
        else:
            st.warning(f"No results for '{search_query}'. Try broader terms or check the Library tab has entries.")
```

# =============================================================================

# MODULE 4 — CLIENT CHANGE & ONBOARDING

# =============================================================================

def render_change_pipeline():
“”“Track onboarding and change request projects with blocker visibility.”””
section_header(“Client Change & Onboarding Pipeline”)

```
df = load_table("change_pipeline")

# Only keep columns that exist (handles migration gracefully)
available_cols = list(df.columns)
edit_cols = [c for c in ["id", "project_name", "type", "stage", "blocker_dept", "blocked_since"]
             if c in available_cols]
df_edit = df[edit_cols].copy() if not df.empty else pd.DataFrame(columns=edit_cols)

st.caption(
    "Set **Blocked Since** to a date when a blocker is assigned. "
    "Days stuck is computed automatically — no manual counting."
)

edited = st.data_editor(
    df_edit,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "project_name": st.column_config.TextColumn("Project"),
        "type": st.column_config.SelectboxColumn(
            "Type", options=["Onboarding", "Change Request"]
        ),
        "stage": st.column_config.TextColumn("Stage"),
        "blocker_dept": st.column_config.SelectboxColumn(
            "Blocker Dept", options=["Legal", "Ops", "Tech", "None"]
        ),
        "blocked_since": st.column_config.DateColumn("Blocked Since"),
    },
    key="editor_changes",
)

if st.button("💾  Commit Changes", key="save_changes"):
    # Auto-clear blocked_since when blocker_dept is set to 'None'
    if not edited.empty and "blocker_dept" in edited.columns and "blocked_since" in edited.columns:
        edited.loc[edited["blocker_dept"] == "None", "blocked_since"] = None
    write_table("change_pipeline", edited)
    st.success("Change pipeline updated.")
    st.rerun()

# --- Computed days_stuck view ---
if not df_edit.empty:
    st.divider()

    # Compute days stuck dynamically from blocked_since
    display_df = df_edit.copy()
    today = date.today()

    def calc_days_stuck(row):
        if pd.isna(row.get("blocked_since")) or row.get("blocker_dept") == "None":
            return 0
        try:
            blocked_dt = pd.to_datetime(row["blocked_since"]).date()
            return (today - blocked_dt).days
        except Exception:
            return 0

    display_df["days_stuck"] = display_df.apply(calc_days_stuck, axis=1)

    col1, col2 = st.columns(2)
    with col1:
        section_header("Blockers by Department")
        blockers = display_df[display_df["blocker_dept"] != "None"]["blocker_dept"].value_counts()
        if not blockers.empty:
            st.bar_chart(blockers, color=THEME["accent_red"])
        else:
            st.info("No active blockers. Pipeline is flowing.")
    with col2:
        section_header("Accountability Timer — Stuck > 5 Days")
        stuck = display_df[display_df["days_stuck"] > 5].sort_values("days_stuck", ascending=False)
        if not stuck.empty:
            st.dataframe(
                stuck[["project_name", "type", "blocker_dept", "blocked_since", "days_stuck"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nothing stuck beyond threshold.")
```

# =============================================================================

# MODULE 5 — RISK & QUALITY

# =============================================================================

def render_risk_quality():
“”“Incidents log and ops friction tracker with colour-coded risk view.”””

```
tab_incidents, tab_friction = st.tabs(["🚨 Incidents Log", "⚙️ Ops Friction"])

# --- Incidents ---
with tab_incidents:
    section_header("Incidents & Near-Miss Register")

    df = load_table("incidents_log")

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "event_date": st.column_config.DateColumn("Date"),
            "type": st.column_config.SelectboxColumn(
                "Type", options=["Error", "Near Miss", "Service Issue"]
            ),
            "impact_level": st.column_config.SelectboxColumn(
                "Impact", options=["Low", "Medium", "High", "Critical"]
            ),
            "root_cause": st.column_config.TextColumn("Root Cause", width="large"),
            "mitigation_status": st.column_config.SelectboxColumn(
                "Status", options=["Open", "In Progress", "Mitigated", "Closed"]
            ),
        },
        key="editor_incidents",
    )

    if st.button("💾  Commit Changes", key="save_incidents"):
        write_table("incidents_log", edited)
        st.success("Incidents log updated.")
        st.rerun()

    # Colour-coded near-miss highlight
    if not df.empty:
        st.divider()
        near_misses = df[df["type"] == "Near Miss"]
        if not near_misses.empty:
            st.warning(
                f"⚠️  **{len(near_misses)} Near Miss(es)** detected — "
                "these are leading indicators of systemic risk. Investigate root causes."
            )
            st.dataframe(
                near_misses[["event_date", "impact_level", "root_cause", "mitigation_status"]],
                use_container_width=True,
                hide_index=True,
            )

        # Impact distribution
        section_header("Impact Distribution")
        impact_counts = df["impact_level"].value_counts()
        st.bar_chart(impact_counts, color=THEME["accent_red"])

# --- Ops Friction ---
with tab_friction:
    section_header("Operational Friction Tracker")
    st.caption(
        "Log manual, repetitive processes and their systemic fix ideas. "
        "This feeds the automation business case."
    )

    df_ops = load_table("ops_friction")

    edited_ops = st.data_editor(
        df_ops,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "process_name": st.column_config.TextColumn("Process"),
            "manual_hours_per_week": st.column_config.NumberColumn(
                "Hrs/Week", min_value=0, format="%.1f"
            ),
            "affected_client": st.column_config.TextColumn("Client(s)"),
            "systemic_fix_idea": st.column_config.TextColumn("Fix Idea", width="large"),
        },
        key="editor_ops_friction",
    )

    if st.button("💾  Commit Changes", key="save_ops_friction"):
        write_table("ops_friction", edited_ops)
        st.success("Ops friction log updated.")
        st.rerun()

    if not df_ops.empty:
        total_hrs = df_ops["manual_hours_per_week"].sum()
        annual_hrs = total_hrs * 52
        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("Total Manual Hours / Week", f"{total_hrs:.1f}h")
        c2.metric("Annualised Waste", f"{annual_hrs:,.0f}h / year")
```

# =============================================================================

# MODULE 6 — LLM EXPORT & REPORTING

# =============================================================================

LLM_PROMPT_PREFIX = (
“You are a Strategic Product CEO in Fund Administration. “
“Analyse the following structured JSON data of my week’s operations “
“and draft a 4-point executive summary highlighting: “
“(1) Innovation opportunities, (2) Risk mitigation priorities, “
“(3) Commercial growth levers, (4) Operational efficiency gains.\n\n”
“DATA:\n”
)

def build_llm_export() -> str:
“””
Query active/open data from every table and produce a compressed
JSON payload prefixed with the LLM analysis prompt.
“””
# Clients leaking
clients = load_table(“client_roster”)
leaking = clients[clients[“margin_status”] == “Leaking”] if not clients.empty else pd.DataFrame()

```
# Open incidents
incidents = load_table("incidents_log")
open_inc = incidents[
    incidents["mitigation_status"].isin(["Open", "In Progress"])
] if not incidents.empty else pd.DataFrame()

# Active changes — enrich with computed days_stuck
changes = load_table("change_pipeline")
active_chg = changes[
    ~changes["stage"].isin(["Complete", "Cancelled"])
] if not changes.empty else pd.DataFrame()
if not active_chg.empty and "blocked_since" in active_chg.columns:
    active_chg = active_chg.copy()
    _today = date.today()
    def _export_stuck(row):
        if pd.isna(row.get("blocked_since")) or row.get("blocker_dept") == "None":
            return 0
        try:
            return (_today - pd.to_datetime(row["blocked_since"]).date()).days
        except Exception:
            return 0
    active_chg["days_stuck"] = active_chg.apply(_export_stuck, axis=1)

# Active RFPs
rfps = load_table("active_rfps")
active_rfps = rfps[
    rfps["status"].isin(["Draft", "In Progress", "Submitted"])
] if not rfps.empty else pd.DataFrame()

# Ops friction
ops = load_table("ops_friction")

# Open action items
actions = load_table("action_items")
open_actions = actions[
    actions["status"].isin(["Open", "In Progress"])
] if not actions.empty else pd.DataFrame()

# Stakeholder landscape summary
stakeholders = load_table("stakeholders")
sh_summary = {}
if not stakeholders.empty and "disposition" in stakeholders.columns:
    sh_summary = stakeholders["disposition"].value_counts().to_dict()

# Recent meetings (last 7 days)
meetings = load_table("meeting_notes")
recent_meetings = pd.DataFrame()
if not meetings.empty:
    meetings_c = meetings.copy()
    meetings_c["date_parsed"] = pd.to_datetime(meetings_c["meeting_date"], errors="coerce")
    week_ago = pd.Timestamp(date.today() - timedelta(days=7))
    recent_meetings = meetings_c[meetings_c["date_parsed"] >= week_ago]

payload = {
    "export_timestamp": datetime.now().isoformat(),
    "leaking_clients": leaking.to_dict(orient="records") if not leaking.empty else [],
    "open_incidents": open_inc.to_dict(orient="records") if not open_inc.empty else [],
    "active_change_requests": active_chg.to_dict(orient="records") if not active_chg.empty else [],
    "active_rfps": active_rfps.to_dict(orient="records") if not active_rfps.empty else [],
    "ops_friction": ops.to_dict(orient="records") if not ops.empty else [],
    "open_action_items": open_actions.to_dict(orient="records") if not open_actions.empty else [],
    "stakeholder_landscape": sh_summary,
    "recent_meetings": recent_meetings[
        ["meeting_date", "meeting_type", "title", "key_decisions", "actions_generated"]
    ].to_dict(orient="records") if not recent_meetings.empty else [],
    "summary_metrics": {
        "leaking_client_count": len(leaking),
        "open_incident_count": len(open_inc),
        "active_change_count": len(active_chg),
        "active_rfp_count": len(active_rfps),
        "total_manual_hours_week": float(ops["manual_hours_per_week"].sum()) if not ops.empty else 0,
        "open_action_count": len(open_actions),
        "total_stakeholders": len(stakeholders),
        "meetings_this_week": len(recent_meetings),
    },
}

json_str = json.dumps(payload, indent=2, default=str)
return LLM_PROMPT_PREFIX + json_str
```

def render_llm_export():
“”“LLM export panel with copy-to-clipboard functionality.”””
section_header(“LLM Brain Export · Copy → Paste → Analyse”)

```
export_text = build_llm_export()

st.text_area(
    "Structured prompt + data payload",
    value=export_text,
    height=420,
    key="llm_export_area",
)

# Copy-to-clipboard via Streamlit's built-in (st.code also has copy)
st.code(export_text, language="json")

st.caption(
    "Copy the text above and paste it into Claude, ChatGPT, or any LLM. "
    "The prompt prefix instructs the model to produce an executive summary."
)
```

# =============================================================================

# MODULE 7 — WEEKLY UPDATE GENERATOR (NATIVE)

# =============================================================================

def render_weekly_update():
“”“Generate a markdown weekly report from live SQL data.”””
section_header(“Weekly Update Generator”)

```
today = date.today()
week_start = today - timedelta(days=today.weekday())

# Pull data
clients = load_table("client_roster")
leaking = clients[clients["margin_status"] == "Leaking"] if not clients.empty else pd.DataFrame()

incidents = load_table("incidents_log")
open_inc = incidents[
    incidents["mitigation_status"].isin(["Open", "In Progress"])
] if not incidents.empty else pd.DataFrame()

changes = load_table("change_pipeline")
active_chg = changes[
    ~changes["stage"].isin(["Complete", "Cancelled"])
] if not changes.empty else pd.DataFrame()
blocked = active_chg[active_chg["blocker_dept"] != "None"] if not active_chg.empty else pd.DataFrame()

# Compute days_stuck dynamically for blocked items
if not blocked.empty and "blocked_since" in blocked.columns:
    blocked = blocked.copy()
    def _wk_stuck(row):
        if pd.isna(row.get("blocked_since")):
            return 0
        try:
            return (today - pd.to_datetime(row["blocked_since"]).date()).days
        except Exception:
            return 0
    blocked["days_stuck"] = blocked.apply(_wk_stuck, axis=1)
elif not blocked.empty:
    blocked = blocked.copy()
    blocked["days_stuck"] = 0

rfps = load_table("active_rfps")
active_rfps = rfps[
    rfps["status"].isin(["Draft", "In Progress", "Submitted"])
] if not rfps.empty else pd.DataFrame()

ops = load_table("ops_friction")
total_manual = ops["manual_hours_per_week"].sum() if not ops.empty else 0

near_misses = incidents[incidents["type"] == "Near Miss"] if not incidents.empty else pd.DataFrame()

# Build markdown
md = f"""# Weekly Product Update — {week_start.strftime('%d %b')} to {today.strftime('%d %b %Y')}
```

-----

## 1. Commercial Health

- **Total Clients**: {len(clients)}
- **Leaking Margin**: {len(leaking)} client(s)
  “””
  if not leaking.empty:
  for _, r in leaking.iterrows():
  md += f”  - {r[‘client_name’]} — {r[‘fee_bps’]} bps, last repriced {r.get(‘last_reprice_date’, ‘N/A’)}\n”
  
  md += f”””

## 2. RFP Pipeline

- **Active RFPs**: {len(active_rfps)}
  “””
  if not active_rfps.empty:
  for _, r in active_rfps.iterrows():
  md += f”  - {r[‘prospect_name’]} — {r[‘status’]} ({r[‘probability’]:.0f}% win probability)\n”
  
  md += f”””

## 3. Change & Onboarding Pipeline

- **Active Projects**: {len(active_chg)}
- **Blocked**: {len(blocked)}
  “””
  if not blocked.empty:
  for _, r in blocked.iterrows():
  md += f”  - {r[‘project_name’]} — blocked by **{r[‘blocker_dept’]}** ({r[‘days_stuck’]} days)\n”
  
  md += f”””

## 4. Risk & Quality

- **Open Incidents**: {len(open_inc)}
- **Near Misses (Leading Indicators)**: {len(near_misses)}
  “””
  if not open_inc.empty:
  for _, r in open_inc.iterrows():
  md += f”  - [{r[‘type’]}] {r.get(‘root_cause’, ‘TBC’)} — {r[‘impact_level’]} impact, {r[‘mitigation_status’]}\n”
  
  md += f”””

## 5. Operational Efficiency

- **Total Manual Hours / Week**: {total_manual:.1f}h ({total_manual * 52:,.0f}h annualised)
  “””
  if not ops.empty:
  top_friction = ops.sort_values(“manual_hours_per_week”, ascending=False).head(3)
  for _, r in top_friction.iterrows():
  md += f”  - {r[‘process_name’]} — {r[‘manual_hours_per_week’]:.1f}h/wk → Fix: {r.get(‘systemic_fix_idea’, ‘TBD’)}\n”
  
  md += “””

-----

*Generated by PM Command Center*
“””

```
st.markdown(md)

st.divider()

# --- Export buttons row ---
col_md, col_docx, col_pptx = st.columns(3)

with col_md:
    st.download_button(
        label="📥 Download Markdown",
        data=md,
        file_name=f"weekly_update_{today.isoformat()}.md",
        mime="text/markdown",
    )

with col_docx:
    if st.button("📄 Generate Word (.docx)", key="gen_docx"):
        with st.spinner("Generating governance pack..."):
            data_payload = _collect_report_data()
            docx_bytes = generate_docx_report(data_payload)
            if docx_bytes:
                st.download_button(
                    label="📥 Download .docx",
                    data=docx_bytes,
                    file_name=f"governance_pack_{today.isoformat()}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_docx",
                )
            else:
                st.error("DOCX generation failed. Check that Node.js and the `docx` package are installed.")

with col_pptx:
    if st.button("📊 Generate PowerPoint (.pptx)", key="gen_pptx"):
        with st.spinner("Generating slide deck..."):
            data_payload = _collect_report_data()
            pptx_bytes = generate_pptx_report(data_payload)
            if pptx_bytes:
                st.download_button(
                    label="📥 Download .pptx",
                    data=pptx_bytes,
                    file_name=f"weekly_deck_{today.isoformat()}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="download_pptx",
                )
            else:
                st.error("PPTX generation failed. Check that Node.js and `pptxgenjs` are installed.")
```

def _collect_report_data() -> dict:
“”“Collect all data needed for Word/PowerPoint reports into a single dict.”””
today = date.today()
week_start = today - timedelta(days=today.weekday())

```
clients = load_table("client_roster")
leaking = clients[clients["margin_status"] == "Leaking"] if not clients.empty else pd.DataFrame()

incidents = load_table("incidents_log")
open_inc = incidents[
    incidents["mitigation_status"].isin(["Open", "In Progress"])
] if not incidents.empty else pd.DataFrame()
near_misses = incidents[incidents["type"] == "Near Miss"] if not incidents.empty else pd.DataFrame()

changes = load_table("change_pipeline")
active_chg = changes[
    ~changes["stage"].isin(["Complete", "Cancelled"])
] if not changes.empty else pd.DataFrame()
blocked = active_chg[active_chg["blocker_dept"] != "None"] if not active_chg.empty else pd.DataFrame()
if not blocked.empty and "blocked_since" in blocked.columns:
    blocked = blocked.copy()
    def _ds(row):
        if pd.isna(row.get("blocked_since")):
            return 0
        try:
            return (today - pd.to_datetime(row["blocked_since"]).date()).days
        except Exception:
            return 0
    blocked["days_stuck"] = blocked.apply(_ds, axis=1)
elif not blocked.empty:
    blocked = blocked.copy()
    blocked["days_stuck"] = 0

rfps = load_table("active_rfps")
active_rfps = rfps[
    rfps["status"].isin(["Draft", "In Progress", "Submitted"])
] if not rfps.empty else pd.DataFrame()

ops = load_table("ops_friction")
total_manual = float(ops["manual_hours_per_week"].sum()) if not ops.empty else 0.0

return {
    "today": today.isoformat(),
    "week_start": week_start.strftime("%d %b"),
    "week_end": today.strftime("%d %b %Y"),
    "total_clients": len(clients),
    "leaking": leaking.to_dict(orient="records") if not leaking.empty else [],
    "leaking_count": len(leaking),
    "open_incidents": open_inc.to_dict(orient="records") if not open_inc.empty else [],
    "open_incident_count": len(open_inc),
    "near_miss_count": len(near_misses),
    "active_changes": len(active_chg),
    "blocked": blocked.to_dict(orient="records") if not blocked.empty else [],
    "blocked_count": len(blocked),
    "active_rfps": active_rfps.to_dict(orient="records") if not active_rfps.empty else [],
    "active_rfp_count": len(active_rfps),
    "total_manual_hours": total_manual,
    "annualised_hours": total_manual * 52,
    "top_friction": (
        ops.sort_values("manual_hours_per_week", ascending=False)
        .head(3)
        .to_dict(orient="records")
        if not ops.empty else []
    ),
}
```

# =============================================================================

# DOCUMENT GENERATION — Word (.docx) via Node.js docx library

# =============================================================================

def generate_docx_report(data: dict) -> bytes | None:
“””
Generate a professional governance pack Word document using the docx npm library.
Returns raw bytes of the .docx file, or None on failure.
“””
data_json = json.dumps(data, default=str)

```
js_code = textwrap.dedent(r"""
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
        LevelFormat, PageBreak } = require("docx");

const data = JSON.parse(fs.readFileSync("/dev/stdin", "utf8"));
const today = data.today;

// --- Colour palette ---
const NAVY = "0A0E17";
const CYAN = "06B6D4";
const RED  = "EF4444";
const GREEN = "10B981";
const GRAY  = "94A3B8";
const LIGHT = "F1F5F9";
const WHITE = "FFFFFF";

const border = { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

// --- Helper: metric row ---
function metricRow(label, value) {
    return new TableRow({
        children: [
            new TableCell({
                borders, width: { size: 4680, type: WidthType.DXA },
                margins: cellMargins,
                children: [new Paragraph({ children: [new TextRun({ text: label, font: "Calibri", size: 22, color: GRAY })] })]
            }),
            new TableCell({
                borders, width: { size: 4680, type: WidthType.DXA },
                margins: cellMargins,
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({ text: String(value), font: "Calibri", size: 24, bold: true, color: NAVY })]
                })]
            }),
        ]
    });
}

// --- Helper: detail bullet ---
function detailLine(text) {
    return new Paragraph({
        spacing: { before: 60, after: 60 },
        children: [new TextRun({ text: "  \u2022  " + text, font: "Calibri", size: 20, color: "334155" })]
    });
}

// --- Build sections ---
const children = [];

// Title
children.push(new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text: "WEEKLY GOVERNANCE PACK", font: "Calibri", size: 36, bold: true, color: NAVY })]
}));
children.push(new Paragraph({
    spacing: { after: 400 },
    children: [new TextRun({ text: `${data.week_start} \u2013 ${data.week_end}`, font: "Calibri", size: 24, color: GRAY })]
}));

// KPI Table
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Executive Summary", font: "Calibri" })] }));
children.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [4680, 4680],
    rows: [
        metricRow("Total Clients", data.total_clients),
        metricRow("Clients Leaking Margin", data.leaking_count),
        metricRow("Open Incidents", data.open_incident_count),
        metricRow("Near Misses (Leading)", data.near_miss_count),
        metricRow("Active Change Requests", data.active_changes),
        metricRow("Blocked Projects", data.blocked_count),
        metricRow("Active RFPs", data.active_rfp_count),
        metricRow("Manual Hours / Week", data.total_manual_hours.toFixed(1) + "h"),
        metricRow("Annualised Waste", data.annualised_hours.toFixed(0) + "h"),
    ]
}));
children.push(new Paragraph({ spacing: { before: 200 }, children: [] }));

// Leaking Clients
if (data.leaking.length > 0) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Clients Leaking Margin", font: "Calibri" })] }));
    const headerRow = new TableRow({
        children: ["Client", "Fee (bps)", "Manual Tasks", "Last Reprice"].map(h =>
            new TableCell({
                borders, width: { size: 2340, type: WidthType.DXA },
                margins: cellMargins,
                shading: { fill: NAVY, type: ShadingType.CLEAR },
                children: [new Paragraph({ children: [new TextRun({ text: h, font: "Calibri", size: 20, bold: true, color: WHITE })] })]
            })
        )
    });
    const dataRows = data.leaking.map(c => new TableRow({
        children: [
            c.client_name || "",
            String(c.fee_bps || 0),
            String(c.manual_tasks || 0),
            c.last_reprice_date || "N/A"
        ].map(v => new TableCell({
            borders, width: { size: 2340, type: WidthType.DXA },
            margins: cellMargins,
            children: [new Paragraph({ children: [new TextRun({ text: v, font: "Calibri", size: 20, color: "334155" })] })]
        }))
    }));
    children.push(new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [2340, 2340, 2340, 2340], rows: [headerRow, ...dataRows] }));
    children.push(new Paragraph({ spacing: { before: 200 }, children: [] }));
}

// RFP Pipeline
if (data.active_rfps.length > 0) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Active RFP Pipeline", font: "Calibri" })] }));
    data.active_rfps.forEach(r => {
        children.push(detailLine(`${r.prospect_name || "TBC"} \u2014 ${r.status} (${(r.probability || 0).toFixed(0)}% win)`));
    });
    children.push(new Paragraph({ spacing: { before: 200 }, children: [] }));
}

// Blocked Projects
if (data.blocked.length > 0) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Blocked Projects \u2014 Escalation Required", font: "Calibri" })] }));
    data.blocked.forEach(b => {
        children.push(detailLine(`${b.project_name} \u2014 blocked by ${b.blocker_dept} (${b.days_stuck || 0} days)`));
    });
    children.push(new Paragraph({ spacing: { before: 200 }, children: [] }));
}

// Open Incidents
if (data.open_incidents.length > 0) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Open Incidents", font: "Calibri" })] }));
    data.open_incidents.forEach(i => {
        children.push(detailLine(`[${i.type}] ${i.root_cause || "TBC"} \u2014 ${i.impact_level} impact, ${i.mitigation_status}`));
    });
    children.push(new Paragraph({ spacing: { before: 200 }, children: [] }));
}

// Ops Friction
if (data.top_friction.length > 0) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: "Top Operational Friction Points", font: "Calibri" })] }));
    data.top_friction.forEach(f => {
        children.push(detailLine(`${f.process_name} \u2014 ${(f.manual_hours_per_week || 0).toFixed(1)}h/wk \u2192 ${f.systemic_fix_idea || "TBD"}`));
    });
}

// Footer
children.push(new Paragraph({ spacing: { before: 600 }, children: [
    new TextRun({ text: "Generated by PM Command Center \u00B7 " + today, font: "Calibri", size: 18, italics: true, color: GRAY })
] }));

const doc = new Document({
    styles: {
        default: { document: { run: { font: "Calibri", size: 24 } } },
        paragraphStyles: [
            { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 30, bold: true, font: "Calibri", color: NAVY },
              paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
        ]
    },
    sections: [{
        properties: {
            page: {
                size: { width: 12240, height: 15840 },
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        children
    }]
});

Packer.toBuffer(doc).then(buf => {
    fs.writeFileSync(process.argv[2], buf);
});
""")

try:
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as js_f:
        js_f.write(js_code)
        js_path = js_f.name

    out_path = tempfile.mktemp(suffix=".docx")

    result = subprocess.run(
        ["node", js_path, out_path],
        input=data_json, capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        st.error(f"DOCX generation error: {result.stderr[:500]}")
        return None

    with open(out_path, "rb") as f:
        return f.read()
except Exception as e:
    st.error(f"DOCX generation failed: {e}")
    return None
finally:
    for p in [js_path, out_path]:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass
```

# =============================================================================

# DOCUMENT GENERATION — PowerPoint (.pptx) via pptxgenjs

# =============================================================================

def generate_pptx_report(data: dict) -> bytes | None:
“””
Generate a governance deck using pptxgenjs.
Returns raw bytes of the .pptx file, or None on failure.
“””
data_json = json.dumps(data, default=str)

```
js_code = textwrap.dedent(r"""
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const data = JSON.parse(fs.readFileSync("/dev/stdin", "utf8"));

const NAVY   = "0A0E17";
const CYAN   = "06B6D4";
const DARK   = "111827";
const GRAY   = "94A3B8";
const WHITE   = "FFFFFF";
const RED    = "EF4444";
const GREEN  = "10B981";
const AMBER  = "F59E0B";
const LIGHT  = "1E293B";

let pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "PM Command Center";
pres.title = `Weekly Governance Pack - ${data.week_end}`;

// =========== SLIDE 1: TITLE ===========
let s1 = pres.addSlide();
s1.background = { color: NAVY };
s1.addText("WEEKLY GOVERNANCE PACK", {
    x: 0.8, y: 1.5, w: 8.4, h: 1.2,
    fontSize: 36, fontFace: "Calibri", color: WHITE, bold: true, charSpacing: 4
});
s1.addText(`${data.week_start} \u2013 ${data.week_end}`, {
    x: 0.8, y: 2.7, w: 8.4, h: 0.6,
    fontSize: 18, fontFace: "Calibri", color: CYAN
});
s1.addText("Fund Administration Operations Intelligence", {
    x: 0.8, y: 3.5, w: 8.4, h: 0.5,
    fontSize: 14, fontFace: "Calibri", color: GRAY, italic: true
});
s1.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 4.3, w: 2, h: 0.04, fill: { color: CYAN }
});

// =========== SLIDE 2: KPI DASHBOARD ===========
let s2 = pres.addSlide();
s2.background = { color: DARK };
s2.addText("Executive Dashboard", {
    x: 0.5, y: 0.3, w: 9, h: 0.6, fontSize: 24, fontFace: "Calibri", color: WHITE, bold: true, margin: 0
});

const metrics = [
    { label: "Leaking Clients", value: String(data.leaking_count), color: data.leaking_count > 0 ? RED : GREEN },
    { label: "Open Incidents", value: String(data.open_incident_count), color: data.open_incident_count > 0 ? AMBER : GREEN },
    { label: "Near Misses", value: String(data.near_miss_count), color: data.near_miss_count > 0 ? AMBER : GREEN },
    { label: "Active Changes", value: String(data.active_changes), color: CYAN },
    { label: "Blocked", value: String(data.blocked_count), color: data.blocked_count > 0 ? RED : GREEN },
    { label: "Active RFPs", value: String(data.active_rfp_count), color: CYAN },
    { label: "Manual Hrs/Wk", value: data.total_manual_hours.toFixed(1) + "h", color: AMBER },
    { label: "Annual Waste", value: data.annualised_hours.toFixed(0) + "h", color: RED },
];

metrics.forEach((m, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = 0.5 + col * 2.35;
    const y = 1.2 + row * 2.0;
    s2.addShape(pres.shapes.RECTANGLE, {
        x, y, w: 2.1, h: 1.7,
        fill: { color: LIGHT },
        shadow: { type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.2 }
    });
    s2.addText(m.value, {
        x, y: y + 0.2, w: 2.1, h: 0.9,
        fontSize: 32, fontFace: "Calibri", color: m.color, bold: true, align: "center", valign: "middle"
    });
    s2.addText(m.label.toUpperCase(), {
        x, y: y + 1.1, w: 2.1, h: 0.4,
        fontSize: 10, fontFace: "Calibri", color: GRAY, align: "center", charSpacing: 2
    });
});

// =========== SLIDE 3: LEAKING CLIENTS ===========
if (data.leaking.length > 0) {
    let s3 = pres.addSlide();
    s3.background = { color: DARK };
    s3.addText("Clients Leaking Margin", {
        x: 0.5, y: 0.3, w: 9, h: 0.6, fontSize: 24, fontFace: "Calibri", color: RED, bold: true, margin: 0
    });

    const tableData = [
        [
            { text: "Client", options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12, fontFace: "Calibri" } },
            { text: "Fee (bps)", options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12, fontFace: "Calibri" } },
            { text: "Manual Tasks", options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12, fontFace: "Calibri" } },
            { text: "Last Reprice", options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12, fontFace: "Calibri" } },
        ],
        ...data.leaking.map(c => [
            { text: c.client_name || "", options: { fontSize: 11, fontFace: "Calibri", color: WHITE } },
            { text: String(c.fee_bps || 0), options: { fontSize: 11, fontFace: "Calibri", color: WHITE } },
            { text: String(c.manual_tasks || 0), options: { fontSize: 11, fontFace: "Calibri", color: WHITE } },
            { text: c.last_reprice_date || "N/A", options: { fontSize: 11, fontFace: "Calibri", color: WHITE } },
        ])
    ];
    s3.addTable(tableData, {
        x: 0.5, y: 1.2, w: 9, colW: [3, 2, 2, 2],
        border: { pt: 0.5, color: LIGHT },
        fill: { color: DARK },
        rowH: [0.4, ...data.leaking.map(() => 0.35)]
    });
}

// =========== SLIDE 4: BLOCKERS & RFPS ===========
let s4 = pres.addSlide();
s4.background = { color: DARK };
s4.addText("Pipeline & Blockers", {
    x: 0.5, y: 0.3, w: 9, h: 0.6, fontSize: 24, fontFace: "Calibri", color: WHITE, bold: true, margin: 0
});

// Left column: blocked projects
s4.addText("BLOCKED PROJECTS", {
    x: 0.5, y: 1.1, w: 4.5, h: 0.4, fontSize: 12, fontFace: "Calibri", color: RED, bold: true, charSpacing: 2
});
if (data.blocked.length > 0) {
    const blockedLines = data.blocked.map(b =>
        ({ text: `${b.project_name} \u2014 ${b.blocker_dept} (${b.days_stuck || 0}d)`, options: { bullet: true, breakLine: true, fontSize: 12, fontFace: "Calibri", color: WHITE } })
    );
    s4.addText(blockedLines, { x: 0.5, y: 1.6, w: 4.3, h: 3.5 });
} else {
    s4.addText("No active blockers", { x: 0.5, y: 1.6, w: 4.3, h: 0.4, fontSize: 12, fontFace: "Calibri", color: GREEN, italic: true });
}

// Right column: active RFPs
s4.addText("ACTIVE RFPS", {
    x: 5.2, y: 1.1, w: 4.5, h: 0.4, fontSize: 12, fontFace: "Calibri", color: CYAN, bold: true, charSpacing: 2
});
if (data.active_rfps.length > 0) {
    const rfpLines = data.active_rfps.map(r =>
        ({ text: `${r.prospect_name || "TBC"} \u2014 ${r.status} (${(r.probability || 0).toFixed(0)}%)`, options: { bullet: true, breakLine: true, fontSize: 12, fontFace: "Calibri", color: WHITE } })
    );
    s4.addText(rfpLines, { x: 5.2, y: 1.6, w: 4.3, h: 3.5 });
} else {
    s4.addText("No active RFPs", { x: 5.2, y: 1.6, w: 4.3, h: 0.4, fontSize: 12, fontFace: "Calibri", color: GRAY, italic: true });
}

// =========== SLIDE 5: OPS FRICTION ===========
if (data.top_friction.length > 0) {
    let s5 = pres.addSlide();
    s5.background = { color: DARK };
    s5.addText("Operational Friction", {
        x: 0.5, y: 0.3, w: 9, h: 0.6, fontSize: 24, fontFace: "Calibri", color: AMBER, bold: true, margin: 0
    });

    // Big stat callouts
    s5.addText(data.total_manual_hours.toFixed(1) + "h", {
        x: 0.5, y: 1.1, w: 3, h: 1.2, fontSize: 48, fontFace: "Calibri", color: AMBER, bold: true, align: "center"
    });
    s5.addText("MANUAL HRS / WEEK", {
        x: 0.5, y: 2.2, w: 3, h: 0.4, fontSize: 10, fontFace: "Calibri", color: GRAY, align: "center", charSpacing: 2
    });
    s5.addText(data.annualised_hours.toFixed(0) + "h", {
        x: 3.5, y: 1.1, w: 3, h: 1.2, fontSize: 48, fontFace: "Calibri", color: RED, bold: true, align: "center"
    });
    s5.addText("ANNUALISED WASTE", {
        x: 3.5, y: 2.2, w: 3, h: 0.4, fontSize: 10, fontFace: "Calibri", color: GRAY, align: "center", charSpacing: 2
    });

    // Top friction items
    const frictionLines = data.top_friction.map(f =>
        ({ text: `${f.process_name} \u2014 ${(f.manual_hours_per_week || 0).toFixed(1)}h/wk \u2192 ${f.systemic_fix_idea || "TBD"}`, options: { bullet: true, breakLine: true, fontSize: 12, fontFace: "Calibri", color: WHITE } })
    );
    s5.addText(frictionLines, { x: 0.5, y: 3.0, w: 9, h: 2.2 });
}

// =========== FINAL SLIDE ===========
let sEnd = pres.addSlide();
sEnd.background = { color: NAVY };
sEnd.addText("END OF REPORT", {
    x: 0.5, y: 2.0, w: 9, h: 1, fontSize: 28, fontFace: "Calibri", color: CYAN, bold: true, align: "center", charSpacing: 6
});
sEnd.addText(`Generated ${data.today} \u00B7 PM Command Center`, {
    x: 0.5, y: 3.2, w: 9, h: 0.5, fontSize: 12, fontFace: "Calibri", color: GRAY, align: "center"
});

pres.writeFile({ fileName: process.argv[2] });
""")

try:
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as js_f:
        js_f.write(js_code)
        js_path = js_f.name

    out_path = tempfile.mktemp(suffix=".pptx")

    result = subprocess.run(
        ["node", js_path, out_path],
        input=data_json, capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        st.error(f"PPTX generation error: {result.stderr[:500]}")
        return None

    with open(out_path, "rb") as f:
        return f.read()
except Exception as e:
    st.error(f"PPTX generation failed: {e}")
    return None
finally:
    for p in [js_path, out_path]:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass
```

# =============================================================================

# MODULE 9 — DAILY STANDUP VIEW

# =============================================================================

def render_daily_standup():
“””
Single-screen morning briefing: what needs attention TODAY.
No clicks required — everything surfaces automatically.
“””
section_header(“Daily Standup · Morning Briefing”)

```
today = date.today()
today_iso = today.isoformat()
week_end = (today + timedelta(days=(4 - today.weekday()) % 7)).isoformat()  # Friday

# ---- Action items due today or overdue ----
actions = load_table("action_items")
if not actions.empty:
    actions_open = actions[actions["status"].isin(["Open", "In Progress"])].copy()
    if not actions_open.empty and "due_date" in actions_open.columns:
        actions_open["due_date_parsed"] = pd.to_datetime(actions_open["due_date"], errors="coerce")
        overdue = actions_open[actions_open["due_date_parsed"] < pd.Timestamp(today)]
        due_today = actions_open[actions_open["due_date_parsed"] == pd.Timestamp(today)]
        due_this_week = actions_open[
            (actions_open["due_date_parsed"] > pd.Timestamp(today))
            & (actions_open["due_date_parsed"] <= pd.Timestamp(week_end))
        ]
    else:
        overdue = due_today = due_this_week = pd.DataFrame()
else:
    overdue = due_today = due_this_week = pd.DataFrame()
    actions_open = pd.DataFrame()

# ---- Incidents opened in last 24h ----
incidents = load_table("incidents_log")
if not incidents.empty:
    incidents["event_date_parsed"] = pd.to_datetime(incidents["event_date"], errors="coerce")
    yesterday = pd.Timestamp(today - timedelta(days=1))
    recent_incidents = incidents[
        (incidents["event_date_parsed"] >= yesterday)
        & (incidents["mitigation_status"].isin(["Open", "In Progress"]))
    ]
else:
    recent_incidents = pd.DataFrame()

# ---- Blocker accountability: newly crossed thresholds ----
changes = load_table("change_pipeline")
stuck_items = pd.DataFrame()
if not changes.empty and "blocked_since" in changes.columns:
    changes_c = changes.copy()
    def _stuck_days(row):
        if pd.isna(row.get("blocked_since")) or row.get("blocker_dept") == "None":
            return 0
        try:
            return (today - pd.to_datetime(row["blocked_since"]).date()).days
        except Exception:
            return 0
    changes_c["days_stuck"] = changes_c.apply(_stuck_days, axis=1)
    stuck_items = changes_c[changes_c["days_stuck"] > 5].sort_values("days_stuck", ascending=False)

# ---- RFPs due this week ----
rfps = load_table("active_rfps")
urgent_rfps = pd.DataFrame()
if not rfps.empty:
    rfps_c = rfps[rfps["status"].isin(["Draft", "In Progress", "Submitted"])].copy()
    if not rfps_c.empty:
        rfps_c["due_parsed"] = pd.to_datetime(rfps_c["due_date"], errors="coerce")
        urgent_rfps = rfps_c[rfps_c["due_parsed"] <= pd.Timestamp(week_end)]

# ---- Stakeholder interactions going cold (> 14 days) ----
stakeholders = load_table("stakeholders")
cold_stakeholders = pd.DataFrame()
if not stakeholders.empty and "last_interaction_date" in stakeholders.columns:
    stakeholders_c = stakeholders.copy()
    stakeholders_c["last_parsed"] = pd.to_datetime(stakeholders_c["last_interaction_date"], errors="coerce")
    cold_stakeholders = stakeholders_c[
        (stakeholders_c["last_parsed"] < pd.Timestamp(today - timedelta(days=14)))
        & (stakeholders_c["disposition"].isin(["Sponsor", "Advocate", "Key Decision Maker"]))
    ] if "disposition" in stakeholders_c.columns else pd.DataFrame()

# ---- Meetings today (from meeting_notes, looking at future-dated entries) ----
meetings = load_table("meeting_notes")
todays_meetings = pd.DataFrame()
if not meetings.empty:
    todays_meetings = meetings[meetings["meeting_date"] == today_iso]

# =========== RENDER ===========

# KPI alert bar
alert_count = len(overdue) + len(recent_incidents) + len(stuck_items)
if alert_count > 0:
    st.error(f"🔴  **{alert_count} items need attention today** — overdue actions, recent incidents, or stuck projects.")
else:
    st.success("🟢  Clean slate — no escalations, no overdue items. Good day to push strategic work forward.")

st.divider()

# ---- Two-column layout ----
col_left, col_right = st.columns(2)

with col_left:
    # Overdue actions
    section_header("🔴 Overdue Actions")
    if not overdue.empty:
        for _, r in overdue.iterrows():
            st.markdown(
                f"**{r.get('task', '')}** · Owner: {r.get('owner', 'Unassigned')} · "
                f"Due: {r.get('due_date', '?')} · Priority: {r.get('priority', 'Medium')}"
            )
    else:
        st.info("Nothing overdue.")

    # Due today
    section_header("🟡 Due Today")
    if not due_today.empty:
        for _, r in due_today.iterrows():
            st.markdown(
                f"**{r.get('task', '')}** · Owner: {r.get('owner', 'Unassigned')} · "
                f"Priority: {r.get('priority', 'Medium')}"
            )
    else:
        st.info("No actions due today.")

    # Due this week
    section_header("📅 Due This Week")
    if not due_this_week.empty:
        for _, r in due_this_week.iterrows():
            st.markdown(
                f"**{r.get('task', '')}** · {r.get('owner', 'Unassigned')} · "
                f"Due: {r.get('due_date', '?')}"
            )
    else:
        st.info("No further actions due this week.")

with col_right:
    # Recent incidents
    section_header("🚨 Incidents (Last 24h)")
    if not recent_incidents.empty:
        for _, r in recent_incidents.iterrows():
            st.markdown(
                f"**[{r.get('type', '')}]** {r.get('root_cause', 'TBC')} · "
                f"{r.get('impact_level', '?')} impact · {r.get('mitigation_status', '?')}"
            )
    else:
        st.info("No recent incidents. Quiet night.")

    # Stuck projects
    section_header("⏰ Stuck Projects (> 5 Days)")
    if not stuck_items.empty:
        for _, r in stuck_items.iterrows():
            st.markdown(
                f"**{r.get('project_name', '')}** · Blocked by **{r.get('blocker_dept', '?')}** · "
                f"{r.get('days_stuck', 0)} days"
            )
    else:
        st.info("No projects stuck beyond threshold.")

    # Urgent RFPs
    section_header("📋 RFPs Due This Week")
    if not urgent_rfps.empty:
        for _, r in urgent_rfps.iterrows():
            st.markdown(
                f"**{r.get('prospect_name', '')}** · Due: {r.get('due_date', '?')} · "
                f"{r.get('status', '?')} ({r.get('probability', 0):.0f}%)"
            )
    else:
        st.info("No RFPs due this week.")

st.divider()

# Bottom row: relationship maintenance + today's meetings
col_b1, col_b2 = st.columns(2)

with col_b1:
    section_header("🧊 Relationships Going Cold (> 14 Days)")
    if not cold_stakeholders.empty:
        for _, r in cold_stakeholders.iterrows():
            days_cold = (today - r["last_parsed"].date()).days if pd.notna(r.get("last_parsed")) else "?"
            st.markdown(
                f"**{r.get('name', '')}** ({r.get('role', '')}, {r.get('department', '')}) · "
                f"Last contact: {days_cold} days ago · "
                f"Disposition: {r.get('disposition', '?')}"
            )
    else:
        st.info("No key relationships going cold.")

with col_b2:
    section_header("📆 Today's Meetings")
    if not todays_meetings.empty:
        for _, r in todays_meetings.iterrows():
            st.markdown(
                f"**{r.get('title', '')}** · {r.get('meeting_type', '')} · "
                f"Attendees: {r.get('attendees', 'TBC')}"
            )
    else:
        st.info("No meetings logged for today.")
```

# =============================================================================

# MODULE 10 — ACTION ITEMS

# =============================================================================

def update_action_status(action_id: int, new_status: str):
“””
Single-row status update for Kanban card moves.
Audit-aware: logs the specific status transition without full-table rewrite.
“””
conn = get_connection()
try:
cur = conn.cursor()
# Fetch current row for audit diff
cur.execute(“SELECT task, status FROM action_items WHERE id = ?”, (action_id,))
row = cur.fetchone()
if row is None:
return
task_label, old_status = row

```
    if old_status == new_status:
        return  # no-op

    # Update
    cur.execute(
        "UPDATE action_items SET status = ? WHERE id = ?",
        (new_status, action_id),
    )

    # Audit log entry
    cur.execute(
        "INSERT INTO audit_log (timestamp, table_name, action, record_summary, field_changes) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(),
            "action_items",
            "UPDATE",
            f"action_items → {task_label}",
            f"status: '{old_status}' → '{new_status}'",
        ),
    )
    conn.commit()
finally:
    conn.close()
```

def quick_add_action(task: str, owner: str, due_date: str, priority: str, source: str):
“”“Single-row insert for the Kanban quick-add form. Audit-aware.”””
conn = get_connection()
try:
cur = conn.cursor()
cur.execute(
“INSERT INTO action_items “
“(task, owner, due_date, priority, source, status, created_date) “
“VALUES (?, ?, ?, ?, ?, ‘Open’, ?)”,
(task, owner, due_date, priority, source, date.today().isoformat()),
)
cur.execute(
“INSERT INTO audit_log (timestamp, table_name, action, record_summary, field_changes) “
“VALUES (?, ?, ?, ?, ?)”,
(
datetime.now().isoformat(),
“action_items”,
“INSERT”,
f”action_items → {task}”,
“”,
),
)
conn.commit()
finally:
conn.close()

def _priority_indicator(priority: str) -> str:
“”“Return a subtle indicator string for priority level.”””
return {
“Critical”: “●●●●”,
“High”: “●●●○”,
“Medium”: “●●○○”,
“Low”: “●○○○”,
}.get(priority, “○○○○”)

def _render_kanban_card(row: pd.Series, today: date):
“”“Render a single Kanban card with action buttons to move between columns.”””
task = row.get(“task”, “”)
task_id = int(row[“id”])
owner = row.get(“owner”, “—”) or “—”
due = row.get(“due_date”, “”)
priority = row.get(“priority”, “Medium”) or “Medium”
status = row.get(“status”, “Open”)
source = row.get(“source”, “”) or “”
linked_table = row.get(“linked_table”, “”) or “”
linked_record = row.get(“linked_record”, “”) or “”

```
# Overdue check
is_overdue = False
days_to_due = None
if due:
    try:
        due_date_obj = pd.to_datetime(due).date()
        days_to_due = (due_date_obj - today).days
        is_overdue = days_to_due < 0 and status != "Done"
    except Exception:
        pass

# Border colour based on urgency (signal only, no decoration)
if is_overdue:
    border_color = THEME["signal_risk"]
elif days_to_due is not None and days_to_due == 0:
    border_color = THEME["signal_warn"]
elif priority == "Critical":
    border_color = THEME["signal_warn"]
else:
    border_color = THEME["border"]

# Due date display
if due:
    if is_overdue:
        due_display = f"⚠ {due} ({abs(days_to_due)}d overdue)"
    elif days_to_due == 0:
        due_display = f"▶ Due today"
    elif days_to_due is not None and days_to_due <= 7:
        due_display = f"{due} (in {days_to_due}d)"
    else:
        due_display = due
else:
    due_display = "No due date"

# Card body
linked_str = f"{linked_table} · {linked_record}" if linked_table else ""

card_html = f"""
<div style="
    background: {THEME['bg_card']};
    border: 1px solid {THEME['border']};
    border-left: 3px solid {border_color};
    border-radius: 4px;
    padding: 10px 12px;
    margin-bottom: 8px;
    font-size: 0.85rem;
">
    <div style="font-weight: 500; color: {THEME['text_primary']}; margin-bottom: 6px;">
        {task}
    </div>
    <div style="color: {THEME['text_secondary']}; font-size: 0.78rem; margin-bottom: 4px;">
        <strong>{owner}</strong> · <span style="font-family: 'JetBrains Mono', monospace;">{_priority_indicator(priority)}</span> {priority}
    </div>
    <div style="color: {THEME['text_muted']}; font-size: 0.76rem; margin-bottom: 2px;">
        {due_display}
    </div>
    {f'<div style="color: {THEME["text_muted"]}; font-size: 0.72rem; font-style: italic;">↳ {linked_str}</div>' if linked_str else ''}
    {f'<div style="color: {THEME["text_muted"]}; font-size: 0.72rem;">from: {source}</div>' if source else ''}
</div>
"""
st.markdown(card_html, unsafe_allow_html=True)

# Move buttons — compact row beneath each card
status_options = ["Open", "In Progress", "Done", "Cancelled"]
other_statuses = [s for s in status_options if s != status]

# Render up to 3 move buttons (skip current status)
cols = st.columns(len(other_statuses))
for i, new_status in enumerate(other_statuses):
    label = {
        "Open": "⟵ Open",
        "In Progress": "▶ Start" if status == "Open" else "⟵ Progress",
        "Done": "✓ Done",
        "Cancelled": "✕ Cancel",
    }.get(new_status, new_status)

    # Shorten for compact display
    if new_status == "In Progress":
        label = "▶ Progress"

    with cols[i]:
        if st.button(label, key=f"move_{task_id}_{new_status}", use_container_width=True):
            update_action_status(task_id, new_status)
            st.rerun()
```

def render_action_items():
“”“Task-level tracking with Kanban board + bulk editor fallback.”””
section_header(“Action Items · Task Tracker”)

```
tab_kanban, tab_editor, tab_all = st.tabs(
    ["📋 Kanban Board", "✏️ Bulk Editor", "🗄️ Archive"]
)

df = load_table("action_items")
today = date.today()

# =========== KANBAN BOARD ===========
with tab_kanban:
    st.caption(
        "Drag work through the stages by clicking the status buttons on each card. "
        "Red border = overdue · Amber border = due today or critical priority."
    )

    # --- Quick add bar ---
    with st.expander("➕ Quick Add Action", expanded=False):
        qa_cols = st.columns([3, 1, 1, 1])
        with qa_cols[0]:
            qa_task = st.text_input("Task", key="qa_action_task", placeholder="What needs doing?")
        with qa_cols[1]:
            qa_owner = st.text_input("Owner", key="qa_action_owner", value="PB")
        with qa_cols[2]:
            qa_due = st.date_input("Due", key="qa_action_due", value=today + timedelta(days=3))
        with qa_cols[3]:
            qa_priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"],
                                       index=1, key="qa_action_priority")

        qa_source = st.text_input("Source", key="qa_action_source",
                                  placeholder="e.g. Governance Meeting, Client Call, Ad Hoc")

        if st.button("Add to Board", key="qa_action_add"):
            if qa_task.strip():
                quick_add_action(qa_task.strip(), qa_owner, qa_due.isoformat(),
                                 qa_priority, qa_source or "Ad Hoc")
                st.success(f"Added: {qa_task}")
                st.rerun()
            else:
                st.warning("Task description required.")

    # --- Filters ---
    filter_cols = st.columns([1, 1, 1, 1])
    with filter_cols[0]:
        owners = ["All"] + sorted(df["owner"].dropna().unique().tolist()) if not df.empty else ["All"]
        filter_owner = st.selectbox("Owner", owners, key="kanban_filter_owner")
    with filter_cols[1]:
        priorities = ["All", "Critical", "High", "Medium", "Low"]
        filter_priority = st.selectbox("Priority", priorities, key="kanban_filter_priority")
    with filter_cols[2]:
        sources = ["All"] + sorted(df["source"].dropna().unique().tolist()) if not df.empty else ["All"]
        filter_source = st.selectbox("Source", sources, key="kanban_filter_source")
    with filter_cols[3]:
        filter_overdue = st.checkbox("Overdue only", key="kanban_filter_overdue")

    # Apply filters
    board_df = df.copy() if not df.empty else df
    if not board_df.empty:
        if filter_owner != "All":
            board_df = board_df[board_df["owner"] == filter_owner]
        if filter_priority != "All":
            board_df = board_df[board_df["priority"] == filter_priority]
        if filter_source != "All":
            board_df = board_df[board_df["source"] == filter_source]
        if filter_overdue and "due_date" in board_df.columns:
            board_df = board_df.copy()
            board_df["_due_parsed"] = pd.to_datetime(board_df["due_date"], errors="coerce")
            board_df = board_df[
                (board_df["_due_parsed"] < pd.Timestamp(today))
                & (board_df["status"].isin(["Open", "In Progress"]))
            ]

    st.divider()

    # --- Three columns: Open / In Progress / Done ---
    col_open, col_progress, col_done = st.columns(3)

    # Helper for sorting: overdue first, then by due date, then by priority
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

    def _sort_key(sub):
        if sub.empty:
            return sub
        sub = sub.copy()
        sub["_due_parsed"] = pd.to_datetime(sub["due_date"], errors="coerce")
        sub["_priority_order"] = sub["priority"].map(priority_order).fillna(4)
        sub = sub.sort_values(["_due_parsed", "_priority_order"], na_position="last")
        return sub

    # OPEN column
    with col_open:
        open_df = board_df[board_df["status"] == "Open"] if not board_df.empty else pd.DataFrame()
        open_df = _sort_key(open_df)
        st.markdown(
            f'<div style="color:{THEME["text_secondary"]}; font-family: JetBrains Mono, monospace; '
            f'font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; '
            f'margin-bottom: 8px; padding-bottom: 4px; border-bottom: 2px solid {THEME["border_strong"]};">'
            f'◯ OPEN  <span style="float:right; color:{THEME["text_muted"]}">{len(open_df)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if not open_df.empty:
            for _, row in open_df.iterrows():
                _render_kanban_card(row, today)
        else:
            st.markdown(
                f'<div style="color:{THEME["text_muted"]}; font-size:0.82rem; '
                f'padding: 20px; text-align:center; border: 1px dashed {THEME["border"]}; '
                f'border-radius: 4px;">No items</div>',
                unsafe_allow_html=True,
            )

    # IN PROGRESS column
    with col_progress:
        prog_df = board_df[board_df["status"] == "In Progress"] if not board_df.empty else pd.DataFrame()
        prog_df = _sort_key(prog_df)
        st.markdown(
            f'<div style="color:{THEME["text_secondary"]}; font-family: JetBrains Mono, monospace; '
            f'font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; '
            f'margin-bottom: 8px; padding-bottom: 4px; border-bottom: 2px solid {THEME["accent"]};">'
            f'▶ IN PROGRESS  <span style="float:right; color:{THEME["text_muted"]}">{len(prog_df)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if not prog_df.empty:
            for _, row in prog_df.iterrows():
                _render_kanban_card(row, today)
        else:
            st.markdown(
                f'<div style="color:{THEME["text_muted"]}; font-size:0.82rem; '
                f'padding: 20px; text-align:center; border: 1px dashed {THEME["border"]}; '
                f'border-radius: 4px;">No items</div>',
                unsafe_allow_html=True,
            )

    # DONE column (last 7 days only to keep it manageable)
    with col_done:
        done_df = board_df[board_df["status"] == "Done"] if not board_df.empty else pd.DataFrame()
        done_df = _sort_key(done_df)
        st.markdown(
            f'<div style="color:{THEME["text_secondary"]}; font-family: JetBrains Mono, monospace; '
            f'font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; '
            f'margin-bottom: 8px; padding-bottom: 4px; border-bottom: 2px solid {THEME["signal_ok"]};">'
            f'✓ DONE  <span style="float:right; color:{THEME["text_muted"]}">{len(done_df)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if not done_df.empty:
            for _, row in done_df.iterrows():
                _render_kanban_card(row, today)
        else:
            st.markdown(
                f'<div style="color:{THEME["text_muted"]}; font-size:0.82rem; '
                f'padding: 20px; text-align:center; border: 1px dashed {THEME["border"]}; '
                f'border-radius: 4px;">No items</div>',
                unsafe_allow_html=True,
            )

    # --- Summary metrics ---
    if not df.empty:
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        open_count = len(df[df["status"] == "Open"])
        prog_count = len(df[df["status"] == "In Progress"])
        done_count = len(df[df["status"] == "Done"])

        overdue_count = 0
        if "due_date" in df.columns:
            df_c = df[df["status"].isin(["Open", "In Progress"])].copy()
            if not df_c.empty:
                df_c["_p"] = pd.to_datetime(df_c["due_date"], errors="coerce")
                overdue_count = len(df_c[df_c["_p"] < pd.Timestamp(today)])

        m1.metric("Open", open_count)
        m2.metric("In Progress", prog_count)
        m3.metric("Overdue", overdue_count)
        m4.metric("Total Done", done_count)

# =========== BULK EDITOR (for heavy lifting) ===========
with tab_editor:
    st.caption(
        "Spreadsheet-style editor for bulk entry, re-assignments, or edits you can't easily do on the board. "
        "Filters to open items only — use the Archive tab for completed work."
    )

    if not df.empty:
        active_df = df[df["status"].isin(["Open", "In Progress"])].copy()
    else:
        active_df = df.copy()

    edited = st.data_editor(
        active_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "task": st.column_config.TextColumn("Task", width="large"),
            "owner": st.column_config.TextColumn("Owner"),
            "due_date": st.column_config.DateColumn("Due Date"),
            "source": st.column_config.TextColumn("Source"),
            "linked_table": st.column_config.SelectboxColumn(
                "Linked Table",
                options=["", "change_pipeline", "incidents_log", "active_rfps",
                         "client_roster", "ops_friction", "meeting_notes"],
            ),
            "linked_record": st.column_config.TextColumn("Linked Record"),
            "priority": st.column_config.SelectboxColumn(
                "Priority", options=["Low", "Medium", "High", "Critical"]
            ),
            "status": st.column_config.SelectboxColumn(
                "Status", options=["Open", "In Progress", "Done", "Cancelled"]
            ),
            "created_date": st.column_config.DateColumn("Created"),
        },
        key="editor_actions_active",
    )

    if st.button("💾  Commit Changes", key="save_actions_active"):
        if not df.empty:
            closed_df = df[~df["status"].isin(["Open", "In Progress"])]
            merged = pd.concat([edited, closed_df], ignore_index=True)
        else:
            merged = edited
        write_table("action_items", merged)
        st.success("Action items updated.")
        st.rerun()

    # Load by owner
    if not active_df.empty and "owner" in active_df.columns:
        st.divider()
        section_header("Load by Owner")
        owner_counts = active_df["owner"].value_counts()
        if not owner_counts.empty:
            st.bar_chart(owner_counts, color=THEME["accent"])

# =========== ARCHIVE ===========
with tab_all:
    section_header("Full Action Item History")
    st.caption("Complete history including Done and Cancelled items.")

    edited_all = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "task": st.column_config.TextColumn("Task", width="large"),
            "owner": st.column_config.TextColumn("Owner"),
            "due_date": st.column_config.DateColumn("Due Date"),
            "source": st.column_config.TextColumn("Source"),
            "linked_table": st.column_config.SelectboxColumn(
                "Linked Table",
                options=["", "change_pipeline", "incidents_log", "active_rfps",
                         "client_roster", "ops_friction", "meeting_notes"],
            ),
            "linked_record": st.column_config.TextColumn("Linked Record"),
            "priority": st.column_config.SelectboxColumn(
                "Priority", options=["Low", "Medium", "High", "Critical"]
            ),
            "status": st.column_config.SelectboxColumn(
                "Status", options=["Open", "In Progress", "Done", "Cancelled"]
            ),
            "created_date": st.column_config.DateColumn("Created"),
        },
        key="editor_actions_all",
    )
    if st.button("💾  Commit All Changes", key="save_actions_all"):
        write_table("action_items", edited_all)
        st.success("Full action items table updated.")
        st.rerun()
```

# =============================================================================

# MODULE 11 — MEETING NOTES

# =============================================================================

def render_meeting_notes():
“”“Institutional memory — searchable log of meetings, decisions, and actions.”””
section_header(“Meeting Notes · Institutional Memory”)

```
tab_log, tab_add = st.tabs(["📋 Meeting Log", "➕ Quick Add"])

df = load_table("meeting_notes")

with tab_log:
    st.caption(
        "Searchable record of governance meetings, client calls, and steering committees. "
        "Key decisions and action items are captured per meeting."
    )

    # Search
    search = st.text_input("Search meetings", placeholder="keyword, attendee, decision...", key="meeting_search")
    if search and not df.empty:
        mask = pd.DataFrame()
        for col in ["title", "attendees", "key_decisions", "discussion_notes", "actions_generated"]:
            if col in df.columns:
                if mask.empty:
                    mask = df[col].str.contains(search, case=False, na=False)
                else:
                    mask = mask | df[col].str.contains(search, case=False, na=False)
        display_df = df[mask] if not mask.empty else df
    else:
        display_df = df

    # Sort newest first
    if not display_df.empty and "meeting_date" in display_df.columns:
        display_df = display_df.sort_values("meeting_date", ascending=False)

    edited = st.data_editor(
        display_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "meeting_date": st.column_config.DateColumn("Date"),
            "meeting_type": st.column_config.SelectboxColumn(
                "Type", options=["Internal", "Client Call", "Governance",
                                 "Steering Committee", "Vendor", "Other"]
            ),
            "title": st.column_config.TextColumn("Title", width="medium"),
            "attendees": st.column_config.TextColumn("Attendees", width="medium"),
            "key_decisions": st.column_config.TextColumn("Key Decisions", width="large"),
            "discussion_notes": st.column_config.TextColumn("Discussion Notes", width="large"),
            "actions_generated": st.column_config.TextColumn("Actions Generated", width="large"),
        },
        key="editor_meetings",
    )

    if st.button("💾  Commit Changes", key="save_meetings"):
        # If search was active, merge edited search results back with unshown rows
        if search and not df.empty:
            unshown = df[~df["id"].isin(display_df["id"])] if "id" in df.columns else pd.DataFrame()
            merged = pd.concat([edited, unshown], ignore_index=True)
            write_table("meeting_notes", merged)
        else:
            write_table("meeting_notes", edited)
        st.success("Meeting notes updated.")
        st.rerun()

    # Meeting frequency chart
    if not df.empty and "meeting_type" in df.columns:
        st.divider()
        section_header("Meeting Frequency by Type")
        type_counts = df["meeting_type"].value_counts()
        st.bar_chart(type_counts, color=THEME["accent_purple"])

with tab_add:
    section_header("Quick Add Meeting")
    st.caption("Rapid entry form for capturing a meeting immediately after it ends.")

    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            qa_date = st.date_input("Date", value=date.today(), key="qa_date")
            qa_type = st.selectbox(
                "Type",
                ["Internal", "Client Call", "Governance", "Steering Committee", "Vendor", "Other"],
                key="qa_type",
            )
        with c2:
            qa_title = st.text_input("Title", key="qa_title")
            qa_attendees = st.text_input("Attendees (comma-separated)", key="qa_attendees")

        qa_decisions = st.text_area("Key Decisions", height=100, key="qa_decisions")
        qa_notes = st.text_area("Discussion Notes", height=100, key="qa_notes")
        qa_actions = st.text_area("Actions Generated", height=100, key="qa_actions")

        if st.button("💾  Save Meeting", key="save_quick_meeting"):
            if qa_title:
                conn = get_connection()
                try:
                    conn.execute(
                        "INSERT INTO meeting_notes "
                        "(meeting_date, meeting_type, title, attendees, key_decisions, discussion_notes, actions_generated) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (qa_date.isoformat(), qa_type, qa_title, qa_attendees,
                         qa_decisions, qa_notes, qa_actions),
                    )
                    conn.commit()
                finally:
                    conn.close()
                st.success(f"Meeting '{qa_title}' saved.")
                st.rerun()
            else:
                st.warning("Title is required.")
```

# =============================================================================

# MODULE 12 — STAKEHOLDER TRACKER & JERSEY GUIDE

# =============================================================================

# Jersey number allocation guide:

# 1-9:   Key Decision Makers / C-Suite (the ones who sign things off)

# 10-19:  Sponsors & Advocates (your allies — protect these relationships)

# 20-29:  Neutral / Swing votes (could go either way — invest here)

# 30-39:  Sceptics (need evidence, not persuasion)

# 40-49:  Blockers (know their objections, plan around them)

JERSEY_BANDS = {
“1–9”: {“label”: “Key Decision Makers”, “colour”: THEME[“accent_cyan”], “desc”: “C-suite, board, fund directors. The ones who sign things off.”},
“10–19”: {“label”: “Sponsors & Advocates”, “colour”: THEME[“accent_green”], “desc”: “Your allies. Protect and invest in these relationships.”},
“20–29”: {“label”: “Neutral / Swing Votes”, “colour”: THEME[“accent_amber”], “desc”: “Could go either way. Target for proactive engagement.”},
“30–39”: {“label”: “Sceptics”, “colour”: THEME[“accent_purple”], “desc”: “Need evidence and data, not persuasion. Respect their rigour.”},
“40–49”: {“label”: “Blockers”, “colour”: THEME[“accent_red”], “desc”: “Know their objections. Plan around them, don’t fight head-on.”},
}

def _jersey_band(number):
“”“Return the jersey band label for a given number.”””
if pd.isna(number):
return “Unassigned”
n = int(number)
if 1 <= n <= 9:
return “1–9 · Key Decision Makers”
elif 10 <= n <= 19:
return “10–19 · Sponsors & Advocates”
elif 20 <= n <= 29:
return “20–29 · Neutral / Swing Votes”
elif 30 <= n <= 39:
return “30–39 · Sceptics”
elif 40 <= n <= 49:
return “40–49 · Blockers”
return “Other”

def _disposition_emoji(disp):
“”“Map disposition to a visual indicator.”””
return {
“Sponsor”: “🟢”,
“Advocate”: “🟢”,
“Neutral”: “🟡”,
“Sceptic”: “🟠”,
“Blocker”: “🔴”,
}.get(disp, “⚪”)

def log_stakeholder_interaction(stakeholder_id: int, contact_date: str,
channel: str, note: str = “”):
“””
Single-row update for “Log Contact” button.
Updates last_interaction_date, optionally channel and appends to notes.
Audit-aware.
“””
conn = get_connection()
try:
cur = conn.cursor()
# Fetch current state
cur.execute(
“SELECT name, last_interaction_date, interaction_notes, preferred_channel “
“FROM stakeholders WHERE id = ?”,
(stakeholder_id,),
)
row = cur.fetchone()
if row is None:
return

```
    name, old_date, old_notes, old_channel = row
    old_notes = old_notes or ""

    # Build new notes: prepend dated entry
    if note.strip():
        dated_note = f"[{contact_date}] {note.strip()}"
        new_notes = f"{dated_note}\n{old_notes}" if old_notes else dated_note
    else:
        new_notes = old_notes

    # Update
    cur.execute(
        "UPDATE stakeholders SET last_interaction_date = ?, "
        "interaction_notes = ?, preferred_channel = ? WHERE id = ?",
        (contact_date, new_notes, channel, stakeholder_id),
    )

    # Audit entry
    changes = [f"last_interaction_date: '{old_date}' → '{contact_date}'"]
    if channel != old_channel:
        changes.append(f"preferred_channel: '{old_channel}' → '{channel}'")
    if note.strip():
        changes.append(f"note added: '{note.strip()[:60]}'")

    cur.execute(
        "INSERT INTO audit_log (timestamp, table_name, action, record_summary, field_changes) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(),
            "stakeholders",
            "UPDATE",
            f"stakeholders → {name}",
            "; ".join(changes),
        ),
    )
    conn.commit()
finally:
    conn.close()
```

def render_stakeholder_tracker():
“””
Political landscape mapper — who matters, where they stand, and
jersey numbers for quick reference in governance contexts.
“””
tab_log, tab_roster, tab_jerseys, tab_map = st.tabs(
[“📞 Log Contact”, “👥 Stakeholder Roster”, “🏉 Jersey Guide”, “🗺️ Influence Map”]
)

```
df = load_table("stakeholders")
today = date.today()

# =========== LOG CONTACT — fast-path for daily use ===========
with tab_log:
    section_header("Log Stakeholder Contact")
    st.caption(
        "One-click way to record that you spoke to someone today. "
        "Updates their last contact date and optionally appends a dated note. "
        "Critical relationships going cold are shown at the top."
    )

    if df.empty:
        st.info("Add stakeholders to the roster first, then come back here to log interactions.")
    else:
        # Compute days since last contact
        df_display = df.copy()
        df_display["_last_parsed"] = pd.to_datetime(df_display["last_interaction_date"], errors="coerce")
        df_display["_days_since"] = df_display["_last_parsed"].apply(
            lambda d: (today - d.date()).days if pd.notna(d) else 9999
        )

        # Sort: priority relationships first (Sponsor/Advocate/KDM) that haven't been contacted recently
        def _priority_rank(row):
            is_priority = (
                row.get("disposition") in ["Sponsor", "Advocate"]
                or row.get("influence_level") == "Key Decision Maker"
            )
            days = row.get("_days_since", 9999)
            # Priority people who are cold come first
            if is_priority and days > 14:
                return (0, -days)  # most overdue priority contacts at top
            elif is_priority:
                return (1, -days)
            else:
                return (2, -days)

        df_display["_rank"] = df_display.apply(_priority_rank, axis=1)
        df_display = df_display.sort_values("_rank", key=lambda s: s.apply(lambda x: x if isinstance(x, tuple) else (3, 0)))

        # Cold relationship alert
        cold_priority = df_display[
            (df_display["_days_since"] > 14)
            & (
                df_display["disposition"].isin(["Sponsor", "Advocate"])
                | (df_display["influence_level"] == "Key Decision Maker")
            )
        ]
        if not cold_priority.empty:
            st.warning(
                f"⚠️  **{len(cold_priority)} priority stakeholder(s)** haven't been contacted in over 14 days. "
                "Shown at the top."
            )

        # Filter box
        fcol1, fcol2 = st.columns([3, 1])
        with fcol1:
            name_filter = st.text_input(
                "Filter by name or department",
                placeholder="type to narrow down...",
                key="log_contact_filter",
            )
        with fcol2:
            show_cold_only = st.checkbox("Cold only (> 14d)", key="log_contact_cold_only")

        display_rows = df_display
        if name_filter:
            mask = (
                display_rows["name"].str.contains(name_filter, case=False, na=False)
                | display_rows["department"].str.contains(name_filter, case=False, na=False)
                | display_rows["role"].str.contains(name_filter, case=False, na=False)
            )
            display_rows = display_rows[mask]
        if show_cold_only:
            display_rows = display_rows[display_rows["_days_since"] > 14]

        st.divider()

        # Render each stakeholder as a compact row with a Log button
        for _, r in display_rows.iterrows():
            stakeholder_id = int(r["id"])
            name = r.get("name", "?")
            role = r.get("role", "") or ""
            dept = r.get("department", "") or ""
            disp = r.get("disposition", "Neutral") or "Neutral"
            influence = r.get("influence_level", "Medium") or "Medium"
            last_date = r.get("last_interaction_date", "")
            days_since = r.get("_days_since", 9999)
            pref_channel = r.get("preferred_channel", "Email") or "Email"
            jersey = r.get("jersey_number")

            # Age indicator
            if pd.isna(r.get("_last_parsed")):
                age_str = "Never contacted"
                age_color = THEME["signal_risk"]
            elif days_since == 0:
                age_str = "Contacted today"
                age_color = THEME["signal_ok"]
            elif days_since <= 7:
                age_str = f"{days_since}d ago"
                age_color = THEME["signal_ok"]
            elif days_since <= 14:
                age_str = f"{days_since}d ago"
                age_color = THEME["signal_warn"]
            else:
                age_str = f"{days_since}d ago"
                age_color = THEME["signal_risk"]

            jersey_badge = (
                f'<span style="font-family: JetBrains Mono, monospace; '
                f'background: {THEME["bg_elevated"]}; padding: 1px 6px; border-radius: 3px; '
                f'font-size: 0.75rem; color: {THEME["text_secondary"]};">#{int(jersey)}</span> '
                if pd.notna(jersey) else ""
            )

            # Card + action button in a row
            card_col, btn_col = st.columns([4, 1])
            with card_col:
                st.markdown(
                    f"""<div style="
                        background: {THEME['bg_card']};
                        border: 1px solid {THEME['border']};
                        border-left: 3px solid {age_color};
                        border-radius: 4px;
                        padding: 10px 14px;
                        margin-bottom: 6px;
                    ">
                        <div style="font-weight: 500; color: {THEME['text_primary']}; font-size: 0.92rem;">
                            {jersey_badge}{name}
                            <span style="color: {THEME['text_muted']}; font-weight: 400; font-size: 0.85rem;">
                                · {role}{' · ' + dept if dept else ''}
                            </span>
                        </div>
                        <div style="color: {THEME['text_secondary']}; font-size: 0.78rem; margin-top: 4px;">
                            {_disposition_emoji(disp)} {disp} · {influence} · prefers {pref_channel}
                            <span style="float:right; color: {age_color}; font-weight: 500;">
                                {age_str}
                            </span>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with btn_col:
                # Expandable quick-log button
                with st.popover("📞 Log contact", use_container_width=True):
                    st.markdown(f"**Log contact with {name}**")
                    log_date = st.date_input(
                        "Date", value=today, key=f"log_date_{stakeholder_id}"
                    )
                    log_channel = st.selectbox(
                        "Channel",
                        ["Email", "Teams", "In Person", "Phone", "Slack"],
                        index=["Email", "Teams", "In Person", "Phone", "Slack"].index(pref_channel)
                            if pref_channel in ["Email", "Teams", "In Person", "Phone", "Slack"] else 0,
                        key=f"log_ch_{stakeholder_id}",
                    )
                    log_note = st.text_area(
                        "Note (optional)",
                        placeholder="what was discussed, commitments made, sentiment...",
                        key=f"log_note_{stakeholder_id}",
                        height=80,
                    )
                    if st.button(
                        "Save", key=f"log_save_{stakeholder_id}", use_container_width=True
                    ):
                        log_stakeholder_interaction(
                            stakeholder_id,
                            log_date.isoformat(),
                            log_channel,
                            log_note,
                        )
                        st.success(f"Logged contact with {name}")
                        st.rerun()

with tab_roster:
    section_header("Stakeholder Roster")
    st.caption(
        "Track disposition, influence level, and interaction recency. "
        "Jersey numbers encode your private assessment of where each person sits."
    )

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "name": st.column_config.TextColumn("Name"),
            "role": st.column_config.TextColumn("Role"),
            "department": st.column_config.TextColumn("Dept"),
            "organisation": st.column_config.TextColumn("Org"),
            "disposition": st.column_config.SelectboxColumn(
                "Disposition",
                options=["Sponsor", "Advocate", "Neutral", "Sceptic", "Blocker"],
            ),
            "influence_level": st.column_config.SelectboxColumn(
                "Influence",
                options=["Low", "Medium", "High", "Key Decision Maker"],
            ),
            "jersey_number": st.column_config.NumberColumn("Jersey #", min_value=1, max_value=99),
            "last_interaction_date": st.column_config.DateColumn("Last Contact"),
            "interaction_notes": st.column_config.TextColumn("Notes", width="large"),
            "preferred_channel": st.column_config.SelectboxColumn(
                "Channel", options=["Email", "Teams", "In Person", "Phone", "Slack"]
            ),
            "topics_of_interest": st.column_config.TextColumn("Interests", width="medium"),
        },
        key="editor_stakeholders",
    )

    if st.button("💾  Commit Changes", key="save_stakeholders"):
        write_table("stakeholders", edited)
        st.success("Stakeholder roster updated.")
        st.rerun()

    # Disposition summary
    if not df.empty:
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            section_header("Disposition Breakdown")
            disp_counts = df["disposition"].value_counts()
            st.bar_chart(disp_counts, color=THEME["accent_cyan"])
        with c2:
            section_header("Influence Distribution")
            inf_counts = df["influence_level"].value_counts()
            st.bar_chart(inf_counts, color=THEME["accent_amber"])

with tab_jerseys:
    section_header("Jersey Number Guide")
    st.caption(
        "A private shorthand for stakeholder assessment. Use jersey numbers in conversation "
        "or notes — only you know the coding scheme."
    )

    # Explain the bands
    for band_key, band_info in JERSEY_BANDS.items():
        st.markdown(
            f'<div style="background:{band_info["colour"]}18; border-left: 4px solid {band_info["colour"]}; '
            f'padding: 12px 16px; margin-bottom: 8px; border-radius: 4px;">'
            f'<strong style="color:{band_info["colour"]}; font-family: JetBrains Mono, monospace;">'
            f'#{band_key}</strong> — '
            f'<strong>{band_info["label"]}</strong><br/>'
            f'<span style="color:{THEME["text_secondary"]}; font-size: 0.88rem;">{band_info["desc"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Show current jersey assignments
    if not df.empty and "jersey_number" in df.columns:
        section_header("Current Jersey Assignments")
        assigned = df[df["jersey_number"].notna()].copy()
        if not assigned.empty:
            assigned["jersey_number"] = assigned["jersey_number"].astype(int)
            assigned["band"] = assigned["jersey_number"].apply(_jersey_band)
            assigned = assigned.sort_values("jersey_number")
            for _, r in assigned.iterrows():
                emoji = _disposition_emoji(r.get("disposition", ""))
                st.markdown(
                    f"**#{int(r['jersey_number'])}** — {emoji} {r.get('name', '?')} "
                    f"({r.get('role', '?')}, {r.get('department', '?')}) · "
                    f"{r.get('disposition', '?')} · {r.get('influence_level', '?')}"
                )
        else:
            st.info("No jersey numbers assigned yet. Edit the roster to add them.")
    else:
        st.info("Add stakeholders to the roster first, then assign jersey numbers.")

with tab_map:
    section_header("Influence × Disposition Map")
    st.caption(
        "Visual mapping of political landscape. Quadrant thinking: "
        "high-influence sponsors are your power base; high-influence blockers are your risk."
    )

    if not df.empty:
        # Build a simple text-based influence map
        influence_order = ["Key Decision Maker", "High", "Medium", "Low"]
        disposition_order = ["Sponsor", "Advocate", "Neutral", "Sceptic", "Blocker"]

        for inf in influence_order:
            inf_group = df[df["influence_level"] == inf] if "influence_level" in df.columns else pd.DataFrame()
            if inf_group.empty:
                continue

            st.markdown(f"#### {inf}")
            cols = st.columns(len(disposition_order))
            for i, disp in enumerate(disposition_order):
                with cols[i]:
                    cell = inf_group[inf_group["disposition"] == disp] if "disposition" in inf_group.columns else pd.DataFrame()
                    emoji = _disposition_emoji(disp)
                    st.markdown(f"**{emoji} {disp}**")
                    if not cell.empty:
                        for _, r in cell.iterrows():
                            jersey = f" #{int(r['jersey_number'])}" if pd.notna(r.get("jersey_number")) else ""
                            st.markdown(
                                f"<span style='font-size:0.85rem;'>{r.get('name', '?')}{jersey}</span>",
                                unsafe_allow_html=True,
                            )
                    else:
                        muted_color = THEME["text_muted"]
                        st.markdown(
                            f"<span style='color:{muted_color}; font-size:0.82rem;'>—</span>",
                            unsafe_allow_html=True,
                        )
            st.divider()
    else:
        st.info("Add stakeholders to the roster to populate the influence map.")
```

# =============================================================================

# MODULE 8 — AUDIT TRAIL

# =============================================================================

def render_audit_trail():
“””
Searchable, filterable audit log — timestamped record of every data change.
This is the receipts table. In a political environment, dates don’t lie.
“””
section_header(“Audit Trail · Change History”)

```
audit_df = load_table("audit_log")

if audit_df.empty:
    st.info(
        "No changes recorded yet. The audit trail captures every insert, "
        "update, and delete across all tables with timestamps."
    )
    return

# --- Filters ---
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    tables = ["All"] + sorted(audit_df["table_name"].unique().tolist())
    sel_table = st.selectbox("Filter by Table", tables, key="audit_filter_table")
with col_f2:
    actions = ["All", "INSERT", "UPDATE", "DELETE"]
    sel_action = st.selectbox("Filter by Action", actions, key="audit_filter_action")
with col_f3:
    search_term = st.text_input("Search", placeholder="keyword...", key="audit_search")

filtered = audit_df.copy()
if sel_table != "All":
    filtered = filtered[filtered["table_name"] == sel_table]
if sel_action != "All":
    filtered = filtered[filtered["action"] == sel_action]
if search_term:
    mask = (
        filtered["record_summary"].str.contains(search_term, case=False, na=False)
        | filtered["field_changes"].str.contains(search_term, case=False, na=False)
    )
    filtered = filtered[mask]

# Sort newest first
filtered = filtered.sort_values("id", ascending=False)

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True,
    column_config={
        "id": st.column_config.NumberColumn("Seq", width="small"),
        "timestamp": st.column_config.TextColumn("Timestamp"),
        "table_name": st.column_config.TextColumn("Table"),
        "action": st.column_config.TextColumn("Action"),
        "record_summary": st.column_config.TextColumn("Record"),
        "field_changes": st.column_config.TextColumn("Changes", width="large"),
    },
)

st.divider()

# Summary stats
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Entries", len(audit_df))
c2.metric("Inserts", len(audit_df[audit_df["action"] == "INSERT"]))
c3.metric("Updates", len(audit_df[audit_df["action"] == "UPDATE"]))
c4.metric("Deletes", len(audit_df[audit_df["action"] == "DELETE"]))

# Purge option (with confirmation)
st.divider()
with st.expander("🗑️ Purge Audit Log", expanded=False):
    st.warning("This permanently deletes all audit history. Use with extreme caution.")
    if st.button("Confirm Purge", key="purge_audit"):
        run_query("DELETE FROM audit_log")
        st.success("Audit log purged.")
        st.rerun()
```

# =============================================================================

# MAIN APPLICATION

# =============================================================================

def main():
st.set_page_config(
page_title=APP_TITLE,
page_icon=APP_ICON,
layout=“wide”,
initial_sidebar_state=“expanded”,
)

```
inject_css()
init_database()

# --- Sidebar navigation ---
with st.sidebar:
    st.markdown(
        f"""
        <div style="text-align:center; padding: 16px 0 8px 0;">
            <span style="font-size:1.8rem;">{APP_ICON}</span><br/>
            <span style="
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.95rem;
                color: {THEME['text_primary']};
                letter-spacing: 0.08em;
                text-transform: uppercase;
                font-weight: 600;
            ">PM Command Center</span><br/>
            <span style="
                font-size: 0.7rem;
                color: {THEME['text_muted']};
                letter-spacing: 0.05em;
            ">Fund Administration Ops Intelligence</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "Navigate",
        options=[
            "☀️ Daily Standup",
            "Executive Dashboard",
            "Action Items",
            "Meeting Notes",
            "Commercials & Repricing",
            "RFP & Pipeline Management",
            "Client Change & Onboarding",
            "Risk & Quality",
            "Stakeholders & Jerseys",
            "LLM Export & Reporting",
            "Weekly Update Generator",
            "Audit Trail",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"Database: `{DB_PATH.name}`")
    st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

# --- Route to selected module ---
if page == "☀️ Daily Standup":
    render_daily_standup()
elif page == "Executive Dashboard":
    render_executive_dashboard()
elif page == "Action Items":
    render_action_items()
elif page == "Meeting Notes":
    render_meeting_notes()
elif page == "Commercials & Repricing":
    render_commercials()
elif page == "RFP & Pipeline Management":
    render_rfp_pipeline()
elif page == "Client Change & Onboarding":
    render_change_pipeline()
elif page == "Risk & Quality":
    render_risk_quality()
elif page == "Stakeholders & Jerseys":
    render_stakeholder_tracker()
elif page == "LLM Export & Reporting":
    render_llm_export()
elif page == "Weekly Update Generator":
    render_weekly_update()
elif page == "Audit Trail":
    render_audit_trail()
```

if **name** == “**main**”:
main()