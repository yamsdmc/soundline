import sys
from collections.abc import AsyncIterator

import pytest
from mcp.client.client import Client
from mcp.types import CallToolResult, TextContent

from soundline import Soundline
from soundline.interfaces.mcp_server import build_server
from soundline.testing import ScriptedLanguageModel

LEASE = "# Bail d'habitation\n\nRent is due on the 5th. Pets are allowed."

pytestmark = [pytest.mark.anyio]
if sys.platform == "win32":
    # asyncio's Windows event loop wakes itself through a loopback socket pair, where Unix
    # uses an AF_UNIX one: allow sockets, but connections to the loopback address only.
    pytestmark += [pytest.mark.enable_socket, pytest.mark.allow_hosts(["127.0.0.1"])]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def soundline_with(llm: ScriptedLanguageModel | None) -> Soundline:
    soundline = Soundline.in_memory(llm=llm or ScriptedLanguageModel())
    soundline.ingest_text("lease.md", LEASE)
    return soundline


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    llm = ScriptedLanguageModel(
        {
            "claims": [
                {
                    "text": "Rent is due on the 5th.",
                    "citations": [{"evidence_id": "E1", "quote": "Rent is due on the 5th"}],
                }
            ],
            "insufficient_evidence": None,
        }
    )
    server = build_server(soundline_with(llm), description="A residential lease.")
    async with Client(server) as connected:
        yield connected


def text_of(result: CallToolResult) -> str:
    return "".join(part.text for part in result.content if isinstance(part, TextContent))


@pytest.mark.spec("MCP-001", "MCP-003")
async def test_the_server_offers_read_only_search_ask_and_list_corpora(client: Client):
    tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {"search", "ask", "list_corpora"}
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools.values())
    assert "ask" in (tools["search"].description or "")  # when to use which (MCP-001)
    assert "search" in (tools["ask"].description or "")


@pytest.mark.spec("MCP-002")
async def test_search_returns_passages_as_labeled_untrusted_data(client: Client):
    result = await client.call_tool("search", {"query": "rent due", "k": 3})

    text = text_of(result)
    assert not result.is_error
    assert '<passage rank="1" source="lease.md" section="Bail d\'habitation">' in text
    assert "Rent is due on the 5th." in text
    assert "untrusted" in text


@pytest.mark.spec("MCP-002")
async def test_ask_returns_a_verified_answer_with_its_citations(client: Client):
    result = await client.call_tool("ask", {"question": "When is rent due?"})

    text = text_of(result)
    assert "Rent is due on the 5th [1]." in text
    assert '[1] lease.md, Bail d\'habitation: "Rent is due on the 5th"' in text


@pytest.mark.spec("MCP-004")
async def test_list_corpora_describes_the_corpus(client: Client):
    text = text_of(await client.call_tool("list_corpora", {}))

    assert "default" in text
    assert "A residential lease." in text


@pytest.mark.spec("API-003")
async def test_a_soundline_error_reaches_the_agent_with_its_stable_code():
    soundline = Soundline.in_memory(llm=ScriptedLanguageModel())  # empty script
    soundline.ingest_text("lease.md", LEASE)
    soundline._llm = None  # pyright: ignore[reportPrivateUsage]  # no model configured

    async with Client(build_server(soundline)) as connected:
        result = await connected.call_tool("ask", {"question": "When is rent due?"})

    assert result.is_error
    assert "error[configuration_error]" in text_of(result)
