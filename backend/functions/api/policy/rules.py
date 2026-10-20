"""
Each rule takes the compiled blueprint dict + EvalContext and returns
a CheckResult. Rules never raise for a policy failure — fail/flag is
a normal result, not an exception. Only genuine bad input should raise.
"""
from api.blueprint.catalog_mvp import MODEL_POLICIES, READ_ONLY_AGENT_TYPES
from api.policy.catalogs import approved_knowledge_ids, approved_tool_ids, tool_risk_levels, unapproved
from api.policy.models import CheckResult, CheckStatus, EvalContext, Stage

RESTRICTED_DATA_CLASSES = {"Security-Restricted"}
SENSITIVE_DATA_CLASSES = {"Confidential", "HR-Sensitive", "Financial"}

# A tool only counts as "read-only" when the API Center catalog actually
# says risk="low". Anything else — medium/high/critical, or "unknown"
# because the tool id didn't resolve in the catalog at all — is treated as
# write-capable. Fail-safe: an unresolvable tool is never assumed harmless.
READ_ONLY_RISK = "low"


def check_identity(bp: dict, ctx: EvalContext) -> CheckResult:
    ok = bool(ctx.requester_id)
    return CheckResult(id="identity", name="Identity",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else "No authenticated requester on the request")


def check_department(bp: dict, ctx: EvalContext) -> CheckResult:
    departments = ctx.requester_departments
    if not departments:
        return CheckResult(id="department", name="Department", status=CheckStatus.FAIL,
                            reason="Requester has no approved department access configured")
    ok = bp.get("department") in departments
    return CheckResult(id="department", name="Department",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else f"Requester is not approved for department '{bp.get('department')}'")

def check_model(bp: dict, ctx: EvalContext) -> CheckResult:
    # Pulled from the live catalog instead of a hardcoded set, so adding a
    # model policy to catalog_mvp.MODEL_POLICIES is enough on its own — no
    # second place to remember to update.
    allowed = set(MODEL_POLICIES.keys())
    ok = bp.get("modelPolicy") in allowed
    return CheckResult(id="model", name="Model",
                        status=CheckStatus.PASS if ok else CheckStatus.FLAGGED,
                        reason="" if ok else f"modelPolicy '{bp.get('modelPolicy')}' not in approved set")


def check_knowledge(bp: dict, ctx: EvalContext) -> CheckResult:
    selected = bp.get("knowledgeSources") or []
    if not selected:
        return CheckResult(id="knowledge", name="Knowledge", status=CheckStatus.PASS,
                            reason="No knowledge sources selected")
    approved = approved_knowledge_ids(bp["department"])
    bad = unapproved(selected, approved)
    ok = not bad
    return CheckResult(id="knowledge", name="Knowledge",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else f"Not in approved catalog: {bad}")


def check_tools(bp: dict, ctx: EvalContext) -> CheckResult:
    selected = bp.get("tools") or []
    if not selected:
        return CheckResult(id="tools", name="Tools", status=CheckStatus.PASS,
                            reason="No tools selected")
    approved = approved_tool_ids(bp["department"])
    bad = unapproved(selected, approved)
    ok = not bad
    return CheckResult(id="tools", name="Tools",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else f"Not in approved catalog: {bad}")


def check_permissions(bp: dict, ctx: EvalContext) -> CheckResult:
    # Crude "minimum necessary" signal until per-tool scopes exist.
    tool_count = len(bp.get("tools") or [])
    ok = tool_count <= 5
    return CheckResult(id="permissions", name="Permissions",
                        status=CheckStatus.PASS if ok else CheckStatus.FLAGGED,
                        reason="" if ok else f"{tool_count} tools requested — review for least privilege")


