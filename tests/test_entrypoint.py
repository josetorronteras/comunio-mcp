import runpy
from unittest.mock import patch

import comunio_mcp


def test_main_module_calls_main() -> None:
    with patch("comunio_mcp.main") as mock_main:
        runpy.run_module("comunio_mcp.__main__", run_name="__main__")

    mock_main.assert_called_once_with()


def test_main_runs_the_server_over_stdio() -> None:
    with patch("comunio_mcp.server.mcp") as mock_mcp:
        comunio_mcp.main()

    mock_mcp.run.assert_called_once_with(transport="stdio")
