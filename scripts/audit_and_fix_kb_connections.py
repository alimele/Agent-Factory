"""
One-time (and periodically-safe-to-rerun) cleanup for knowledge-source
catalog entries that predate api/blueprint/connection_manager.py and
knowledge_registry.register_knowledge_source() — i.e. entries whose
`projectConnectionName` was typed by hand and may be wrong.

This is exactly the script to run to find and fix the Alpha Bank /
knowledgebase107 incident, and to confirm nothing else in the catalog has
the same problem.

Usage:
    cd backend/functions
    python ../../scripts/audit_and_fix_kb_connections.py            # report only
    python ../../scripts/audit_and_fix_kb_connections.py --fix      # report + fix

Requires the same environment as the Function App itself: APPCONFIG_ENDPOINT,
PROJECT_RESOURCE_ID, and `az login` (or another DefaultAzureCredential-
compatible auth) with Foundry Project Manager on the project and read access
to App Configuration.

--fix re-provisions each affected entry via register_knowledge_source(),
which re-derives the connection name from source_id and re-runs
ensure_project_connection() against that entry's OWN searchServiceEndpoint/
knowledgeBaseName. It never touches entries that already pass the audit.
"""
import argparse
import json
import sys

# Make `api.*` importable when run directly from scripts/, same pattern
# other one-off scripts in this repo rely on (run via the backend/functions
# virtualenv, or add backend/functions to PYTHONPATH).
sys.path.insert(0, "backend/functions")
sys.path.insert(0, "../backend/functions")

from api.blueprint.knowledge_registry import (  # noqa: E402
    audit_connection_assignments,
    list_all_knowledge_sources,
    register_knowledge_source,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Apply fixes, not just report")
    args = parser.parse_args()

    findings = audit_connection_assignments()

    if not findings:
        print("Clean — every knowledge source has its own connection, and every "
              "connection's live target matches what its registry entry expects.")
        return

    print(f"Found {len(findings)} issue(s):\n")
    affected_source_ids: set[str] = set()
    for f in findings:
        print(f"  [{f['issue']}] {f['sourceId']}: {f.get('detail', '')}")
        affected_source_ids.add(f["sourceId"])

    if not args.fix:
        print("\nRe-run with --fix to re-provision the affected entries' connections.")
        return

    print(f"\nFixing {len(affected_source_ids)} entry(ies)...")
    sources = list_all_knowledge_sources()
    for source_id in affected_source_ids:
        item = sources.get(source_id)
        if item is None:
            print(f"  SKIP {source_id}: no longer present in the registry")
            continue
        result = register_knowledge_source(
            source_id=source_id,
            display_name=item.get("displayName", source_id),
            departments=item.get("department") or [],
            data_classification=item.get("dataClassification", "Internal"),
            search_service_endpoint=item["searchServiceEndpoint"],
            knowledge_base_name=item["knowledgeBaseName"],
            agent_factory_ready=item.get("agentFactoryReady", True),
        )
        print(f"  FIXED {source_id} -> connection '{result['connectionName']}' -> {result['mcpTarget']}")

    print("\nDone. Recreate/republish any agents built from the affected knowledge "
          "sources (Review page -> \"Create a new version\") so they pick up the "
          "corrected connection.")


if __name__ == "__main__":
    main()
