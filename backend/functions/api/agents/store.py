"""
Cosmos DB persistence for Agent records.

Partitioned by /owner, so "list my agents" (My Agents, Playground) is
always a single-partition query. Uses the same DefaultAzureCredential
pattern as every other dynamic catalog in this codebase (knowledge_registry,
api_center_catalog) — no connection string, no key in app settings.

Required app settings:
  COSMOS_ENDPOINT     e.g. https://<account>.documents.azure.com:443/
Optional:
  COSMOS_DATABASE                 default "credo-factory"
  COSMOS_AGENTS_CONTAINER         default "agents"
  COSMOS_AGENTS_THROUGHPUT        set only if your account needs an explicit
                                   container-level RU/s (serverless accounts,
                                   or accounts with database-level shared
                                   throughput, should leave this unset)

The calling identity (this Function App's managed identity locally via
`az login` / DefaultAzureCredential) needs Cosmos DB Built-in Data
Contributor on the account — a data-plane RBAC role, not a control-plane
one; granting only Contributor on the ARM resource is a common mistake that
produces a 403 here.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential

from api.agents.models import AgentRecord, AgentStatus

logger = logging.getLogger(__name__)

_DATABASE_NAME = os.environ.get("COSMOS_DATABASE", "credo-factory")
_CONTAINER_NAME = os.environ.get("COSMOS_AGENTS_CONTAINER", "agents")
_THROUGHPUT = os.environ.get("COSMOS_AGENTS_THROUGHPUT")

_client: Optional[CosmosClient] = None
_container = None


def _get_container():
    global _client, _container
    if _container is not None:
        return _container

    endpoint = os.environ["COSMOS_ENDPOINT"]
    if _client is None:
        _client = CosmosClient(endpoint, credential=DefaultAzureCredential())

    database = _client.create_database_if_not_exists(_DATABASE_NAME)

    kwargs: dict = {}
    if _THROUGHPUT:
        kwargs["offer_throughput"] = int(_THROUGHPUT)

    _container = database.create_container_if_not_exists(
        id=_CONTAINER_NAME,
        partition_key=PartitionKey(path="/owner"),
        **kwargs,
    )
    return _container


def save(record: AgentRecord) -> AgentRecord:
    container = _get_container()
    container.upsert_item(record.model_dump())
    return record


def get(owner: str, agent_id: str) -> Optional[AgentRecord]:
    if not agent_id:
        return None
    container = _get_container()
    try:
        item = container.read_item(item=agent_id, partition_key=owner)
    except exceptions.CosmosResourceNotFoundError:
        return None
    return AgentRecord(**item)


def list_for_owner(owner: str, status: Optional[AgentStatus] = None) -> list[AgentRecord]:
    container = _get_container()
    query = "SELECT * FROM c WHERE c.owner = @owner"
    params = [{"name": "@owner", "value": owner}]
    if status:
        query += " AND c.status = @status"
        params.append({"name": "@status", "value": status.value})
    query += " ORDER BY c.updatedAt DESC"

    try:
        items = list(container.query_items(query=query, parameters=params, partition_key=owner))
    except exceptions.CosmosHttpResponseError:
        logger.exception("Cosmos query failed for owner=%s", owner)
        raise
    return [AgentRecord(**item) for item in items]
