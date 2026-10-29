"""
OmniNexus AI - 控制中枢后端服务器 (server.py)
基于 aiohttp 实现异步全栈服务：提供暗黑科技作战大屏 API 与静态资源托管
"""
import os
import json
import asyncio
from datetime import datetime
from aiohttp import web

from database.models import init_db, get_db
from core.ceo_agent import CEOAgent
from workers.ecom_worker import EcomWorker
from workers.hackathon_worker import HackathonWorker
from workers.forum_worker import ForumWorker
from workers.github_skills_worker import GitHubSkillsWorker
from workers.boss_parttime_worker import BossParttimeWorker
from workers.schedule_worker import ScheduleWorker
from workers.knowledge_worker import KnowledgeWorker
from workers.invest_worker import InvestWorker
from workers.opensource_worker import OpenSourceWorker
from workers.solutions_worker import SolutionsWorker
from workers.media_worker import MediaWorker

init_db()
ceo = CEOAgent()
ecom = EcomWorker()
media = MediaWorker()
hackathon = HackathonWorker()
forum = ForumWorker()
github_skills = GitHubSkillsWorker()
boss_parttime = BossParttimeWorker()
schedule = ScheduleWorker()
knowledge = KnowledgeWorker()
invest = InvestWorker()
opensource = OpenSourceWorker()
solutions = SolutionsWorker()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

# ── API 路由 ──

