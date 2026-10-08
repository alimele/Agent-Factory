"""
The 14-point governance checklist from the project plan (section 6),
as individual, independently testable functions.

Each rule takes the compiled blueprint dict + EvalContext and returns
a CheckResult. Rules never raise for a policy failure — fail/flag is
a normal result, not an exception. Only genuine bad input should raise.
"""
from api.policy.catalogs import approved_knowledge_ids, approved_tool_ids, unapproved
from api.policy.models import CheckResult, CheckStatus, EvalContext, Stage

RESTRICTED_DATA_CLASSES = {"Security-Restricted"}
SENSITIVE_DATA_CLASSES = {"Confidential", "HR-Sensitive", "Financial"}
WRITE_ACTION_HINTS = ("create", "update", "delete", "approve", "transfer", "send")


def check_identity(bp: dict, ctx: EvalContext) -> CheckResult:
    ok = bool(ctx.requester_id)
    return CheckResult(id="identity", name="Identity",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else "No authenticated requester on the request")


def check_department(bp: dict, ctx: EvalContext) -> CheckResult:
    if ctx.requester_department is None:
        return CheckResult(id="department", name="Department", status=CheckStatus.SKIPPED,
                            reason="Requester department not wired yet")
    ok = ctx.requester_department == bp.get("department")
    return CheckResult(id="department", name="Department",
                        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                        reason="" if ok else f"Requester is not in {bp.get('department')}")


def check_model(bp: dict, ctx: EvalContext) -> CheckResult:
    allowed = {"approved-general-enterprise"}  # extend as you add model policies
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
    tools = [t.lower() for t in (bp.get("tools") or [])]
    writes = [t for t in tools if any(h in t for h in WRITE_ACTION_HINTS)]
    if not writes:
        return CheckResult(id="actions", name="Actions", status=CheckStatus.PASS, reason="")
    return CheckResult(id="actions", name="Actions", status=CheckStatus.FLAGGED,
                        reason=f"State-changing tools present: {writes}")


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
