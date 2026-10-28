"""
OmniNexus AI - BaseAutonomousWorker Production Engine (V4.0)
Architecture Pillars:
1. Dual-State Scratchpad Isolation: Transient in-memory scratchpad during execution; committed only after judge assertion.
2. Dynamic Stage-Gate Pipeline: Uphill exploration & red-team auditing -> Governance Trust Ladder -> Downhill deterministic execution.
3. Controlled Self-Healing Loop (/loop): Exponential backoff retry (<=3x), routed to Dead-Letter Queue (DLQ) upon exhaustion.
4. Hard Budget Enforcement: Real-time token consumption metering & threshold circuit breaker.
5. Progressive Trust Ladder: 5 consecutive human approvals grant FULL_AUTO status; single rejection triggers instant downgrade.
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
        self.scratchpad: Dict[str, Any] = {} # Dual-state transient scratchpad

    def record_token_usage(self, tokens: int):
        """Track and increment token consumption against budget"""
        self.consumed_tokens += tokens

    def run_with_loop(
        self, 
        task_name: str, 
        execute_fn: Callable, 
        judge_fn: Callable[[Dict[str, Any]], Tuple[bool, str]], 
        *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Controlled Self-Healing Loop (/loop):
        - Retries up to max_retries with stack trace capture and exponential backoff;
        - Enforces dual-state isolation (unverified drafts never touch persistent state);
        - Atomic commit only when the outside physical judge asserts 100% PASS.
        """
        retries = 0
        last_error = ""

        while retries <= self.max_retries:
            # 1. Global token budget assertion
            if self.consumed_tokens > self.max_budget_tokens:
                dlq_res = self.ceo.record_dlq(
                    worker_name=self.worker_name,
                    task_name=task_name,
                    reason=f"Token budget threshold exceeded (Consumed: {self.consumed_tokens} > Limit: {self.max_budget_tokens})",
                    retry_count=retries
                )
                return {
                    "status": "BUDGET_EXCEEDED", 
                    "msg": "Hard token budget limit tripped. Circuit breaker active.", 
                    "dlq": dlq_res
                }

            # 2. Physical execution (stored in ephemeral scratchpad)
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

            # 3. Outside Physical Judge Assertion (Exit Code + Pydantic Schema + Invariants)
            passed, notes = judge_fn(self.scratchpad)

            if passed:
                # 4. Atomic commit to persistent ledger upon verification
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

            # Judge intercept: prepare for self-healing reflection
            last_error = notes
            retries += 1
            if retries <= self.max_retries:
                backoff_time = 0.5 * (2 ** (retries - 1)) # 0.5s, 1.0s, 2.0s
                print(f"⚠️ [{self.worker_name}] Task '{task_name}' intercepted by Outside Judge (Attempt {retries}): {notes}. Retrying with exponential backoff ({backoff_time:.1f}s)...")
                time.sleep(backoff_time)

        # Retry threshold exhausted: divert to Dead-Letter Queue (DLQ)
        dlq_res = self.ceo.record_dlq(
            worker_name=self.worker_name,
            task_name=task_name,
            reason=f"Max retry limit exhausted ({self.max_retries} retries): {last_error}",
            error_stack=str(self.scratchpad.get("stack", "")),
            retry_count=retries
        )
        return {
            "status": "DEAD_LETTER", 
            "msg": f"Task exceeded max retry limit ({self.max_retries}). Diverted to Dead-Letter Queue.", 
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
        Dynamic Stage-Gate Pipeline:
        [Uphill Stage] Environmental Sensing & Red-Team Audit -> 
        [Trust Ladder Check] HITL Governance Gate -> 
        [Downhill Stage] Deterministic High-Speed Execution & Outside Judge
        """
        # ==================== Phase 1: Uphill Exploration & Red-Teaming ====================
        print(f"\n🧗 [{self.worker_name}] Entering Uphill Phase: Environmental sensing & red-team audit...")
        sense_data = uphill_sense_fn()
        
        passed_redteam, redteam_notes = uphill_redteam_fn(sense_data)
        if not passed_redteam:
            print(f"🛑 [{self.worker_name}] Uphill Red-Team Gate Intercept: {redteam_notes}")
            return {
                "status": "REJECTED_BY_REDTEAM",
                "reason": redteam_notes,
                "msg": "Uphill red-team validation failed. Aborting pipeline before execution."
            }
        print(f"✅ [{self.worker_name}] Uphill Red-Team Gate PASSED: {redteam_notes}")

        # ==================== Phase 2: Progressive Trust Ladder Check ====================
        autonomy = self.ceo.get_action_autonomy(action_name)
        level = autonomy.get("autonomy_level", "HUMAN_APPROVAL")
        approvals = autonomy.get("consecutive_approvals", 0)
        print(f"🛡️ [{self.worker_name}] Action '{action_name}' Trust Ladder Level: {level} ({approvals} consecutive approvals)")

        if level != "FULL_AUTO":
            # Action requires human sign-off: dispatch to Executive HUD
            task_id = f"{self.worker_name.upper()}-{action_name}-{int(time.time())}"
            proposal_res = self.ceo.submit_proposal_from_worker(
                module=self.worker_name.split("_")[0].lower(),
                task_type=action_name,
                title=f"[{self.worker_name}] {task_name} (Pending Approval)",
                proposal_data={"sense_data": sense_data, "redteam_passed": redteam_notes}
            )
            return {
                "status": "WAITING_HUMAN_APPROVAL",
                "msg": f"Trust threshold pending ({approvals}/5). Proposal dispatched to Executive HITL HUD.",
                "proposal": proposal_res
            }

        # ==================== Phase 3: Downhill Execution (FULL_AUTO) ====================
        print(f"🚀 [{self.worker_name}] Trust Ladder at FULL_AUTO. Commencing downhill execution...")
        exec_result = self.run_with_loop(
            task_name=task_name,
            execute_fn=downhill_exec_fn,
            judge_fn=downhill_judge_fn,
            sense_data=sense_data
        )
        return exec_result
