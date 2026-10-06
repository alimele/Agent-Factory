"""
Run: python test_phase2.py

Simulates the full 3-stage flow without any network call:
1. Stage 1 — a stand-in for what the LLM would return from the Describe
   page (we don't call the model in offline tests, just build the same
   CoreBlueprintDraft shape generate_core_blueprint() would hand back).
2. Stage 2 — manual picks, pulled from catalog_mvp's department-filtered
   helpers, exactly as a real Knowledge/Actions page would do.
3. Stage 3 — blueprint_compiler.compile_blueprint(), then resolve to the
   Foundry agent-creation payload.

A live end-to-end run (actually calling Stage 1 against your Foundry
deployment) is in run_live_core_call() at the bottom, not run by default.
"""

from api.blueprint.blueprint_generator import build_core_draft_model
from api.blueprint.blueprint_compiler import compile_blueprint, CatalogValidationError
from api.blueprint.foundry_payload import to_foundry_agent_payload
from api.blueprint.catalog_mvp import mvp_catalog_snapshot, knowledge_sources_for_department, tools_for_department


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def test_knowledge_and_action_three_stage():
    catalog = mvp_catalog_snapshot()
    CoreDraft = build_core_draft_model(catalog)

    # Stand-in for Stage 1's LLM output (HR example from the plan doc)
    core = CoreDraft(
        name="HR Leave & Support Agent",
        department="HR",
        agentType="Process Agent",
        pattern="knowledge_action",
        purpose="Answers employee questions about leave policies and raises ServiceNow requests when needed.",
        modelPolicy="approved-general-enterprise",
        dataClassification="HR-Sensitive",
        humanApproval=True,
        externalSharing=False,
    )

    # Stage 2 — what the Knowledge/Actions pages would show, pre-filtered by department
    available_knowledge = knowledge_sources_for_department("HR")
    available_tools = tools_for_department("HR")
    check("HR knowledge page shows the leave source", "HR-SharePoint-Leave" in available_knowledge)
    check("HR actions page shows the ServiceNow tool", "ServiceNow-Create-HR-Request" in available_tools)
    check("HR actions page does NOT show the IT ticket tool", "ServiceNow-Create-IT-Ticket" not in available_tools)

    # user picks from what was shown
    bp = compile_blueprint(
        core_draft=core,
        knowledge_source_ids=["HR-SharePoint-Leave"],
        tool_ids=["ServiceNow-Create-HR-Request"],
        audience_ids=["All-Employees"],
        requester_email="user@customer.com",
    )

    payload = to_foundry_agent_payload(bp)
    tool_types = {t["type"] for t in payload["tools"]}
    check("has file_search tool", "file_search" in tool_types)
    check("has openapi action tool", "openapi" in tool_types)
    print(payload["instructions"])
    print()


def test_rejects_unapproved_id():
    catalog = mvp_catalog_snapshot()
    CoreDraft = build_core_draft_model(catalog)
    core = CoreDraft(
        name="Shady Agent", department="HR", agentType="Process Agent", pattern="process",
        purpose="x", modelPolicy="approved-general-enterprise",
        dataClassification="Internal", humanApproval=True,
    )
    try:
        compile_blueprint(
            core_draft=core,
            knowledge_source_ids=[],
            tool_ids=["Not-A-Real-Tool"],  # e.g. a tampered request
            audience_ids=["All-Employees"],
            requester_email="user@customer.com",
        )
        check("tampered tool id was rejected", False)
    except CatalogValidationError:
        check("tampered tool id was rejected", True)


def test_knowledge_only_no_tools():
    catalog = mvp_catalog_snapshot()
    CoreDraft = build_core_draft_model(catalog)
    core = CoreDraft(
        name="Finance Policy Q&A", department="Finance", agentType="Knowledge Assistant",
        pattern="knowledge_only", purpose="Answers questions about expense policy.",
        modelPolicy="approved-fast-lowcost", dataClassification="Internal", humanApproval=False,
    )
    bp = compile_blueprint(
        core_draft=core,
        knowledge_source_ids=["Finance-SharePoint-Policies"],
        tool_ids=[],
        audience_ids=["Finance-Team"],
        requester_email="user@customer.com",
    )
    payload = to_foundry_agent_payload(bp)
    tool_types = {t["type"] for t in payload["tools"]}
    check("only knowledge tool present", tool_types == {"file_search"})


def run_live_core_call():
    """Not run by default — needs FOUNDRY_PROJECT_ENDPOINT / AZURE_OPENAI_DEPLOYMENT
    set and `az login` done."""
    from blueprint_generator import generate_core_blueprint

    text = (
        "Create an HR agent that answers employee questions about leave policies "
        "and can raise a ServiceNow request when the employee needs HR support."
    )
    core = generate_core_blueprint(text, mvp_catalog_snapshot())
    print(core.model_dump_json(indent=2))


if __name__ == "__main__":
    test_knowledge_and_action_three_stage()
    test_rejects_unapproved_id()
    test_knowledge_only_no_tools()
    print("\nAll offline checks passed.")