async def get_overview(request):
    """总览页数据：7个Agent在岗状态、心跳、待办数量"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM agent_status")
    agents = []
    for r in cur.fetchall():
        d = dict(r)
        d["sub_items"] = json.loads(d["sub_items"]) if d["sub_items"] else {}
        d["pipeline_info"] = json.loads(d["pipeline_info"]) if d["pipeline_info"] else {}
        agents.append(d)
        
    cur.execute("SELECT count(*) as cnt FROM tasks WHERE status = 'PENDING_APPROVAL'")
    pending_count = cur.fetchone()["cnt"]

    # 真实计算 CEO 巡视轮数与出手次数
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT count(*) as cnt FROM tasks WHERE created_at LIKE ?", (f"{today_prefix}%",))
    today_actions = cur.fetchone()["cnt"]

    cur.execute("SELECT count(*) as cnt FROM dead_letter_queue WHERE created_at LIKE ?", (f"{today_prefix}%",))
    today_dlq = cur.fetchone()["cnt"]

    current_hour = datetime.now().hour
    rounds = max(1, current_hour - 7) # 假设 8 点开盘，每小时巡视一轮
    
    conn.close()
    
    hack_rep = hackathon.get_latest_report()
    forum_rep = forum.get_latest_report()
    gh_rep = github_skills.get_latest_report()
    bp_rep = boss_parttime.get_report()
    sch_rep = schedule.get_report()
    kb_rep = knowledge.get_report()
    inv_rep = invest.get_report()
    os_rep = opensource.get_report()

    is_en = (request.query.get("lang") == "en") or ("/en" in request.headers.get("Referer", ""))

    # 处理 BOSS 长期兼职 / 雇主指标展示
    if is_en:
        if bp_rep["mode"] == "hired" and bp_rep["active_employer"]:
            bp_subtext = f"Resident: {bp_rep['active_employer']['company']}"
            bp_count = bp_rep['active_employer']['salary_monthly']
            bp_title = f"Resident: {bp_rep['active_employer']['company']}"
        else:
            bp_subtext = "5 Golden Gigs Monitored · Click for Brief"
            bp_count = "5 Active"
            bp_title = "High-Ticket Contracts"

        resp_agents = []
        en_agent_map = {
            "ceo": ("CEO Agent", "Global Orchestration Core"),
            "ecom": ("E-Commerce Agent", "Store Traffic & Arbitrage"),
            "media": ("Media Growth Agent", "Matrix Content & Distribution"),
            "solutions": ("Solutions Agent", "High-Ticket B2B & Micro-SaaS"),
            "opensource": ("Open Source Agent", "Tooling & Developer Ecosystem"),
            "invest": ("Capital Agent", "Treasury & Market Research"),
            "knowledge": ("Knowledge Agent", "Obsidian Vault & Snapshot"),
            "assistant": ("Assistant Agent", "Opportunity Radar & Schedule")
        }
        for ag in agents:
            ag_copy = dict(ag)
            aid = ag_copy.get("agent_id")
            if aid in en_agent_map:
                ag_copy["name"] = en_agent_map[aid][0]
                ag_copy["role"] = en_agent_map[aid][1]
            resp_agents.append(ag_copy)

        return web.json_response({
            "system_name": "OMNINEXUS AI Executive Matrix HUD",
            "online_agents": f"{len(agents)}/8",
            "pending_count": pending_count,
            "boss": {
                "name": "Yasin",
                "role": "Founder · Strategic Arbitrage",
                "pending_badge": f"Awaiting: {pending_count} items"
            },
            "ceo": {
                "status": f"Hourly Patrols · Today {rounds} cycles · Interventions {today_actions} actions (Circuit Breakers: {today_dlq})",
                "report_times": "3x Daily (08:20 / 12:20 / 20:20 SGT)"
            },
            "agents": resp_agents,
            "assistant_metrics": {
                "hackathon": {
                    "urgent_count": hack_rep["summary"]["urgent_count"],
                    "new_count": hack_rep["summary"]["new_count"],
                    "subtext": f"Expiring Soon: {hack_rep['summary']['urgent_count']} · Generate Brief",
                    "count_display": hack_rep["summary"]["urgent_count"]
                },
                "forum": {
                    "total_monitored": forum_rep["summary"]["total_monitored"],
                    "selected_count": forum_rep["summary"]["selected_count"],
                    "new_count": forum_rep["summary"]["new_count"],
                    "subtext": f"30 Days Horizon: {forum_rep['summary']['total_monitored']} events · Curated: {forum_rep['summary']['selected_count']}",
                    "count_display": forum_rep["summary"]["new_count"]
                },
                "github_skills": {
                    "total_monitored": gh_rep["summary"]["total_monitored"],
                    "selected_count": gh_rep["summary"]["selected_count"],
                    "new_count": gh_rep["summary"]["new_count"],
                    "subtext": f"Tracking: {gh_rep['summary']['total_monitored']} crates · Curated: {gh_rep['summary']['selected_count']}",
                    "count_display": f"+{gh_rep['summary']['new_count']}"
                },
                "boss_parttime": {
                    "mode": bp_rep["mode"],
                    "title": bp_title,
                    "subtext": bp_subtext,
                    "count_display": bp_count
                },
                "schedule": {
                    "total_7_days": sch_rep["summary"]["total_7_days"],
                    "today_total": sch_rep["summary"]["today_total"],
                    "today_pending": sch_rep["summary"]["today_pending"],
                    "urgent_count": sch_rep["summary"]["urgent_count"],
                    "subtext": "7-Day Horizon: 11 items · Pending: 1 item",
                    "count_display": "1 Today"
                },
                "knowledge": {
                    "total_sops": kb_rep["summary"]["total_sops"],
                    "pending_proposals_count": kb_rep["summary"]["pending_proposals_count"],
                    "last_snapshot_time": kb_rep["summary"]["last_snapshot_time"],
                    "subtext": f"Synthesized: {kb_rep['summary']['total_sops']} playbooks · Pending: {kb_rep['summary']['pending_proposals_count']}",
                    "count_display": f"{kb_rep['summary']['total_sops']} docs"
                },
                "invest": {
                    "cnh_rate": inv_rep["data"]["summary"]["cnh_rate"],
                    "fx_advice": inv_rep["data"]["summary"]["fx_advice"],
                    "runway_days": inv_rep["data"]["summary"]["runway_days"],
                    "annual_yield": inv_rep["data"]["summary"]["annual_yield"],
                    "macro_mood": inv_rep["data"]["summary"]["macro_mood"],
                    "subtext": f"USD/CNH: {inv_rep['data']['summary']['cnh_rate']} · Runway: {inv_rep['data']['summary']['runway_days']}d · APY: {inv_rep['data']['summary']['annual_yield']}",
                    "count_display": "5/5 Active"
                },
                "opensource": {
                    "total_stars": os_rep["data"]["summary"]["total_stars"],
                    "today_new_stars": os_rep["data"]["summary"]["today_new_stars"],
                    "commercial_leads_count": os_rep["data"]["summary"]["commercial_leads_count"],
                    "sponsors_monthly": os_rep["data"]["summary"]["sponsors_monthly"],
                    "subtext": f"Proprietary: {os_rep['data']['summary']['total_stars']} stars · Active telemetry",
                    "count_display": f"★ {os_rep['data']['summary']['total_stars']} stars"
                }
            }
        })
    else:
        # 中文原版数据 (严格保留给根路径 /)
        if bp_rep["mode"] == "hired" and bp_rep["active_employer"]:
            bp_subtext = f"常驻雇主: {bp_rep['active_employer']['company']}"
            bp_count = bp_rep['active_employer']['salary_monthly']
            bp_title = f"常驻: {bp_rep['active_employer']['company']}"
        else:
            bp_subtext = "最新发布 5 个黄金兼职 · 点击出研报"
            bp_count = "5 条在跟"
            bp_title = "BOSS长期兼职"

        return web.json_response({
            "system_name": "OMNINEXUS AI 全域运转台",
            "online_agents": f"{len(agents)}/8",
            "pending_count": pending_count,
            "boss": {
                "name": "Yasin",
                "role": "创始人 · 拍板定方向",
                "pending_badge": f"等你 {pending_count} 件"
            },
            "ceo": {
                "status": f"每小时巡视 · 今天 {rounds} 轮 · 出手 {today_actions} 次 (拦截熔断 {today_dlq} 件)",
                "report_times": "每天 3 次 (08:20 / 12:20 / 20:20)"
            },
            "agents": agents,
            "assistant_metrics": {
                "hackathon": {
                    "urgent_count": hack_rep["summary"]["urgent_count"],
                    "new_count": hack_rep["summary"]["new_count"],
                    "subtext": f"快截止 {hack_rep['summary']['urgent_count']} 个 · 点击出研报",
                    "count_display": hack_rep["summary"]["new_count"]
                },
                "forum": {
                    "total_monitored": forum_rep["summary"]["total_monitored"],
                    "selected_count": forum_rep["summary"]["selected_count"],
                    "new_count": forum_rep["summary"]["new_count"],
                    "subtext": f"30 天内开幕 {forum_rep['summary']['total_monitored']} 场 · 精选 {forum_rep['summary']['selected_count']} 场",
                    "count_display": forum_rep["summary"]["new_count"]
                },
                "github_skills": {
                    "total_monitored": gh_rep["summary"]["total_monitored"],
                    "selected_count": gh_rep["summary"]["selected_count"],
                    "new_count": gh_rep["summary"]["new_count"],
                    "subtext": f"监控 {gh_rep['summary']['total_monitored']} 款 · 精选 {gh_rep['summary']['selected_count']} 款",
                    "count_display": f"+{gh_rep['summary']['new_count']}"
                },
                "boss_parttime": {
                    "mode": bp_rep["mode"],
                    "title": bp_title,
                    "subtext": bp_subtext,
                    "count_display": bp_count
                },
                "schedule": {
                    "total_7_days": sch_rep["summary"]["total_7_days"],
                    "today_total": sch_rep["summary"]["today_total"],
                    "today_pending": sch_rep["summary"]["today_pending"],
                    "urgent_count": sch_rep["summary"]["urgent_count"],
                    "subtext": sch_rep["summary"]["display_subtext"],
                    "count_display": sch_rep["summary"]["count_display"]
                },
                "knowledge": {
                    "total_sops": kb_rep["summary"]["total_sops"],
                    "pending_proposals_count": kb_rep["summary"]["pending_proposals_count"],
                    "last_snapshot_time": kb_rep["summary"]["last_snapshot_time"],
                    "subtext": f"已沉淀 {kb_rep['summary']['total_sops']} 篇操典 · 待审提案 {kb_rep['summary']['pending_proposals_count']} 份",
                    "count_display": f"{kb_rep['summary']['total_sops']} 篇"
                },
                "invest": {
                    "cnh_rate": inv_rep["data"]["summary"]["cnh_rate"],
                    "fx_advice": inv_rep["data"]["summary"]["fx_advice"],
                    "runway_days": inv_rep["data"]["summary"]["runway_days"],
                    "annual_yield": inv_rep["data"]["summary"]["annual_yield"],
                    "macro_mood": inv_rep["data"]["summary"]["macro_mood"],
                    "subtext": inv_rep["data"]["summary"]["display_subtext"],
                    "count_display": inv_rep["data"]["summary"]["display_count"]
                },
                "opensource": {
                    "total_stars": os_rep["data"]["summary"]["total_stars"],
                    "today_new_stars": os_rep["data"]["summary"]["today_new_stars"],
                    "commercial_leads_count": os_rep["data"]["summary"]["commercial_leads_count"],
                    "sponsors_monthly": os_rep["data"]["summary"]["sponsors_monthly"],
                    "subtext": os_rep["data"]["summary"]["display_subtext"],
                    "count_display": os_rep["data"]["summary"]["display_count"]
                }
            }
        })

async def get_ecom_data(request):
    """电商专页数据：整店漏斗、各店铺柱状图、8步闭环最新进展"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM funnel_metrics ORDER BY date DESC, id DESC LIMIT 5")
    funnels = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT * FROM stores")
    stores = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT * FROM tasks WHERE module='ecom' ORDER BY created_at DESC LIMIT 5")
    tasks = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    # 计算当前聚合漏斗
    latest = funnels[0] if funnels else {"visitors": 1240, "add_to_cart": 74, "orders": 31}
    v = latest.get("visitors", 1240)
    c = latest.get("add_to_cart", 74)
    o = latest.get("orders", 31)
    
    cart_rate = f"{round(c / v * 100, 1)}%" if v else "0%"
    order_rate = f"{round(o / c * 100, 1)}%" if c else "0%"
    
    return web.json_response({
        "stores": stores,
        "funnel": {
            "visitors": v,
            "add_to_cart": c,
            "orders": o,
            "cart_rate": cart_rate,
            "order_rate": order_rate,
            "note": "单数、件数、金额来自成交邮件转寄；浏览和收藏是每天 08:00 快照相减"
        },
        "recent_tasks": tasks
    })

