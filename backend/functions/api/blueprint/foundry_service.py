"""Phase 4: create and test development agents in Microsoft Foundry.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    MCPTool,
    OpenApiAnonymousAuthDetails,
    OpenApiFunctionDefinition,
    OpenApiManagedAuthDetails,
    OpenApiManagedSecurityScheme,
    OpenApiProjectConnectionAuthDetails,
    OpenApiProjectConnectionSecurityScheme,
    OpenApiTool,
    PromptAgentDefinition,
)
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field

from api.blueprint.api_center_catalog import get_foundry_tool
from api.blueprint.catalog_mvp import MODEL_POLICIES
from api.blueprint.knowledge_registry import get_foundry_tool as get_knowledge_mcp_tool
from api.blueprint.blueprint_schema import AgentBlueprint, BehaviorOptions
from api.blueprint.instructions import build_instructions

logger = logging.getLogger(__name__)


class TestAgentRequest(BaseModel):
    agentName: str = Field(min_length=1, max_length=63)
    agentVersion: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=10000)

    class Config:
        extra = "forbid"


def _agent_name(name: str) -> str:
    """Return a Foundry-safe name: alphanumerics with hyphens in the middle."""
    cleaned = re.sub(r"[^A-Za-z0-9-]+", "-", name.strip()).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned).lower()
    if not cleaned:
        raise ValueError("Blueprint name must contain at least one letter or number")
    return cleaned[:63].rstrip("-")


def _model_deployment(policy_name: str) -> str:
    """Use optional app-setting overrides; otherwise respect the catalog mapping."""
    setting_by_policy = {
        "approved-general-enterprise": "FOUNDRY_MODEL_APPROVED_GENERAL_ENTERPRISE",
        "approved-high-accuracy": "FOUNDRY_MODEL_APPROVED_HIGH_ACCURACY",
        "approved-fast-lowcost": "FOUNDRY_MODEL_APPROVED_FAST_LOWCOST",
    }
    fallback = MODEL_POLICIES.get(policy_name)
    if fallback is None:
        raise ValueError(f"Unknown approved model policy: {policy_name}")
    return os.environ.get(setting_by_policy.get(policy_name, ""), "").strip() or fallback


def _parse_openapi_spec(value: Any, tool_id: str) -> dict[str, Any]:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            try:
                value = yaml.safe_load(value)
            except yaml.YAMLError as exc:
                raise ValueError(f"API Center tool '{tool_id}' has an unreadable OpenAPI specification") from exc
    if not isinstance(value, dict) or not isinstance(value.get("paths"), dict):
        raise ValueError(f"API Center tool '{tool_id}' did not export an OpenAPI object with paths")

    # Foundry requires operationIds with letters, hyphens, or underscores.
    http_methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    for path, path_item in value["paths"].items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in http_methods or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError(f"API Center tool '{tool_id}' operation {method.upper()} {path} is missing operationId")
            if not re.fullmatch(r"[A-Za-z_-]+", operation_id):
                raise ValueError(
                    f"API Center tool '{tool_id}' operationId '{operation_id}' must contain only letters, hyphens, or underscores"
                )
    return value


def _openapi_auth(auth_config: dict[str, Any], tool_id: str) -> Any:
    auth_type = (auth_config.get("type") or "anonymous").strip().lower()
    if auth_type == "anonymous":
        return OpenApiAnonymousAuthDetails()
    if auth_type in {"connection", "project_connection"}:
        connection_id = auth_config.get("connection_id")
        if not connection_id:
            raise ValueError(f"API Center tool '{tool_id}' requires a Foundry project connection ID")
        return OpenApiProjectConnectionAuthDetails(
            security_scheme=OpenApiProjectConnectionSecurityScheme(
                project_connection_id=connection_id,
            )
        )
    if auth_type in {"managed", "managed_identity"}:
        audience = auth_config.get("audience")
        if not audience:
            raise ValueError(f"API Center tool '{tool_id}' requires a managed-identity audience")
        return OpenApiManagedAuthDetails(
            security_scheme=OpenApiManagedSecurityScheme(audience=audience)
        )
    raise ValueError(f"API Center tool '{tool_id}' uses unsupported auth type '{auth_type}'")


def _build_tools(blueprint: AgentBlueprint) -> list[Any]:
    tools: list[Any] = []

    # This typed MCPTool configuration follows the working project smoke test
    # at scripts/test_foundry_iq_agent.py and the existing knowledge registry.
    for source_id in blueprint.knowledgeSources:
        config = get_knowledge_mcp_tool(source_id)
        tools.append(
            MCPTool(
                server_label=config["server_label"],
                server_url=config["server_url"],
                require_approval=config.get("require_approval", "never"),
                allowed_tools=config.get("allowed_tools"),
                project_connection_id=config["project_connection_id"],
            )
        )

    # Resolve only IDs selected by the user and revalidated against API
    # Center. Each one resolves to either an OpenAPI tool or an MCP server
    # tool — api_center_catalog.py::get_foundry_tool() tags which with a
    # "type" discriminator, mirroring the knowledge-source MCP tools above.
    for tool_id in blueprint.tools:
        config = get_foundry_tool(tool_id)
        tool_type = config.get("type")

        if tool_type == "mcp":
            mcp = config.get("mcp")
            if not isinstance(mcp, dict):
                raise ValueError(f"API Center tool '{tool_id}' did not resolve to a supported MCP definition")
            tools.append(
                MCPTool(
                    server_label=mcp["server_label"],
                    server_url=mcp["server_url"],
                    require_approval=mcp.get("require_approval", "never"),
                    allowed_tools=mcp.get("allowed_tools"),
                    project_connection_id=mcp.get("project_connection_id"),
                    headers=mcp.get("headers"),
                )
            )
        elif tool_type == "openapi":
            item = config.get("openapi")
            if not isinstance(item, dict):
                raise ValueError(f"API Center tool '{tool_id}' did not resolve to a supported OpenAPI definition")
            spec = _parse_openapi_spec(item.get("spec"), tool_id)
            auth = _openapi_auth(item.get("auth") or {"type": "anonymous"}, tool_id)
            definition = OpenApiFunctionDefinition(
                name=item["name"],
                description=item.get("description") or item["name"],
                spec=spec,
                auth=auth,
            )
            tools.append(OpenApiTool(openapi=definition))
        else:
            raise ValueError(f"API Center tool '{tool_id}' has an unrecognized tool type '{tool_type}'")
    return tools


def _metadata(blueprint: AgentBlueprint) -> dict[str, str]:
    # Agent version metadata is searchable/inspectable in Foundry and is used
    # by the test route to ensure the requester owns the test agent.
    raw = {
        "credo_department": blueprint.department,
        "credo_agent_type": blueprint.agentType,
        "credo_pattern": blueprint.pattern,
        "credo_owner": blueprint.owner or "",
        "credo_data_classification": blueprint.dataClassification,
        "credo_human_approval_required": str(blueprint.humanApproval).lower(),
        "credo_external_sharing": str(blueprint.externalSharing).lower(),
        "credo_audience": ",".join(blueprint.audience),
        "credo_review_period_days": str(blueprint.reviewPeriodDays),
        "credo_blueprint_version": blueprint.blueprintVersion,
        "credo_environment": "development",
    }
    return {key: value[:512] for key, value in raw.items()}


def _project_client() -> AIProjectClient:
    endpoint = os.environ.get("FOUNDRY_ACTUAL_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("FOUNDRY_ACTUAL_PROJECT_ENDPOINT app setting is required")
    return AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )


def create_test_agent(
    blueprint: AgentBlueprint,
    behavior: BehaviorOptions | None = None,
) -> dict[str, Any]:
    """Create a versioned, unpublished development agent from a validated blueprint."""
    behavior = behavior or BehaviorOptions()
    deployment = _model_deployment(blueprint.modelPolicy)
    agent_name = _agent_name(blueprint.name)
    project = _project_client()
    try:
        definition = PromptAgentDefinition(
            model=deployment,
            instructions=build_instructions(blueprint, behavior),
            tools=_build_tools(blueprint),
        )
        agent = project.agents.create_version(
            agent_name=agent_name,
            definition=definition,
            metadata=_metadata(blueprint),
            description="CREDO-generated development/test agent. Not published to users.",
        )
        result = {
            "name": getattr(agent, "name", agent_name),
            "id": getattr(agent, "id", None),
            "version": str(getattr(agent, "version", "")),
            "model": deployment,
            "status": "created",
            "environment": "development",
        }
        logger.info(
            "Created Foundry development agent name=%s version=%s owner=%s",
            result["name"], result["version"], blueprint.owner,
        )
        return result
    finally:
        project.close()


def _read_field(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        return value.get(field)
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return getter(field)
        except Exception:
            pass
    return getattr(value, field, None)


def run_test_query(request: TestAgentRequest, requester_email: str) -> dict[str, Any]:
    """Run a user-submitted test prompt against a development agent owned by them."""
    if _agent_name(request.agentName) != request.agentName:
        raise ValueError("agentName must match the Foundry-safe name returned by the create endpoint")
    project = _project_client()
    try:
        version_resource = project.agents.get_version(
            agent_name=request.agentName,
            agent_version=request.agentVersion,
        )
        metadata = _read_field(version_resource, "metadata") or {}
        owner = metadata.get("credo_owner") if isinstance(metadata, dict) else None
        environment = metadata.get("credo_environment") if isinstance(metadata, dict) else None
        if not owner or owner.casefold() != requester_email.casefold() or environment != "development":
            raise PermissionError("This development agent is not available to the signed-in requester")

        # Mirrors the tested call shape in scripts/test_foundry_iq_agent.py.
        # Tool-enabled agents can make real calls; the UI warns users to use
        # read-only or sandboxed API Center endpoints while testing.
        openai_client = project.get_openai_client()
        conversation = openai_client.conversations.create()
        response = openai_client.responses.create(
            conversation=conversation.id,
            input=request.prompt,
            extra_body={
                "agent_reference": {
                    "name": request.agentName,
                    "type": "agent_reference",
                }
            },
        )
        return {
            "agentName": request.agentName,
            "agentVersion": request.agentVersion,
            "outputText": getattr(response, "output_text", "") or "No text output was returned.",
        }
    finally:
        project.close()
