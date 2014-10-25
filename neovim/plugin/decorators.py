"""Decorators used by python host plugin system."""
import inspect


import logging
logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)
__all__ = ('plugin', 'rpc_export', 'command', 'autocommand', 'function',
           'encoding')


def plugin(cls):
    """Tag a class as a plugin.

    This decorator is required to make the a class methods discoverable by the
    plugin_load method of the host.
    """
    cls._nvim_plugin = True
    # the _nvim_bind attribute is set to True by default, meaning that
    # decorated functions have a bound Nvim instance as first argument.
    # For methods in a plugin-decorated class this is not required, because
    # the class initializer will already receive the nvim object. 
    for _, fn in inspect.getmembers(cls, inspect.ismethod):
        if hasattr(fn, '_nvim_bind'):
            fn.im_func._nvim_bind = False
    return cls


def rpc_export(rpc_method_name, async=False):
    """Export a function or plugin method as a msgpack-rpc request handler."""
    def dec(f):
        f._nvim_rpc_method_name = rpc_method_name
        f._nvim_rpc_async = async
        f._nvim_bind = True
        return f
    return dec


def command(name, nargs=0, complete=None, range=None, count=None, bang=False,
            bar=False, register=False, async=False):
    """Tag a function or plugin method as a Nvim command handler."""
    def dec(f):
        f._nvim_command_name = name
        f._nvim_command_nargs = nargs
        f._nvim_command_complete = complete
        f._nvim_command_range = range
        f._nvim_command_count = count
        f._nvim_command_bang = bang
        f._nvim_command_bar = bar
        f._nvim_command_register = register
        f._nvim_rpc_method_name = 'command:{0}'.format(name)
        f._nvim_rpc_async = async
        f._nvim_bind = True
        return f
    return dec


def autocommand(event, unique_id=None, async=False):
    """Tag a function or plugin method as a Nvim autocommand handler."""
    def dec(f):
        uid = unique_id
        if not uid:
            uid = '{1}.{0}'.format(f.__module__, f.__name__)
        f._nvim_autocommand_event = event
        f._nvim_rpc_method_name = 'autocmd:{0}:{1}'.format(event, uid)
        f._nvim_rpc_async = async
        f._nvim_bind = True
        return f
    return dec


def function(name, range=False, async=False):
    """Tag a function or plugin method as a Nvim function handler."""
    def dec(f):
        f._nvim_function_name = name
        f._nvim_function_range = range
        f._nvim_rpc_method_name = 'function:{0}'.format(name)
        f._nvim_rpc_async = async
        f._nvim_bind = True
        return f
    return dec


def encoding(encoding=True):
    """Configure automatic encoding/decoding of strings."""
    def dec(f):
        f._nvim_encoding = encoding
        return f
    return dec