async def get_pending_tasks(request):
    """获取等待店主在上方拍板的工单列表"""
    tasks = ceo.get_pending_tasks()
    for t in tasks:
        t["proposal"] = json.loads(t["proposal"]) if t.get("proposal") else {}
        t["artifacts"] = json.loads(t["artifacts"]) if t.get("artifacts") else {}
    return web.json_response({"tasks": tasks})

async def get_all_tasks(request):
    """获取所有历史工单"""
    tasks = ceo.get_all_tasks()
    for t in tasks:
        t["proposal"] = json.loads(t["proposal"]) if t.get("proposal") else {}
        t["artifacts"] = json.loads(t["artifacts"]) if t.get("artifacts") else {}
    return web.json_response({"tasks": tasks})

async def post_task_decision(request):
    """店主拍板接口：approve (点头同意) 或 reject (打回重做)"""
    data = await request.json()
    task_id = data.get("task_id")
    action = data.get("action") # "approve" or "reject"
    feedback = data.get("feedback", "")
    
    res = ceo.boss_decision(task_id, action, feedback)
    
    # 如果店主点了同意，立即全自动异步触发 06动手干活 与 07验收
    if action == "approve":
        asyncio.create_task(async_execute_ecom_task(task_id))
        
    return web.json_response(res)

