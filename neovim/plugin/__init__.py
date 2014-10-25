"""Nvim plugin/host subpackage."""

from .decorators import (autocommand, command, encoding, function, plugin,
                         rpc_export)
from .host import Host


__all__ = ('Host', 'plugin', 'rpc_export', 'command', 'autocommand',
           'function', 'encoding')
