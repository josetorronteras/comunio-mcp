import asyncio

from comunio_mcp.metadata import SERVER_NAME
from comunio_mcp.server import mcp


def test_server_identity() -> None:
    assert mcp.name == SERVER_NAME


def test_reads_and_writes_are_told_apart_by_annotation() -> None:
    # A client uses this to decide what to ask about before running.
    tools = asyncio.run(mcp.list_tools())

    reads = {t.name for t in tools if t.annotations and t.annotations.read_only_hint}
    writes = {t.name for t in tools if not (t.annotations and t.annotations.read_only_hint)}

    assert all(name.startswith("get_") for name in reads)
    assert not any(name.startswith("get_") for name in writes)


def test_only_accepting_an_offer_is_destructive() -> None:
    # Everything else queues or can be reversed; this is the one that cannot.
    tools = asyncio.run(mcp.list_tools())

    destructive = {
        t.name for t in tools if t.annotations and t.annotations.destructive_hint
    }

    assert destructive == {"accept_offer"}