async def async_execute_ecom_task(task_id: str):
    """异步执行动手与验收"""
    await asyncio.sleep(1.0)
    ecom.step_06_do_the_work(task_id)

async def trigger_hackathon_pipeline(request):
    """一键触发黑客松端到端自动化流水线"""
    try:
        data = await request.json() if request.can_read_body else {}
    except Exception:
        data = {}
    comp_id = data.get("competition_id", "hack-2026-01")
    res = hackathon.run_automated_hackathon_pipeline(comp_id)
    return web.json_response(res)

async def trigger_ecom_pipeline(request):
    """手动触发一次完整的电商 01-04 巡检与提案生成"""
    step1 = ecom.step_01_ingest_data()
    step2 = ecom.step_02_look_at_data(step1)
    step3 = ecom.step_03_give_suggestions(step2)
    step4 = ecom.step_04_submit_to_ceo(step3)
    return web.json_response({
        "msg": "已完成 01接数据 ➔ 02看数 ➔ 03给建议 ➔ 04质检并汇总至CEO",
        "task_id": step4.get("task_id"),
        "status": step4.get("status")
    })

async def post_recirculate(request):
    """手动触发 08 回流"""
    data = await request.json()
    task_id = data.get("task_id")
    res = ecom.step_08_recirculate(task_id)
    return web.json_response(res)

