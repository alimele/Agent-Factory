"""
Policy engine entrypoint. Runs the checklist, rolls it up into an
overall status, and maps the result to a risk tier + approval route
per the project plan's approval model.
"""
from api.policy.models import CheckResult, CheckStatus, EvalContext, PolicyEvaluation, RiskTier, Stage
from . import rules

ALL_RULES = [
    rules.check_identity,
    rules.check_department,
    rules.check_model,
    rules.check_knowledge,
    rules.check_tools,
    rules.check_permissions,
    rules.check_data_sensitivity,
    rules.check_actions,
    rules.check_human_in_loop,
    rules.check_external_access,
    rules.check_network,
    rules.check_ownership,
    rules.check_lifecycle,
]


def _run_checks(bp: dict, ctx: EvalContext, stage: Stage) -> list[CheckResult]:
    results = [r(bp, ctx) for r in ALL_RULES]
    results.append(rules.check_evaluation(bp, ctx, stage))
    return results


def _risk_tier(bp: dict, checks: list[CheckResult]) -> RiskTier:
    by_id = {c.id: c for c in checks}
    data_status = by_id["data"].status
    actions_status = by_id["actions"].status

    if data_status == CheckStatus.FAIL or bp.get("dataClassification") == "Restricted":
        return RiskTier.RESTRICTED
    if data_status == CheckStatus.FLAGGED or actions_status == CheckStatus.FLAGGED:
        if bp.get("dataClassification") in ("HR-Sensitive", "Financial", "Security"):
            return RiskTier.HIGH
        return RiskTier.MEDIUM
    if data_status == CheckStatus.PASS and actions_status == CheckStatus.PASS:
        return RiskTier.LOW
    return RiskTier.MEDIUM


APPROVAL_ROUTES = {
    RiskTier.LOW: ["department_owner"],
    RiskTier.MEDIUM: ["department_owner", "security_policy"],
    RiskTier.HIGH: ["business_owner", "security_privacy", "ai_platform"],
    RiskTier.RESTRICTED: ["engineering_review"],
}


def _overall_status(checks: list[CheckResult], risk_tier: RiskTier) -> CheckStatus:
    if risk_tier == RiskTier.RESTRICTED or any(c.status == CheckStatus.FAIL for c in checks):
        return CheckStatus.FAIL
    if any(c.status == CheckStatus.FLAGGED for c in checks):
        return CheckStatus.FLAGGED
    return CheckStatus.PASS


def evaluate(blueprint: dict, context: EvalContext, stage: Stage,
             blueprint_id: str | None = None) -> PolicyEvaluation:
    checks = _run_checks(blueprint, context, stage)
    risk_tier = _risk_tier(blueprint, checks)
    overall = _overall_status(checks, risk_tier)
    return PolicyEvaluation(
        blueprint_id=blueprint_id,
        stage=stage,
        overall_status=overall,
        risk_tier=risk_tier,
        required_approvers=APPROVAL_ROUTES[risk_tier],
        checks=checks,
    )
