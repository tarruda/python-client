"""Implements a Nvim host for python plugins."""
import functools
import imp
import inspect
import logging
import os
import os.path

from ..api import DecodeHook
from ..compat import IS_PYTHON3, find_module


__all__ = ('Host')

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)


class Host(object):

    """Nvim host for python plugins.

    Takes care of loading/unloading plugins and routing msgpack-rpc
    requests/notifications to the appropriate handlers.
    """

    def __init__(self, nvim):
        """Set handlers for plugin_load/plugin_unload."""
        self.nvim = nvim
        self._loaded = {}
        self._notification_handlers = {}
        self._request_handlers = {
            'plugin_load': self.plugin_load,
            'plugin_unload': self.plugin_unload
        }
        self._nvim_encoding = nvim.options['encoding']

    def run(self):
        """Start listening for msgpack-rpc requests and notifications."""
        self.nvim.session.run(self.on_request, self.on_notification)

    def on_request(self, name, args):
        """Handle a msgpack-rpc request."""
        handler = self._request_handlers.get(name, None)
        if not handler:
            msg = 'no request handlers registered for "%s"' % name
            warn(msg)
            raise Exception(msg)

        debug('calling request handler for "%s", args: "%s"', name, args)
        rv = handler(*args)
        debug("request handler for '%s %s' returns: %s", name, args, rv)
        return rv

    def on_notification(self, name, args):
        """Handle a msgpack-rpc notification."""
        handlers = self._notification_handlers.get(name, None)
        if not handlers:
            warn('no notification handlers registered for "%s"', name)
            return

        debug('calling notification handler for "%s", args: "%s"', name, args)
        for handler in handlers:
            handler(*args)

    def plugin_load(self, path):
        """Handle the "plugin_load" msgpack-rpc method."""
        if path in self._loaded:
            raise Exception('{0} is already loaded'.format(path))
        directory, name = os.path.split(os.path.splitext(path)[0])
        file, pathname, description = find_module(name, [directory])
        module = imp.load_module(name, file, pathname, description)
        handlers = []
        self._discover_classes(module, handlers)
        self._discover_functions(module, handlers)
        if not handlers:
            raise Exception('{0} exports no handlers'.format(path))
        self._loaded[path] = {'handlers': handlers, 'module': module}

    def plugin_unload(self, path):
        """Handle the "plugin_unload" msgpack-rpc method."""
        plugin = self._loaded.pop(path, None)
        if not plugin:
            raise Exception('{0} is not loaded'.format(path))
        handlers = plugin['handlers']
        for handler in handlers:
            if handler._nvim_unload_handler:
                handler()
            elif handler._nvim_rpc_async:
                del self._notification_handlers[handler._nvim_rpc_method_name]
            else:
                del self._request_handlers[handler._nvim_rpc_method_name]

    def _discover_classes(self, module, handlers):
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if getattr(cls, '_nvim_plugin', False):
                # create an instance of the plugin and pass the nvim object
                plugin = cls(self._configure_nvim_for(cls))
                # discover handlers in the plugin instance
                self._discover_functions(plugin, handlers)

    def _discover_functions(self, obj, handlers):
        predicate = lambda o: hasattr(o, '_nvim_rpc_method_name')
        for _, fn in inspect.getmembers(obj, predicate):
            if fn._nvim_bind:
                # bind a nvim instance to the handler
                fn2 = functools.partial(fn, self._configure_nvim_for(fn))
                # copy _nvim_* attributes from the original function
                for attr in dir(fn):
                    if attr.startswith('_nvim_'):
                        setattr(fn2, attr, getattr(fn, attr))
                fn = fn2
            # register in the rpc handler dict
            if fn._nvim_rpc_async:
                self._notification_handlers[fn._nvim_rpc_method_name] = fn
            else:
                self._request_handlers[fn._nvim_rpc_method_name] = fn
            handlers.append(fn)

    def _configure_nvim_for(self, obj):
        # Configure a nvim instance for obj(checks encoding configuration)
        nvim = self.nvim
        encoding = getattr(obj, '_nvim_encoding', None)
        if IS_PYTHON3 and encoding is None:
            encoding = True
        if encoding is True:
            encoding = self._nvim_encoding
        if encoding:
            nvim = nvim.with_hook(DecodeHook(encoding))
        return nvim