def check_data_sensitivity(bp: dict, ctx: EvalContext) -> CheckResult:
    cls = bp.get("dataClassification", "Internal")
    if cls in RESTRICTED_DATA_CLASSES:
        return CheckResult(id="data", name="Data", status=CheckStatus.FAIL,
                            reason=f"Data classification '{cls}' is restricted")
    if cls in SENSITIVE_DATA_CLASSES:
        return CheckResult(id="data", name="Data", status=CheckStatus.FLAGGED,
                            reason=f"Sensitive data classification '{cls}'")
    return CheckResult(id="data", name="Data", status=CheckStatus.PASS, reason="")


def check_actions(bp: dict, ctx: EvalContext) -> CheckResult:
    tools = bp.get("tools") or []
    if not tools:
        return CheckResult(id="actions", name="Actions", status=CheckStatus.PASS, reason="")
    risk_by_tool = tool_risk_levels(bp["department"], tools)
    writes = [t for t in tools if risk_by_tool.get(t, "unknown").lower() != READ_ONLY_RISK]
    if not writes:
        return CheckResult(id="actions", name="Actions", status=CheckStatus.PASS, reason="")
    return CheckResult(
        id="actions", name="Actions", status=CheckStatus.FLAGGED,
        reason=f"Tools with elevated risk present: {[(t, risk_by_tool.get(t, 'unknown')) for t in writes]}",
    )


def check_agent_type(bp: dict, ctx: EvalContext) -> CheckResult:
    agent_type = bp.get("agentType")
    if agent_type not in READ_ONLY_AGENT_TYPES:
        return CheckResult(id="agent_type", name="Agent type", status=CheckStatus.PASS, reason="")
    tools = bp.get("tools") or []
    if not tools:
        return CheckResult(id="agent_type", name="Agent type", status=CheckStatus.PASS, reason="")
    return CheckResult(
        id="agent_type", name="Agent type", status=CheckStatus.FAIL,
        reason=f"'{agent_type}' agents must not have action tools attached; found: {tools}",
    )


def check_human_in_loop(bp: dict, ctx: EvalContext) -> CheckResult:
    has_writes = check_actions(bp, ctx).status == CheckStatus.FLAGGED
    ok = (not has_writes) or bp.get("humanApproval") is True
    return CheckResult(id="human_in_loop", name="Human-in-the-loop",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else "Write-capable agent without humanApproval set")


def check_external_access(bp: dict, ctx: EvalContext) -> CheckResult:
    ok = bp.get("externalSharing") is not True
    return CheckResult(id="external_access", name="External access",
                        status=CheckStatus.PASS if ok else CheckStatus.FLAGGED,
                        reason="" if ok else "externalSharing is enabled")


def check_network(bp: dict, ctx: EvalContext) -> CheckResult:
    # MVP: Foundry project already sits on private networking at the
    # resource level — nothing per-agent to check yet. Revisit if/when
    # per-agent network policy exists.
    return CheckResult(id="network", name="Network", status=CheckStatus.SKIPPED,
                        reason="Enforced at Foundry project level, not per-agent yet")


def check_evaluation(bp: dict, ctx: EvalContext, stage: Stage) -> CheckResult:
    if stage != Stage.PRE_PUBLISH:
        return CheckResult(id="evaluation", name="Evaluation", status=CheckStatus.SKIPPED,
                            reason="Evaluated after Test/red-team, before publish")
    results = ctx.test_results or {}
    passed = results.get("passed", 0)
    total = results.get("total", 0)
    ok = total > 0 and passed == total
    return CheckResult(id="evaluation", name="Evaluation",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else f"{passed}/{total} test cases passed")


def check_ownership(bp: dict, ctx: EvalContext) -> CheckResult:
    ok = bool(bp.get("owner"))
    return CheckResult(id="ownership", name="Ownership",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else "No owner set on blueprint")


def check_lifecycle(bp: dict, ctx: EvalContext) -> CheckResult:
    ok = bool(bp.get("reviewPeriodDays"))
    return CheckResult(id="lifecycle", name="Lifecycle",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else "No reviewPeriodDays set on blueprint")
