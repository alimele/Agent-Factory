"""
Stage 1 of 3 — Describe page.

NL text -> the CORE blueprint fields only: name, department, agentType,
pattern, purpose, modelPolicy, dataClassification, humanApproval,
externalSharing. Deliberately does NOT touch knowledgeSources, tools, or
audience — those are picked by the user on their own catalog pages
(Knowledge/Actions/Security), never guessed from the description text. See
blueprint_compiler.py for Stage 3, which assembles the final AgentBlueprint
once those manual picks exist.

Uses the Foundry project's own OpenAI-compatible endpoint and the Responses
API — matching the sample your Foundry project page gives you (model =
your deployment name, not a bare model id):

    from openai import OpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    endpoint = "https://<your-project>/openai/v1"
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )
    client = OpenAI(base_url=endpoint, api_key=token_provider)
    response = client.responses.parse(model=deployment_name, input=..., text_format=SomeModel)

Requires:
    pip install -U openai pydantic azure-identity
Env:
    FOUNDRY_PROJECT_ENDPOINT   copy the exact base_url from your Foundry
                               project's own code sample — don't hand-build
                               it, the host format has changed before.
    AZURE_OPENAI_DEPLOYMENT    the deployment name you chose in the portal, e.g. "gpt-5"
Auth:
    DefaultAzureCredential — run `az login` locally so it has something to
    pick up. No API key is used or stored.
"""

from __future__ import annotations

from typing import List, Literal, Type
from pydantic import BaseModel, create_model

from blueprint_schema import CatalogSnapshot


def _literal(values: List[str]):
    return Literal[tuple(values)]  # type: ignore[valid-type]


def build_core_draft_model(catalog: CatalogSnapshot) -> Type[BaseModel]:
    """
    The Stage 1 output schema. Only catalog-bound fields that belong to
    Stage 1 exist here at all — knowledgeSources/tools/audience aren't just
    optional, they're simply absent from this model, so the LLM cannot
    populate them even if it tried.
    """
    return create_model(
        "CoreBlueprintDraft",
        name=(str, ...),
        department=(_literal(catalog.departments), ...),
        agentType=(_literal(catalog.agent_types), ...),
        pattern=(_literal(catalog.patterns), ...),
        purpose=(str, ...),
        modelPolicy=(_literal(catalog.model_policies), ...),
        dataClassification=(_literal(catalog.data_classifications), ...),
        humanApproval=(bool, ...),
        externalSharing=(bool, False),
    )


SYSTEM_PROMPT_TEMPLATE = """You are the Agent Blueprint generator for CREDO Enterprise Agent Factory.

A business user has described, in plain language, an AI agent they want
built. From that description alone, determine:
- which department it belongs to
- what type of agent it is
- its overall pattern
- a 1-3 sentence restatement of its purpose
- which model policy tier it needs
- the most restrictive data classification its purpose plausibly touches
  (pick the most restrictive plausible one, not the most convenient one)
- whether a human should approve its actions before they run
- whether it may ever share data externally (default to false unless the
  request is unambiguous about needing external sharing)

Do NOT decide what knowledge sources or tools this agent will use — that is
decided later by the user on separate catalog pages. You have no visibility
into those catalogs and must not reference or guess specific systems,
SharePoint sites, or tools by name in the purpose text.

Approved departments: {departments}
Approved agent types: {agent_types}
Approved patterns: {patterns}
Approved model policies: {model_policies}
Approved data classifications: {data_classifications}
"""


def _default_client():
    import os
    from openai import OpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )
    return OpenAI(base_url=os.environ["FOUNDRY_PROJECT_ENDPOINT"], api_key=token_provider)


def generate_core_blueprint(
    user_text: str,
    catalog: CatalogSnapshot,
    client=None,
    deployment: str | None = None,
) -> BaseModel:
    """
    Returns an instance of the dynamically-built CoreBlueprintDraft model —
    NOT the full AgentBlueprint. Call blueprint_compiler.compile_blueprint()
    once the user has also picked knowledgeSources/tools/audience to get the
    final AgentBlueprint.
    """
    import os

    if client is None:
        client = _default_client()
    if deployment is None:
        deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

    draft_model = build_core_draft_model(catalog)

    instructions = SYSTEM_PROMPT_TEMPLATE.format(
        departments=", ".join(catalog.departments),
        agent_types=", ".join(catalog.agent_types),
        patterns=", ".join(catalog.patterns),
        model_policies=", ".join(catalog.model_policies),
        data_classifications=", ".join(catalog.data_classifications),
    )

    response = client.responses.parse(
        model=deployment,
        instructions=instructions,
        input=user_text,
        text_format=draft_model,
    )
    return response.output_parsed
