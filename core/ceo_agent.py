"""
OmniNexus AI - CEO Agent 调度与流程参谋中枢
原则：
- 店主只跟 CEO 讲，干活的 AI 不直接找店主；
- 几条建议合成一份，每天按点报店主；
- 店主点了头，再交给干活的 AI；干完对着要求查 (07验收)；查过才算完，不过就返工。
"""
import json
import uuid
import threading
from datetime import datetime
from database.models import get_db
from core.inspector_agent import InspectorAgent

inspector = InspectorAgent()

class CEOAgent:
    def __init__(self):
        self.inspector = inspector
        
    def submit_proposal_from_worker(self, module: str, task_type: str, title: str, proposal_data: dict) -> dict:
        """
        接收干活 Worker 提交的建议，先交给质检 Agent (AI 查 AI)，合格后由 CEO 挂牌到【待办事项】
        """
        # 1. AI 查 AI：自动审查
        inspection = self.inspector.inspect_proposal(module, proposal_data)
        
        task_id = f"{module.upper()}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4]}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = get_db()
        cur = conn.cursor()
        
        if inspection["passed"]:
            status = "PENDING_APPROVAL" # 等店主在上方拍板
            cur.execute("""
            INSERT INTO tasks (task_id, module, task_type, title, proposal, status, inspector_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_id, module, task_type, title, json.dumps(proposal_data, ensure_ascii=False),
                  status, inspection["notes"], now_str, now_str))
            
            # 更新 CEO Agent 活跃指标
            cur.execute("UPDATE agent_status SET status='working' WHERE agent_id='ceo'")
            conn.commit()
            conn.close()
            return {"task_id": task_id, "status": status, "msg": "质检通过，已推送到【待办】等店主拍板"}
        else:
            status = "REWORK" # 质检不通过，底层直接打回，不打扰店主
            cur.execute("""
            INSERT INTO tasks (task_id, module, task_type, title, proposal, status, inspector_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_id, module, task_type, title, json.dumps(proposal_data, ensure_ascii=False),
                  status, inspection["notes"], now_str, now_str))
            conn.commit()
            conn.close()
            return {"task_id": task_id, "status": status, "msg": f"AI 查 AI 拦截：{inspection['notes']}"}

    def boss_decision(self, task_id: str, action: str, feedback: str = "") -> dict:
        """
        店主在上方拍板：action = 'approve' (点头同意) 或 'reject' (打回重做)
        """
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task = cur.fetchone()
        if not task:
            conn.close()
            return {"error": "未找到工单"}
            
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        module = task["module"] if "module" in task.keys() else "ecom"
        action_name = f"{module}_{task['task_type']}"
        
        if action == "approve":
            # 店主点头，CEO 派活给干活的 AI (状态流转为 APPROVED -> EXECUTING)
            cur.execute("""
            UPDATE tasks SET status='APPROVED', boss_feedback=?, updated_at=? WHERE task_id=?
            """, ("店主已批准", now_str, task_id))
            conn.commit()
            conn.close()
            
            # 更新信任阶梯 (连续通过递增)
            self.update_trust_ladder(action_name, approved=True)

            # 🚀 自动化物理联动：如果是黑客松工单，自动唤起真机 Chrome 浏览器执行报名与凭证捕获
            if task.get("task_type") == "hackathon_submission":
                try:
                    from workers.hackathon_browser_runner import run_live_hackathon_registration
                    t = threading.Thread(
                        target=run_live_hackathon_registration,
                        args=(task_id,),
                        daemon=True
                    )
                    t.start()
                    return {"status": "APPROVED", "msg": "店主已点头拍板！本地 Google Chrome 浏览器已自动唤起，正在真机执行官方报名与凭证捕获！"}
                except Exception as e:
                    print(f"唤醒浏览器自动化异常: {e}")

            return {"status": "APPROVED", "msg": "店主已点头拍板，CEO Agent 正在派活执行"}
            
        elif action == "reject":
            # 店主打回重做，附带修改批注
            cur.execute("""
            UPDATE tasks SET status='REWORK', boss_feedback=?, updated_at=? WHERE task_id=?
            """, (feedback or "方案未达预期，请结合反馈重新优化", now_str, task_id))
            conn.commit()
            conn.close()
            
            # 信任阶梯熔断退行 (连续通过清零)
            self.update_trust_ladder(action_name, approved=False)
            return {"status": "REWORK", "msg": "已打回给干活 Agent，正在吸取意见重做第二版"}
            
        conn.close()
        return {"error": "未知动作"}

    def record_dlq(self, worker_name: str, task_name: str, reason: str, error_stack: str = "", retry_count: int = 3, task_id: str = "") -> dict:
        """记录死信队列 (DLQ)，防止无限重试与 Token 暴击"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO dead_letter_queue (task_id, worker_name, task_name, reason, error_stack, retry_count, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?)
        """, (task_id or f"DLQ-{uuid.uuid4().hex[:6]}", worker_name, task_name, reason, error_stack, retry_count, now_str))
        conn.commit()
        conn.close()
        return {"status": "RECORDED_IN_DLQ", "reason": reason}

    def commit_task_state(self, worker_name: str, task_name: str, payload: dict, status: str = "COMPLETED") -> dict:
        """双态隔离：只有外部裁判 100% 通过后，才调用 commit 原子入库"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_id = f"{worker_name.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO tasks (task_id, module, task_type, title, proposal, status, inspector_notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, '物理外部裁判 100% 验收通过并已 Commit', ?, ?)
        """, (task_id, worker_name.split("_")[0].lower(), "autonomous_execution", f"[{worker_name}] {task_name}",
              json.dumps(payload, ensure_ascii=False), status, now_str, now_str))
        conn.commit()
        conn.close()
        return {"task_id": task_id, "status": status}

    def get_action_autonomy(self, action_name: str) -> dict:
        """查询动作的渐进式信任阶梯状态"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM agent_permissions WHERE action_name = ?", (action_name,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"action_name": action_name, "consecutive_approvals": 0, "autonomy_level": "HUMAN_APPROVAL"}
        return dict(row)

    def update_trust_ladder(self, action_name: str, approved: bool):
        """渐进式授权更新：连续通过 5 次升级为 FULL_AUTO；打回一次瞬间清零退行"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT consecutive_approvals, autonomy_level FROM agent_permissions WHERE action_name = ?", (action_name,))
        row = cur.fetchone()
        
        if not row:
            curr_cnt = 0
        else:
            curr_cnt = row["consecutive_approvals"]

        if approved:
            new_cnt = curr_cnt + 1
            new_level = "FULL_AUTO" if new_cnt >= 5 else "HUMAN_APPROVAL"
        else:
            new_cnt = 0
            new_level = "HUMAN_APPROVAL"

        cur.execute("""
        INSERT INTO agent_permissions (action_name, worker_name, consecutive_approvals, autonomy_level, last_evaluated)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(action_name) DO UPDATE SET
            consecutive_approvals = excluded.consecutive_approvals,
            autonomy_level = excluded.autonomy_level,
            last_evaluated = excluded.last_evaluated
        """, (action_name, action_name.split("_")[0], new_cnt, new_level, now_str))
        conn.commit()
        conn.close()

    def get_pending_tasks(self):
        """获取所有待店主审批的工单"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE status = 'PENDING_APPROVAL' ORDER BY created_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_all_tasks(self):
        """获取所有历史工单"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
