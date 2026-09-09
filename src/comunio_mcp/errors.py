"""Letting a failure say what went wrong.

The SDK hides the detail of a crash on purpose. Anything a tool raises that is not a
`ToolError` reaches the client as `Error executing tool <name>` and nothing else, with the
exception and its traceback kept in the server log: a traceback can carry whatever the
process happened to be holding, so not shipping it to the model is the right default.

The cost is that a refusal the server means to make looks identical to a crash. Every
guard in `comunio/actions.py` raises `ValueError` with a precise sentence — "A bid must be
greater than zero", "That offer is not one of yours" — and the client was seeing none of
it. So was the message that says which credentials to set, and so was a response whose
shape Comunio had changed underneath us: `status: null` on the market took four days to
find because the field name never left the server.

`ToolError` is the other contract: raised deliberately, delivered to the model, logged
without a traceback. What follows translates the four failures this server anticipates
into one, and lets everything else stay a crash.

Nothing here forwards a value. A pydantic message quotes the input it rejected, and that
input is somebody's squad; an HTTP error stringifies the URL, which carries account and
league ids. Field names and a status code are enough to act on and carry neither.
"""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

import httpx2
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

Tool = TypeVar("Tool", bound=Callable[..., Awaitable[Any]])


def _shape_changed(exc: ValidationError) -> str:
    """Name the fields that failed, never what they held."""
    fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
    return (
        "Comunio's response did not match what this server expects, at: "
        f"{', '.join(fields)}. This is a change on Comunio's side rather than a bad "
        "request: the server needs updating before this tool can answer."
    )


def _refused(exc: httpx2.HTTPStatusError) -> str:
    """Report the status and only the status.

    A failed login answers with the credentials echoed back in the body, and every URL
    here carries the league and user ids, so neither the body nor the request is safe to
    put in a message the model reads.
    """
    return f"Comunio answered HTTP {exc.response.status_code} and the call did not go through."


def reporting_failures(tool: Tool) -> Tool:
    """Turn the failures this server anticipates into ones the client can read.

    Wraps a tool body: `ValidationError` first, since pydantic raises a subclass of
    `ValueError` and would otherwise be reported as a guard refusing the call.
    """

    @wraps(tool)
    async def call(*args: Any, **kwargs: Any) -> Any:
        try:
            return await tool(*args, **kwargs)
        except ValidationError as exc:
            raise ToolError(_shape_changed(exc)) from exc
        except httpx2.HTTPStatusError as exc:
            raise ToolError(_refused(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            # A guard in `comunio/actions.py` refusing the call, or the message naming
            # the credentials that are not set. Both are already written for the model.
            raise ToolError(str(exc)) from exc

    return call  # type: ignore[return-value]