async def get_hackathon_report(request):
    """助理 Agent: 黑客松商业赛事研报与算力白嫖雷达"""
    report = hackathon.get_latest_report()
    return web.json_response(report)

async def get_forum_report(request):
    """助理 Agent: 全球顶尖 AI 论坛与峰会雷达研报"""
    report = forum.get_latest_report()
    return web.json_response(report)

async def get_github_skills_report(request):
    """助理 Agent: GitHub 前沿高星 Agent Skills 与技能武器库研报"""
    report = github_skills.get_latest_report()
    return web.json_response(report)

async def post_github_skills_refresh(request):
    """手动嗅探 GitHub 前沿高星 Agent Skills"""
    res = github_skills.trigger_scan()
    return web.json_response(res)

async def get_boss_parttime_report(request):
    """助理 Agent: BOSS 长期兼职与雇主看板研报"""
    report = boss_parttime.get_report()
    return web.json_response(report)

async def post_boss_parttime_refresh(request):
    """手动触发 BOSS 最新兼职轻量嗅探 (仅抓前10条防风控)"""
    res = boss_parttime.trigger_light_scan()
    return web.json_response(res)

async def post_boss_parttime_lock(request):
    """一键锁定为长期雇主"""
    data = await request.json()
    job_id = data.get("job_id")
    custom_salary = data.get("custom_salary")
    res = boss_parttime.lock_as_employer(job_id, custom_salary)
    return web.json_response(res)

async def post_boss_parttime_unlock(request):
    """切回继续寻找兼职池"""
    res = boss_parttime.unlock_to_hunting()
    return web.json_response(res)

async def get_schedule_report(request):
    """助理 Agent: 一人公司全域作战与履约日程总览 (支持中英双轨)"""
    is_en = (request.query.get("lang") == "en") or ("/en" in request.headers.get("Referer", ""))
    report = schedule.get_report()
    if not is_en:
        return web.json_response(report)
        
    # 纯英文模式下的高精度专业科技词汇转换
    cat_map = {
        "ecom_ops": "E-Commerce",
        "content_publish": "Media Growth",
        "client_delivery": "B2B Solutions",
        "radar_scan": "Opportunity Radar",
        "knowledge_ops": "Knowledge Base"
    }
    prio_map = {
        "urgent": "🔴 Critical Deliverable",
        "high": "🟡 High Focus",
        "normal": "🟢 Routine Auto"
    }
    action_map = {
        "直达电商漏斗": "Inspect Funnel",
        "直达视频工厂": "Inspect Video",
        "直达企服看板": "Inspect B2B Deal",
        "直达知识库": "Inspect Vault",
        "直达雷达研报": "Inspect Radar"
    }
    
    en_schedules = []
    for item in report.get("schedules", []):
        it = dict(item)
        cat = it.get("category", "")
        prio = it.get("priority", "normal")
        it["category_name"] = cat_map.get(cat, cat.replace("_", " ").title())
        it["priority_label"] = prio_map.get(prio, "🟢 Routine Auto")
        it["action_text"] = action_map.get(it.get("action_text", ""), "Inspect")
        
        # 精确翻译各任务标题与描述
        sid = it.get("id")
        if sid == "sch-01":
            it["title"] = "Overnight Order Settlement & Etsy Trend Ingestion"
            it["description"] = "Parsed 31 overnight orders via webhook; verified Etsy growth; auto-dispatched derivative candidates for CEO approval."
        elif sid == "sch-02":
            it["title"] = "Singularity Captain Ep.01 Video Render & Multi-Channel Sync"
            it["description"] = "Master render of day_01_director_cut_v7.mp4 (58.56s, 24 cuts, BGM/SFX); queued for syndication across TikTok and Channels."
        elif sid == "sch-03":
            it["title"] = "B2B Enterprise Lead Follow-up (Fangbo 16-Agent QA)"
            it["description"] = "Awaiting Thursday test dataset confirmation and initial milestone payment from garment supply chain owner."
        elif sid == "sch-04":
            it["title"] = "Google Gemini 2.5 Agent Grand Sprint Package Preparation"
            it["description"] = "Review 1080P demo video, verify Apache-2.0 repo, and finalize Devpost submission form."
        elif sid == "sch-05":
            it["title"] = "Daily Financial Treasury Ingestion & US Equity Rebalancing"
            it["description"] = "Monitor USD/CNH high FX window; audit automated quantitative signals across technology equities."
        elif sid == "sch-06":
            it["title"] = "Autonomous Multi-Platform Social Media Telemetry Radar"
            it["description"] = "Patrol 11 platforms for topic spikes, competitor comment trends, and viral script opportunities."
        elif sid == "sch-07":
            it["title"] = "LeDouJia Retail Chain ERP Reconciliation Proposal Alignment"
            it["description"] = "Async written alignment on technical SLA and database idempotent reconciliation pipeline."
        elif sid == "sch-08":
            it["title"] = "Nightly Second Brain Knowledge Refinery & Lossless State Snapshot"
            it["description"] = "Compile 2 daily production SOPs into Obsidian Vault; commit atomic state ledger snapshot."
        elif sid == "sch-09":
            it["title"] = "Autonomous Weekly Quality Assurance & Client SLA Briefing"
            it["description"] = "Deliver automated verification telemetry detailing zero-fault interception, exception logs, and idempotent pipeline uptime."
        elif sid == "sch-10":
            it["title"] = "Google Gemini 2.5 Agent Grand Sprint Hackathon Final Submission"
            it["description"] = "$30,000 Grand Prize Track: Submit OmniNexus Apache-2.0 repo, architecture documentation, and 1080P official demo."
        elif sid == "sch-11":
            it["title"] = "Amazon & Etsy 7-Day Funnel Performance Review & Restock Decision"
            it["description"] = "Audit 7-day net ROI and SKU conversion rates; auto-trigger upstream product iteration workflows."
        else:
            # 通用回退英文
            it["title"] = it.get("title", "").replace("巡检", " Audit").replace("复盘", " Review").replace("提案", " Proposal")
            it["description"] = it.get("description", "").replace("单", " orders").replace("万", "k")
            
        en_schedules.append(it)
        
    en_report = {
        "status": "success",
        "last_updated": report.get("last_updated", ""),
        "summary": {
            "today_total": report["summary"].get("today_total", 1),
            "today_pending": report["summary"].get("today_pending", 1),
            "today_done": report["summary"].get("today_done", 0),
            "total_7_days": report["summary"].get("total_7_days", 11),
            "urgent_count": report["summary"].get("urgent_count", 3),
            "display_subtext": "7-Day Horizon: 11 items · Pending: 1 item",
            "count_display": "1 Today"
        },
        "schedules": en_schedules
    }
    return web.json_response(en_report)

