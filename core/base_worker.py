"""
OmniNexus AI - BaseAutonomousWorker 工业级特种兵通用底模 (V4.0)
架构军规：
1. 双态隔离 (Dual-State Isolation)：运行期草稿 Scratchpad 暂存易失内存，裁判通过方可 Commit 入库；
2. 动态双轨门禁 (Stage-Gate Pipeline)：上坡期强制情报感知与红蓝做空，下坡期关闭外部辩论拼物理极速；
3. 自愈循环 (/loop) 与断路器：指数退避重试 (<=3次)，超限打入死信队列 (DLQ) 并通知 CEO；
4. 全局预算熔断水表 (Hard Budget Enforcer)：限制 Token 与调用硬上限；
5. 渐进式信任阶梯 (Trust Ladder)：连续 5 次点头自动升格 FULL_AUTO，打回一次瞬间熔断降级。
"""

import time
import json
import traceback
from typing import Callable, Tuple, Any, Dict
from core.ceo_agent import CEOAgent

class BaseAutonomousWorker:
    def __init__(self, worker_name: str, max_retries: int = 3, max_budget_tokens: int = 50000):
        self.worker_name = worker_name
        self.max_retries = max_retries
        self.max_budget_tokens = max_budget_tokens
        self.consumed_tokens = 0
        self.ceo = CEOAgent()
        self.scratchpad: Dict[str, Any] = {} # 双态隔离草稿

    def record_token_usage(self, tokens: int):
        """记录 Token 水表消耗"""
        self.consumed_tokens += tokens

    def run_with_loop(
        self, 
        task_name: str, 
        execute_fn: Callable, 
        judge_fn: Callable[[Dict[str, Any]], Tuple[bool, str]], 
        *args, **kwargs
    ) -> Dict[str, Any]:
        """
        受控自愈循环 (/loop)：
        - 带着真实报错堆栈最多重试 3 次；
        - 双态隔离：草稿未过绝不入库；
        - 裁判 100% 验收通过后才原子化 Commit。
        """
        retries = 0
        last_error = ""

        while retries <= self.max_retries:
            # 1. 全局预算水表排查
            if self.consumed_tokens > self.max_budget_tokens:
                dlq_res = self.ceo.record_dlq(
                    worker_name=self.worker_name,
                    task_name=task_name,
                    reason=f"Token预算超支熔断 (消耗: {self.consumed_tokens} > 上限: {self.max_budget_tokens})",
                    retry_count=retries
                )
                return {"status": "BUDGET_EXCEEDED", "msg": "Token预算超支，已触发物理断电熔断", "dlq": dlq_res}

            # 2. 物理执行动作 (结果暂存至运行期草稿 Scratchpad)
            try:
                self.scratchpad = execute_fn(*args, **kwargs)
                if not isinstance(self.scratchpad, dict):
                    self.scratchpad = {"raw_output": self.scratchpad}
            except Exception as e:
                stack = traceback.format_exc()
                self.scratchpad = {
                    "error": str(e),
                    "stack": stack,
                    "execution_failed": True
                }

            # 3. 铁面物理外部裁判 (Exit Code + Pydantic + 业务硬断言)
            passed, notes = judge_fn(self.scratchpad)

            if passed:
                # 4. 只有裁判 100% 验收通过，才 Commit 正式提交入库 (防记忆中毒)
                commit_res = self.ceo.commit_task_state(
                    worker_name=self.worker_name,
                    task_name=task_name,
                    payload=self.scratchpad
                )
                return {
                    "status": "SUCCESS", 
                    "notes": notes, 
                    "retries": retries,
                    "data": self.scratchpad, 
                    "commit": commit_res
                }

            # 裁判未通过，准备反思重试
            last_error = notes
            retries += 1
            if retries <= self.max_retries:
                backoff_time = 0.5 * (2 ** (retries - 1)) # 0.5s, 1.0s, 2.0s
                print(f"⚠️ [{self.worker_name}] 任务 '{task_name}' 裁判拦截第 {retries} 次: {notes}，指数退避 {backoff_time:.1f}s 后自愈重跑...")
                time.sleep(backoff_time)

        # 超过上限：打入死信队列 (DLQ)
        dlq_res = self.ceo.record_dlq(
            worker_name=self.worker_name,
            task_name=task_name,
            reason=f"重试超过最大上限 ({self.max_retries}次): {last_error}",
            error_stack=str(self.scratchpad.get("stack", "")),
            retry_count=retries
        )
        return {
            "status": "DEAD_LETTER", 
            "msg": f"任务重试达到上限 ({self.max_retries}次)，已打入死信队列并挂起", 
            "dlq": dlq_res
        }

    def run_stage_gate_pipeline(
        self,
        task_name: str,
        action_name: str,
        uphill_sense_fn: Callable,
        uphill_redteam_fn: Callable[[Dict[str, Any]], Tuple[bool, str]],
        downhill_exec_fn: Callable,
        downhill_judge_fn: Callable[[Dict[str, Any]], Tuple[bool, str]]
    ) -> Dict[str, Any]:
        """
        动态双轨门禁全流程：
        【上坡期】外部感知与红蓝做空 ──> 【人机放权判断】 ──> 【下坡期】物理极速执行与裁判
        """
        # ==================== 【阶段 1：上坡决策期】 ====================
        print(f"\n🧗 [{self.worker_name}] 进入上坡期：执行外部情报感知与红蓝做空审计...")
        sense_data = uphill_sense_fn()
        
        passed_redteam, redteam_notes = uphill_redteam_fn(sense_data)
        if not passed_redteam:
            print(f"🛑 [{self.worker_name}] 上坡红蓝做空门禁拦截：{redteam_notes}")
            return {
                "status": "REJECTED_BY_REDTEAM",
                "reason": redteam_notes,
                "msg": "上坡红蓝做空未通过，提前斩杀止损，绝不进入下坡执行"
            }
        print(f"✅ [{self.worker_name}] 上坡红蓝门禁通过：{redteam_notes}")

        # ==================== 【阶段 2：人机协同与信任阶梯检查】 ====================
        autonomy = self.ceo.get_action_autonomy(action_name)
        level = autonomy.get("autonomy_level", "HUMAN_APPROVAL")
        approvals = autonomy.get("consecutive_approvals", 0)
        print(f"🛡️ [{self.worker_name}] 动作 '{action_name}' 当前信任阶梯：{level} (连续点头: {approvals}次)")

        if level != "FULL_AUTO":
            # 尚未全自动托管：推送到大屏待审批
            task_id = f"{self.worker_name.upper()}-{action_name}-{int(time.time())}"
            proposal_res = self.ceo.submit_proposal_from_worker(
                module=self.worker_name.split("_")[0].lower(),
                task_type=action_name,
                title=f"[{self.worker_name}] {task_name} (待审批)",
                proposal_data={"sense_data": sense_data, "redteam_passed": redteam_notes}
            )
            return {
                "status": "WAITING_HUMAN_APPROVAL",
                "msg": f"信任阶梯未满 5 次 ({approvals}/5)，已生成工单推送到 Tree AI 大屏等店主拍板",
                "proposal": proposal_res
            }

        # ==================== 【阶段 3：下坡极速冲刺期 (FULL_AUTO)】 ====================
        print(f"🚀 [{self.worker_name}] 信任阶梯已达 FULL_AUTO，进入下坡期极速冲刺 (锁死外部辩论)...")
        exec_result = self.run_with_loop(
            task_name=task_name,
            execute_fn=downhill_exec_fn,
            judge_fn=downhill_judge_fn,
            sense_data=sense_data
        )
        return exec_result
