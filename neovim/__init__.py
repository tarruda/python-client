from client import Client
from script_host import ScriptHost
from uv_stream import UvStream
from time import sleep
import logging

__all__ = ['connect', 'run_script_host', 'ScriptHost']

logger = logging.getLogger(__name__)
debug = logger.debug

def connect(address=None, port=None):
    client = Client(UvStream(address, port))
    client.discover_api()
    return client.vim

def run_script_host(address=None, port=None):
    logfile = '/tmp/script-host.log'
    open(logfile, 'w').close()
    logging.basicConfig(filename=logfile, level=logging.WARNING)
    debug('connecting to neovim')
    vim = connect(address, port)
    debug('connected to neovim')
    with ScriptHost(vim) as host:
        host.run()