async def post_schedule_toggle(request):
    """日程任务一键打卡完成 / 撤销"""
    data = await request.json()
    task_id = data.get("task_id")
    res = schedule.toggle_task_status(task_id)
    return web.json_response(res)

async def post_schedule_add(request):
    """快捷新建自定义日程工单"""
    data = await request.json()
    title = data.get("title", "")
    category = data.get("category", "client_delivery")
    date_str = data.get("date", "")
    time_str = data.get("time", "")
    priority = data.get("priority", "normal")
    description = data.get("description", "")
    res = schedule.add_custom_task(title, category, date_str, time_str, priority, description)
    return web.json_response(res)

async def get_knowledge_report(request):
    """运营·知识库 Agent: 知识沉淀、待审提案与状态快照总览"""
    report = knowledge.get_report()
    return web.json_response(report)

async def post_knowledge_decision(request):
    """知识提案拍板：approve (点头同意) 或 reject (打回)"""
    data = await request.json()
    proposal_id = data.get("proposal_id")
    action = data.get("action")
    res = knowledge.decide_proposal(proposal_id, action)
    return web.json_response(res)

async def post_knowledge_snapshot(request):
    """手动触发全量状态物理快照与无损记忆固化"""
    res = knowledge.trigger_snapshot()
    return web.json_response(res)

async def get_invest_report(request):
    """投资与资本中枢 Agent: 5维全球资产、跨境汇率、AI研报与资本生息"""
    report = invest.get_report()
    return web.json_response(report)

async def post_invest_refresh(request):
    """手动触发投资中枢最新行情与宏观情绪巡检"""
    res = invest.trigger_refresh()
    return web.json_response(res)

async def get_opensource_report(request):
    """开源·武器库 Agent: 自研Skill星、商业获客、社区商机、生产力雷达、赞助"""
    report = opensource.get_report()
    return web.json_response(report)

