"""
MVP catalogs — 5-10 tools, a handful of knowledge sources, matching the
"5-8 agent templates / 5-10 tools" MVP scope in the project plan (section 9).

TODO before Phase 4: replace the placeholder `tool_resource` / `foundry_tool`
values below with real Azure resource ids once they're provisioned
(vector store ids for AI Search indexes, APIM/connection ids for ServiceNow
etc). The *shape* is correct now; the ids are stubs so Phase 2 can be built
and tested independently of Phase 4 provisioning.
"""

from api.blueprint.blueprint_schema import CatalogSnapshot

DEPARTMENTS = ["HR", "Finance", "DevSecOps", "IT Support", "Admin", "Sales"]

AGENT_TYPES = [
    "Knowledge Assistant", "Analyst", "Process Agent", "Action Agent", "Monitoring Agent",
]

PATTERNS = ["knowledge_only", "knowledge_action", "process", "monitoring"]

MODEL_POLICIES = {
    # internal policy name -> your Azure OpenAI DEPLOYMENT name in Foundry
    # (not a bare model id — Azure OpenAI routes by deployment name, and
    # you choose that name yourself when you deploy in the portal). These
    # are placeholders: confirm what you actually deploy and rename to match.
    "approved-general-enterprise": "gpt-5",
    "approved-high-accuracy": "gpt-5-pro",
    "approved-fast-lowcost": "gpt-5-mini",
}

DATA_CLASSIFICATIONS = [
    "Public", "Internal", "Confidential", "HR-Sensitive", "Financial", "Security-Restricted",
]

CHANNELS = ["Teams", "M365Copilot"]

AUDIENCES = {
    "All-Employees": {"entra_group_id": "TODO-group-id-all-employees"},
    "HR-Team": {"entra_group_id": "TODO-group-id-hr"},
    "Finance-Team": {"entra_group_id": "TODO-group-id-finance"},
    "IT-Support-Team": {"entra_group_id": "TODO-group-id-it-support"},
}

# Knowledge sources resolve to a file_search or azure_ai_search Foundry tool.
KNOWLEDGE_CATALOG = {
    "HR-SharePoint-Leave": {
        "display_name": "HR SharePoint — Leave Policies",
        "department": ["HR"],
        "data_classification": "HR-Sensitive",
        "foundry_tool_type": "file_search",
        "tool_resource": {"file_search": {"vector_store_ids": ["TODO-vector-store-id-hr-leave"]}},
    },
    "Finance-SharePoint-Policies": {
        "display_name": "Finance SharePoint Policies",
        "department": ["Finance"],
        "data_classification": "Internal",
        "foundry_tool_type": "file_search",
        "tool_resource": {"file_search": {"vector_store_ids": ["TODO-vector-store-id-finance-policies"]}},
    },
    "IT-KB-AzureSearch": {
        "display_name": "IT Knowledge Base",
        "department": ["IT Support"],
        "data_classification": "Internal",
        "foundry_tool_type": "foundry_iq",
        "tool_resource": {
            "knowledge_base": {
                "name": "knowledgebase107",
                "knowledge_source": "ks-searchindex-458",
                "search_service" : "alimele2378-0871-srch-65s4",
                "index_name": "rag-1790607218889"
                }},
    },
}

# Action tools resolve to a function / openapi / built-in Foundry tool.
TOOL_CATALOG = {
    "ServiceNow-Create-HR-Request": {
        "display_name": "Create ServiceNow HR Request",
        "department": ["HR"],
        "risk": "medium",
        "foundry_tool": {
            "type": "openapi",
            "openapi": {
                "name": "servicenow_create_hr_request",
                "description": "Create a ServiceNow HR support ticket on behalf of an employee",
                "spec_ref": "TODO-path-or-url-to-openapi-spec.json",
                "auth": {"type": "connection", "connection_id": "TODO-apim-connection-id-servicenow"},
            },
        },
    },
    "ServiceNow-Create-IT-Ticket": {
        "display_name": "Create ServiceNow IT Ticket",
        "department": ["IT Support"],
        "risk": "low",
        "foundry_tool": {
            "type": "openapi",
            "openapi": {
                "name": "servicenow_create_it_ticket",
                "description": "Create a ServiceNow IT ticket",
                "spec_ref": "TODO-path-or-url-to-openapi-spec.json",
                "auth": {"type": "connection", "connection_id": "TODO-apim-connection-id-servicenow"},
            },
        },
    },
    "Outlook-Send-Notification": {
        "display_name": "Send Outlook Notification",
        "department": ["HR", "Finance", "IT Support", "Operations"],
        "risk": "low",
        "foundry_tool": {
            "type": "openapi",
            "openapi": {
                "name": "send_outlook_notification",
                "description": "Send a notification email via Outlook/Graph on behalf of the agent's service account",
                "spec_ref": "TODO-path-or-url-to-graph-mail-spec.json",
                "auth": {"type": "connection", "connection_id": "TODO-graph-connection-id"},
            },
        },
    },
}


def knowledge_sources_for_department(department: str) -> dict:
    """Stage 2 (Knowledge page): what to show the user, pre-filtered by the
    department Stage 1 already determined. Pure lookup, no model involved."""
    return {k: v for k, v in KNOWLEDGE_CATALOG.items() if department in v["department"]}


def tools_for_department(department: str) -> dict:
    """Stage 2 (Actions page): same idea, for the tool catalog."""
    return {k: v for k, v in TOOL_CATALOG.items() if department in v["department"]}


def mvp_catalog_snapshot() -> CatalogSnapshot:
    """
    For Phase 2 MVP: the full static catalog, unfiltered. Swap this out in
    Phase 3 for a function that filters by the requester's Entra groups /
    department before the blueprint generator ever sees it.
    """
    return CatalogSnapshot(
        departments=DEPARTMENTS,
        agent_types=AGENT_TYPES,
        patterns=PATTERNS,
        model_policies=list(MODEL_POLICIES.keys()),
        knowledge_source_ids=list(KNOWLEDGE_CATALOG.keys()),
        tool_ids=list(TOOL_CATALOG.keys()),
        audience_ids=list(AUDIENCES.keys()),
        data_classifications=DATA_CLASSIFICATIONS,
        channels=CHANNELS,
    )
