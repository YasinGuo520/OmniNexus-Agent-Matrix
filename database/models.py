"""
Phoenix Tree AI - 数据库层与轻量 SQLite 模型
包含：店铺、漏斗指标、待办工单(HITL)、Agent状态与经营结报
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phoenix_tree.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # 1. 店铺配置表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        store_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        platform TEXT NOT NULL,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'active'
    )
    """)
    
    # 2. 整店漏斗日数据表
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
    
    # 3. 待办工单与 HITL 状态机表
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
    
    # 4. Agent 状态表
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
    
    # 5. 每日经营简报表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_briefs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        time_slot TEXT,
        content TEXT,
        action_count INTEGER DEFAULT 0
    )
    """)

    # 6. 工业级死信队列与熔断表 (DLQ)
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

    # 7. 渐进式授权信任阶梯表 (Trust Ladder)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agent_permissions (
        action_name TEXT PRIMARY KEY,
        worker_name TEXT NOT NULL,
        consecutive_approvals INTEGER DEFAULT 0,
        autonomy_level TEXT DEFAULT 'HUMAN_APPROVAL',
        last_evaluated TEXT
    )
    """)
    
    # 插入默认 4 大店铺
    default_stores = [
        ("store_a", "亚马逊店铺 A", "Amazon", "USD", "active"),
        ("store_b", "Etsy 店铺 B", "Etsy", "USD", "active"),
        ("store_c", "Shopify 独立站", "Shopify", "USD", "active"),
        ("store_d", "抖音小店 / 抖店", "Douyin", "CNY", "active")
    ]
    for s in default_stores:
        cur.execute("INSERT OR IGNORE INTO stores (store_id, name, platform, currency, status) VALUES (?,?,?,?,?)", s)
        
    # 插入默认漏斗数据 (还原视频真实数字：访客1240, 加购74, 下单31)
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
        
    # 初始化 7 大 Agent
    default_agents = [
        ("ceo", "CEO Agent", "全局流程中枢", "idle", 
         json.dumps({"今天巡视": "8 轮", "CEO 出手": "4 次", "巡检周期": "每小时"}), 
         json.dumps({"向上": "每日汇报 3 次 (08:20/12:20/20:20)", "向下": "统筹下发派活与最终验收"}), 
         "08:20", "09:20"),
        ("ecom", "电商 Agent", "店铺流量与选品", "idle", 
         json.dumps({"亚马逊": "$69.98 本周", "Etsy": "$238.89 本周", "Shopify": "$0.00", "抖店": "日结420单"}), 
         json.dumps({"派活": "4 件", "日报": "08:05", "采集方式": "成交邮件 + 08:00 定时快照"}), 
         "08:05", "10:30"),
        ("media", "内容 Agent", "矩阵内容与爆款", "idle", 
         json.dumps({"抖音大号": "6.40万粉 (+74)", "抖音小号": "2.25万粉", "视频号": "1.33万粉 (+1)", "B站": "4,745粉 (+7)"}), 
         json.dumps({"采集": "3 次/天", "汇报": "08:16", "本周触达": "+1.46万"}), 
         "08:16", "12:00"),
        ("solutions", "企服·SaaS Agent", "高客单交付与SaaS孵化", "idle", 
         json.dumps({"BOSS高客单": "2.0w 锁定中", "电鸭/V2兼职": "2 份商机", "Upwork海外": "$50/h", "Fiverr交付": "标准包跑通", "SaaS孵化": "16-Agent质检"}), 
         json.dumps({"派活": "2 件", "商机巡检": "08:10", "高客单漏斗": "1 家锁定 / 3 家跟进"}), 
         "08:10", "11:30"),
        ("opensource", "开源 Agent", "代码与工具链", "idle", 
         json.dumps({"a-stock-data": "+16 星", "TradingAgents": "+1 星", "Vibe-Research": "+13 星"}), 
         json.dumps({"派活": "3 件", "日报": "07:00", "本周新增星": "+47"}), 
         "07:00", "09:30"),
        ("invest", "投资 Agent", "产业与行情研究", "idle", 
         json.dumps({"美股量化": "+0.25% 本周", "A股产业投资": "1/1 在跑"}), 
         json.dumps({"派工": "不派工", "日报": "05:44", "心跳": "08:20"}), 
         "05:44", "08:20"),
        ("knowledge", "运营·知识库", "每晚沉淀与快照", "idle", 
         json.dumps({"知识沉淀": "每晚 22:30", "知识提案": "2 份待审", "状态快照": "23:30 跑完"}), 
         json.dumps({"入库": "每晚自动整理", "换Agent": "0秒无损接手"}), 
         "22:30", "23:30"),
        ("assistant", "助理 Agent", "线索雷达与日程", "idle", 
         json.dumps({"比赛巡检": "快截止 0 个", "AI论坛": "84 场", "新职位": "4 条", "7天日程": "11 件"}), 
         json.dumps({"每天巡检": "自动扫描", "新发现": "16 条"}), 
         "07:35", "明天 07:30")
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
    print("Database initialized successfully at:", DB_PATH)
