"""
This script demonstrates how to create a connection in Foundry IQ to an Azure Cognitive Search knowledge base using the Foundry IQ API. It uses the DefaultAzureCredential for authentication and requires the PROJECT_RESOURCE_ID, SEARCH_SERVICE_ENDPOINT, and knowledge_base_name to be set in a .env file.
"""
import requests
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
import os
load_dotenv()  # load .env file with PROJECT_RESOURCE_ID
credential = DefaultAzureCredential()

project_resource_id = os.getenv("PROJECT_RESOURCE_ID")  # from step 3 above
project_connection_name = "credo-kb-mcp-connection"  # any name you choose
search_service_endpoint = os.getenv("SEARCH_SERVICE_ENDPOINT")  # your real service
knowledge_base_name = "knowledgebase107"  # your real, already-existing KB

mcp_endpoint = f"{search_service_endpoint}/knowledgebases/{knowledge_base_name}/mcp?api-version=2026-08-01-preview"

bearer_token_provider = get_bearer_token_provider(credential, "https://management.azure.com/.default")
headers = {"Authorization": f"Bearer {bearer_token_provider()}"}

response = requests.put(
    f"https://management.azure.com{project_resource_id}/connections/{project_connection_name}?api-version=2025-10-01-preview",
    headers=headers,
    json={
        "name": project_connection_name,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": mcp_endpoint,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    },
)
response.raise_for_status()
print(f"Connection '{project_connection_name}' created successfully.")
