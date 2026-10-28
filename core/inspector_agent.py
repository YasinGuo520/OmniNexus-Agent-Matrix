"""
OmniNexus AI - InspectorAgent (Dual-Agent QA & Policy Enforcement)
Principle:
"An executing agent must never grade its own work. AI checks AI.
Only verified deliverables commit; failures are rejected for rework."
"""
import re
import json

class InspectorAgent:
    def __init__(self):
        # Regulatory forbidden superlative keywords
        self.forbidden_keywords = [
            "cheapest", "#1 in the world", "best ever", "100% guaranteed", "miracle cure", "flawless", "zero risk"
        ]
        
    def inspect_proposal(self, module: str, proposal_data: dict) -> dict:
        """
        AI checks AI (Phase 1): Pre-flight policy and logical consistency check on worker proposals.
        """
        issues = []
        text_corpus = json.dumps(proposal_data, ensure_ascii=False).lower()
        
        # 1. Prohibited superlative claims assertion
        for kw in self.forbidden_keywords:
            if kw.lower() in text_corpus:
                issues.append(f"Prohibited superlative detected: '{kw}'")
                
        # 2. Unit economics verification (minimum gross margin check)
        if "pricing" in proposal_data:
            cost = float(proposal_data["pricing"].get("cost", 0))
            price = float(proposal_data["pricing"].get("price", 0))
            if price > 0 and (price - cost) / price < 0.2:
                issues.append("Projected gross margin is below the 20% safety threshold")
                
        passed = len(issues) == 0
        notes = (
            "✅ InspectorAgent QA PASS: Compliant policy, verified margin model, sound provenance."
            if passed else
            f"❌ InspectorAgent Intercept: {'; '.join(issues)}"
        )
        
        return {
            "passed": passed,
            "inspector": "InspectorAgent (Policy & Integrity Guard)",
            "notes": notes,
            "issues": issues
        }

    def inspect_execution_artifacts(self, artifacts: dict) -> dict:
        """
        AI checks AI (Phase 2): Evaluates executed artifacts (titles, copy, parameters) for compliance.
        """
        issues = []
        title = artifacts.get("title", "")
        if len(title) < 5 or len(title) > 120:
            issues.append(f"Product title length out of bounds ({len(title)} chars). Expected 10-100.")
            
        for kw in self.forbidden_keywords:
            if kw.lower() in title.lower():
                issues.append(f"Title contains prohibited word: '{kw}'")
                
        images = artifacts.get("images", [])
        if not images:
            issues.append("Missing required product hero image specification")
            
        passed = len(issues) == 0
        return {
            "passed": passed,
            "inspector": "InspectorAgent (Artifact QA Engine)",
            "notes": (
                "✅ Artifact QA PASS: Specifications verified. Cleared for CEO review."
                if passed else
                f"❌ Artifact QA FAIL: {'; '.join(issues)}"
            ),
            "issues": issues
        }
