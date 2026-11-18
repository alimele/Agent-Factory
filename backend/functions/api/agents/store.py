"""
Azure Table Storage persistence for Agent records.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import DefaultAzureCredential

from api.agents.models import AgentRecord, AgentStatus

logger = logging.getLogger(__name__)

_ENDPOINT = os.environ["TABLE_STORAGE_ENDPOINT"]
_TABLE_NAME = os.environ.get("TABLE_STORAGE_TABLE_NAME", "AgentRecords")

_service: Optional[TableServiceClient] = None
_table = None


def _get_table():
    global _service, _table

    if _table is not None:
        return _table

    if _service is None:
        _service = TableServiceClient(
            endpoint=_ENDPOINT,
            credential=DefaultAzureCredential(),
        )

    _service.create_table_if_not_exists(_TABLE_NAME)
    _table = _service.get_table_client(_TABLE_NAME)
    return _table


def _to_entity(record: AgentRecord) -> dict:
    data = record.model_dump(mode="json")

    entity = {
        "PartitionKey": record.owner,
        "RowKey": record.id,
        "id": record.id,
        "owner": record.owner,
        "status": record.status.value,
        "createdAt": record.createdAt,
        "updatedAt": record.updatedAt,
    }

    # Store complex fields as JSON strings.
    json_fields = [
        "coreDraft",
        "knowledgeSourceIds",
        "toolSelections",
        "audienceIds",
        "behavior",
        "blueprint",
        "foundryPayload",
        "policyEvaluation",
        "foundryAgentName",
        "foundryAgentVersion",
        "templateId",
    ]

    for field in json_fields:
        entity[field] = json.dumps(data.get(field))

    return entity


def _to_record(entity: dict) -> AgentRecord:
    data = {
        "id": entity["RowKey"],
        "owner": entity["owner"],
        "status": entity["status"],
        "createdAt": entity["createdAt"],
        "updatedAt": entity["updatedAt"],
    }

    json_fields = [
        "coreDraft",
        "knowledgeSourceIds",
        "toolSelections",
        "audienceIds",
        "behavior",
        "blueprint",
        "foundryPayload",
        "policyEvaluation",
        "foundryAgentName",
        "foundryAgentVersion",
        "templateId",
    ]

    # Fields that default to an empty list on AgentRecord — fall back to "[]"
    # for an entity written before that field existed (e.g. a pre-upgrade
    # draft that still has the old "toolIds" column but no "toolSelections"),
    # rather than passing None into a list-typed field and failing validation.
    _list_fields = {"knowledgeSourceIds", "toolSelections", "audienceIds"}
    for field in json_fields:
        value = entity.get(field)
        if value is None:
            data[field] = [] if field in _list_fields else None
        else:
            data[field] = json.loads(value)

    return AgentRecord(**data)


def save(record: AgentRecord) -> AgentRecord:
    _get_table().upsert_entity(
        entity=_to_entity(record),
        mode=UpdateMode.REPLACE,
    )
    return record


def get(owner: str, agent_id: str) -> Optional[AgentRecord]:
    if not agent_id:
        return None

    try:
        entity = _get_table().get_entity(
            partition_key=owner,
            row_key=agent_id,
        )
    except ResourceNotFoundError:
        return None

    return _to_record(entity)


def list_for_owner(
    owner: str,
    status: Optional[AgentStatus] = None,
) -> list[AgentRecord]:
    # Escape apostrophes for OData string literals.
    safe_owner = owner.replace("'", "''")
    query = f"PartitionKey eq '{safe_owner}'"

    if status:
        query += f" and status eq '{status.value}'"

    entities = _get_table().query_entities(query_filter=query)
    records = [_to_record(entity) for entity in entities]

    # Table Storage does not support ORDER BY updatedAt.
    return sorted(
        records,
        key=lambda record: record.updatedAt,
        reverse=True,
    )