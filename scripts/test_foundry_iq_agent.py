"""
this script demonstrates how to create a Foundry IQ agent that uses an existing knowledge base via the MCP tool. It assumes you have already created a knowledge base and set up a connection to it in your Foundry project.
"""
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool
from azure.identity import DefaultAzureCredential
import os
from dotenv import load_dotenv
load_dotenv()  # load .env file with PROJECT_ENDPOINT
credential = DefaultAzureCredential()

project_endpoint = os.getenv("PROJECT_ENDPOINT")  # your FOUNDRY_PROJECT_ENDPOINT from .env
project_connection_name = "credo-kb-mcp-connection"  # must match test_foundry_iq_connection.py
search_service_endpoint = os.getenv("SEARCH_SERVICE_ENDPOINT")  # your real service
knowledge_base_name = "knowledgebase107"
agent_name = "credo-kb-smoke-test"
agent_model = os.getenv("AGENT_MODEL")  # your real Foundry model deployment name, e.g. gpt-5

mcp_endpoint = f"{search_service_endpoint}/knowledgebases/{knowledge_base_name}/mcp?api-version=2026-08-01-preview"

project_client = AIProjectClient(endpoint=project_endpoint, credential=credential, allow_preview=True)

instructions = """
You are a helpful assistant that must use the knowledge base to answer all
questions from the user. You must never answer from your own knowledge.
Every answer must provide annotations for using the MCP knowledge base tool
and render them as: `【message_idx:search_idx†source_name】`
If you cannot find the answer in the provided knowledge base you must
respond with "I don't know".
"""

mcp_kb_tool = MCPTool(
    server_label="knowledge-base",
    server_url=mcp_endpoint,
    require_approval="never",
    allowed_tools=["knowledge_base_retrieve"],
    project_connection_id=project_connection_name,
)

agent = project_client.agents.create_version(
    agent_name=agent_name,
    definition=PromptAgentDefinition(
        model=agent_model,
        instructions=instructions,
        tools=[mcp_kb_tool],
    ),
)
print(f"Agent '{agent_name}' created — version {agent.version}")

# --- Invoke it with one test query ---
openai_client = project_client.get_openai_client()
conversation = openai_client.conversations.create()

response = openai_client.responses.create(
    conversation=conversation.id,
    input="What does this knowledge base actually contain? Summarize it.",
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
)
print("\nResponse:\n", response.output_text)

# --- Cleanup (uncomment once you've confirmed it worked) ---
# project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
# print(f"Deleted agent '{agent.name}' version '{agent.version}'")