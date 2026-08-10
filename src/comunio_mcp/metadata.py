"""Identity of the server, shared by the server instance and the tools."""

from importlib.metadata import version

SERVER_NAME = "comunio"
SERVER_VERSION = version("comunio-mcp")
