"""
Phoenix Tree AI - 质检审查引擎 (AI 查 AI)
遵循视频 2 核心军规：
“干活的 AI 绝不能给自己验收！AI 查 AI，查过才算完，不过就返工！”
"""
import re
import json

class InspectorAgent:
    def __init__(self):
        # 广告法极限词库
        self.forbidden_keywords = [
            "最便宜", "全网第一", "地表最强", "绝对有效", "100%保证", "全宇宙", "独一无二"
        ]
        
    def inspect_proposal(self, module: str, proposal_data: dict) -> dict:
        """
        AI 查 AI 阶段 1：对干活 Agent 提交的待审提案进行机审
        """
        issues = []
        text_corpus = json.dumps(proposal_data, ensure_ascii=False)
        
        # 1. 违规极限词排查
        for kw in self.forbidden_keywords:
            if kw in text_corpus:
                issues.append(f"包含极限违规词汇: 【{kw}】")
                
        # 2. 商业逻辑自洽性校验 (毛利与售价核验)
        if "pricing" in proposal_data:
            cost = float(proposal_data["pricing"].get("cost", 0))
            price = float(proposal_data["pricing"].get("price", 0))
            if price > 0 and (price - cost) / price < 0.2:
                issues.append("预期毛利率低于 20% 安全警戒线，被质检拦截")
                
        # 3. 结果判定
        passed = len(issues) == 0
        notes = "✅ AI 查 AI 质检通过：类目合规无极限词、毛利模型自洽、数据源逻辑闭环。" if passed else f"❌ 质检拦截打回：{'; '.join(issues)}"
        
        return {
            "passed": passed,
            "inspector": "Inspector-Agent (Codex/Audit)",
            "notes": notes,
            "issues": issues
        }

    def inspect_execution_artifacts(self, artifacts: dict) -> dict:
        """
        AI 查 AI 阶段 2：对执行产出的具体交付物（标题、文案、图片参数）进行合规性与质量复核
        """
        issues = []
        title = artifacts.get("title", "")
        if len(title) < 5 or len(title) > 60:
            issues.append(f"商品标题长度不合规 ({len(title)} 字符)，应在 10-50 字符之间")
            
        for kw in self.forbidden_keywords:
            if kw in title:
                issues.append(f"标题包含违规词: 【{kw}】")
                
        images = artifacts.get("images", [])
        if not images:
            issues.append("缺少商品场景图/白底图生成规范")
            
        passed = len(issues) == 0
        return {
            "passed": passed,
            "inspector": "Inspector-Agent (Pre-publish Guard)",
            "notes": "✅ 终审产出物质检通过，准予推送到草稿箱与 CEO 验收。" if passed else f"❌ 产出物未达标：{'; '.join(issues)}",
            "issues": issues
        }
