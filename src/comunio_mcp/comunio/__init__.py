"""Everything that talks to api.comunio.es."""

from comunio_mcp.comunio.auth import AuthError, ComunioAuth
from comunio_mcp.comunio.client import ComunioClient

__all__ = ["AuthError", "ComunioAuth", "ComunioClient"]
