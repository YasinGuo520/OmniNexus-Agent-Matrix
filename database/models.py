"""
OmniNexus AI - High-Concurrency Persistent Database Layer (SQLite WAL)
Defines schema for Stores, Funnel Metrics, HITL Human-in-the-Loop Tasks,
Agent Cluster Topology, Dead-Letter Queue (DLQ), and Trust Ladder Permissions.
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omninexus_state.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # 1. E-Commerce Stores Registry
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        store_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        platform TEXT NOT NULL,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'active'
    )
    """)
    
    # 2. Daily Funnel Metrics
    cur.execute("""
    CREATE TABLE IF NOT EXISTS funnel_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        date TEXT,
        visitors INTEGER,
        add_to_cart INTEGER,
        orders INTEGER,
        refunds INTEGER,
        gmv REAL,
        net_profit REAL,
        FOREIGN KEY(store_id) REFERENCES stores(store_id)
    )
    """)
    
    # 3. Tasks & HITL (Human-in-the-Loop) State Machine
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        module TEXT NOT NULL,
        task_type TEXT NOT NULL,
        title TEXT NOT NULL,
        proposal TEXT NOT NULL,
        status TEXT NOT NULL,
        inspector_notes TEXT,
        boss_feedback TEXT,
        artifacts TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    
    # 4. Agent Cluster Topology & Heartbeats
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agent_status (
        agent_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'idle',
        sub_items TEXT,
        pipeline_info TEXT,
        last_run TEXT,
        next_run TEXT
    )
    """)
    
    # 5. Executive Daily Briefs Ledger
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_briefs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        time_slot TEXT,
        content TEXT,
        action_count INTEGER DEFAULT 0
    )
    """)

    # 6. Industrial-Grade Dead-Letter Queue (DLQ)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dead_letter_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        worker_name TEXT NOT NULL,
        task_name TEXT NOT NULL,
        reason TEXT NOT NULL,
        error_stack TEXT,
        retry_count INTEGER,
        status TEXT DEFAULT 'OPEN',
        created_at TEXT
    )
    """)

    # 7. Progressive Trust Ladder Governance
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agent_permissions (
        action_name TEXT PRIMARY KEY,
        worker_name TEXT NOT NULL,
        consecutive_approvals INTEGER DEFAULT 0,
        autonomy_level TEXT DEFAULT 'HUMAN_APPROVAL',
        last_evaluated TEXT
    )
    """)
    
    # Default Commerce Nodes
    default_stores = [
        ("store_a", "Amazon Store Alpha", "Amazon", "USD", "active"),
        ("store_b", "Etsy Crafts Hub", "Etsy", "USD", "active"),
        ("store_c", "Shopify Global Store", "Shopify", "USD", "active"),
        ("store_d", "TikTok Shop Direct", "TikTok", "USD", "active")
    ]
    for s in default_stores:
        cur.execute("INSERT OR IGNORE INTO stores (store_id, name, platform, currency, status) VALUES (?,?,?,?,?)", s)
        
    # Baseline Funnel Metrics
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT count(*) as cnt FROM funnel_metrics WHERE store_id='store_a'")
    if cur.fetchone()["cnt"] == 0:
        cur.execute("""
        INSERT INTO funnel_metrics (store_id, date, visitors, add_to_cart, orders, refunds, gmv, net_profit)
        VALUES ('store_a', ?, 1240, 74, 31, 2, 69.98, 38.5)
        """, (today,))
        cur.execute("""
        INSERT INTO funnel_metrics (store_id, date, visitors, add_to_cart, orders, refunds, gmv, net_profit)
        VALUES ('store_b', ?, 2100, 142, 68, 5, 238.89, 145.2)
        """, (today,))
        
    # Default Specialized Agent Swarm
    default_agents = [
        ("ceo", "CEO Agent", "Executive Chief of Staff", "idle", 
         json.dumps({"Daily Patrols": "8 cycles", "Direct Interventions": "4 actions", "Interval": "Hourly"}), 
         json.dumps({"Upstream": "Tri-daily executive summary (08:20/12:20/20:20)", "Downstream": "DAG task dispatch & final QA"}), 
         "08:20", "09:20"),
        ("ecom", "Ecom Agent", "Traffic & Catalog Arbiter", "idle", 
         json.dumps({"Amazon": "$69.98 WTD", "Etsy": "$238.89 WTD", "Shopify": "Scaling", "TikTok": "420 orders/day"}), 
         json.dumps({"Dispatched": "4 tasks", "Report": "08:05", "Ingestion": "Order Webhooks + 08:00 snapshot"}), 
         "08:05", "10:30"),
        ("media", "Media Agent", "Multimodal Growth Engine", "idle", 
         json.dumps({"TikTok Main": "64.0k subs (+74)", "YouTube": "22.5k subs", "Instagram": "13.3k subs", "X / Twitter": "4,745 followers"}), 
         json.dumps({"Ingestion": "3x / day", "Report": "08:16", "Weekly Reach": "+14.6k"}), 
         "08:16", "12:00"),
        ("solutions", "Solutions Agent", "High-Ticket SaaS & Delivery", "idle", 
         json.dumps({"Enterprise Contract": "$20,000 locked", "B2B Leads": "2 qualified", "Upwork Consulting": "$50/hr", "Fiverr Direct": "Verified", "SaaS Pipeline": "16-Agent QA"}), 
         json.dumps({"Dispatched": "2 tasks", "Lead Scan": "08:10", "Funnel State": "1 Closed / 3 In Pipeline"}), 
         "08:10", "11:30"),
        ("opensource", "OpenSource Agent", "Code & Tooling Pipeline", "idle", 
         json.dumps({"OmniNexus": "Verified", "FastMCP Gateway": "Active", "DLQ Circuit": "Green"}), 
         json.dumps({"Dispatched": "3 tasks", "Report": "07:00", "New Stars": "+47 this week"}), 
         "07:00", "09:30"),
        ("invest", "Invest Agent", "Market & Risk Intelligence", "idle", 
         json.dumps({"Alpha Factors": "+0.25% WTD", "Sector Monitor": "Active"}), 
         json.dumps({"Execution": "Paper Trading", "Report": "05:44", "Heartbeat": "08:20"}), 
         "05:44", "08:20"),
        ("knowledge", "Knowledge Agent", "Persistent Memory Vault", "idle", 
         json.dumps({"Vault Ingestion": "22:30 Daily", "Proposals": "2 Pending Review", "State Snapshot": "Verified"}), 
         json.dumps({"Storage": "Obsidian + SQLite WAL", "Context Switch": "Zero Loss Instant Recovery"}), 
         "22:30", "23:30"),
        ("assistant", "Assistant Agent", "Scheduler & Opportunity Radar", "idle", 
         json.dumps({"Hackathon Radar": "PayPal AI ($67.5k)", "Tech Forums": "84 monitored", "Opportunities": "4 active", "7-Day Milestones": "11 items"}), 
         json.dumps({"Automation": "Continuous background polling", "New Alerts": "16 items"}), 
         "07:35", "Tomorrow 07:30")
    ]
    for a in default_agents:
        cur.execute("""
        INSERT OR REPLACE INTO agent_status (agent_id, name, role, status, sub_items, pipeline_info, last_run, next_run)
        VALUES (?,?,?,?,?,?,?,?)
        """, a)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("OmniNexus state database initialized successfully at:", DB_PATH)