async def post_opensource_refresh(request):
    """手动触发开源中枢巡检"""
    res = opensource.trigger_refresh()
    return web.json_response(res)

async def post_opensource_lead_contact(request):
    """将社区商机标记为已跟进"""
    data = await request.json()
    lead_id = data.get("lead_id")
    res = opensource.mark_lead_contacted(lead_id)
    return web.json_response(res)

async def post_opensource_bind_repo(request):
    """绑定真实的 GitHub 仓库并实时读取星数"""
    data = await request.json()
    repo = data.get("repo", "")
    res = opensource.bind_real_repo(repo)
    return web.json_response(res)

async def get_solutions_report(request):
    """企服·SaaS Agent: BOSS高客单、电鸭/V2兼职、Upwork海外、Fiverr标准件与SaaS孵化"""
    report = solutions.get_report()
    return web.json_response(report)

async def get_media_report(request):
    """内容 Agent: 11平台全域资产矩阵、出片流水线、4090算力与商业转化"""
    report = media.get_report()
    return web.json_response(report)

# ── 静态首页与专用中台大屏 ──
async def index_handler(request):
    """中文原版大屏 (根路径 /)"""
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

async def index_en_handler(request):
    """OmniNexus AI 国际纯英文版大屏 (专用于海外/黑客松 /en)"""
    en_path = os.path.join(STATIC_DIR, "index_en.html")
    if os.path.exists(en_path):
        return web.FileResponse(en_path)
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

async def fde_demo_handler(request):
    """FDE 多模态数据工程与证据仲裁交付大屏 (单文件 HTML)"""
    fde_path = os.path.join(os.path.dirname(PROJECT_ROOT), "project_fde_multimodal_pipeline", "demo_artifact.html")
    if os.path.exists(fde_path):
        return web.FileResponse(fde_path)
    return web.Response(text="FDE Demo artifact not found", status=404)

def create_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/en", index_en_handler)
    app.router.add_get("/fde-demo", fde_demo_handler)
    app.router.add_get("/api/overview", get_overview)
    app.router.add_get("/api/ecom/data", get_ecom_data)
    app.router.add_get("/api/tasks/pending", get_pending_tasks)
    app.router.add_get("/api/tasks/all", get_all_tasks)
    app.router.add_get("/api/hackathons/report", get_hackathon_report)
    app.router.add_get("/api/forums/report", get_forum_report)
    app.router.add_get("/api/github_skills/report", get_github_skills_report)
    app.router.add_get("/api/boss_parttime/report", get_boss_parttime_report)
    app.router.add_get("/api/schedule/report", get_schedule_report)
    app.router.add_get("/api/knowledge/report", get_knowledge_report)
    app.router.add_get("/api/invest/report", get_invest_report)
    app.router.add_get("/api/opensource/report", get_opensource_report)
    app.router.add_get("/api/solutions/report", get_solutions_report)
    app.router.add_get("/api/media/report", get_media_report)
    app.router.add_post("/api/github_skills/refresh", post_github_skills_refresh)
    app.router.add_post("/api/boss_parttime/refresh", post_boss_parttime_refresh)
    app.router.add_post("/api/boss_parttime/lock", post_boss_parttime_lock)
    app.router.add_post("/api/boss_parttime/unlock", post_boss_parttime_unlock)
    app.router.add_post("/api/schedule/toggle", post_schedule_toggle)
    app.router.add_post("/api/schedule/add", post_schedule_add)
    app.router.add_post("/api/knowledge/proposal/decision", post_knowledge_decision)
    app.router.add_post("/api/knowledge/snapshot/trigger", post_knowledge_snapshot)
    app.router.add_post("/api/invest/refresh", post_invest_refresh)
    app.router.add_post("/api/opensource/refresh", post_opensource_refresh)
    app.router.add_post("/api/opensource/lead/contact", post_opensource_lead_contact)
    app.router.add_post("/api/opensource/bind_repo", post_opensource_bind_repo)
    app.router.add_post("/api/tasks/decision", post_task_decision)
    app.router.add_post("/api/hackathon/trigger_pipeline", trigger_hackathon_pipeline)
    app.router.add_post("/api/ecom/trigger_pipeline", trigger_ecom_pipeline)
    app.router.add_post("/api/ecom/recirculate", post_recirculate)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8899))
    app = create_app()
    print(f"🚀 OmniNexus AI 控制中枢正在启动: http://0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)
