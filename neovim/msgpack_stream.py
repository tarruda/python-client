import msgpack, logging

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)

class MsgpackStream(object):
    def __init__(self, stream):
        def default(obj):
            if callable(obj):
                return msgpack.ExtType(self.vim.api_metadata['types']['Function']['id'], msgpack.packb(obj.__name__, use_bin_type=True))
            return obj._handle

        def ext_hook(code, data):
            klass = self.types[code]
            rv = klass(self.vim, msgpack.ExtType(code, data))
            klass.initialize(rv)
            return rv

        self.types = None
        self.type_codes = None
        self.vim = None
        self.packer = msgpack.Packer(use_bin_type=True, default=default)
        self.unpacker = msgpack.Unpacker(ext_hook=ext_hook)
        self.stream = stream


    def configure(self, vim):
        self.vim = vim
        self.types = {}
        self.type_codes = {}
        for name, info in vim.api_metadata['types'].items():
            if hasattr(vim, name):
                kls = getattr(vim, name)
                self.types[info['id']] = kls
                self.type_codes[kls] = info['id']

    def interrupt(self):
        self.stream.interrupt()


    def send(self, msg):
        self.stream.send(self.packer.pack(msg))


    def loop_start(self, msg_cb, error_cb):
        def data_cb(data):
            self.unpacker.feed(data)

            while True:
                try:
                    debug('waiting for message...')
                    msg = next(self.unpacker)
                    debug('received message: %s', msg)
                    msg_cb(msg)
                except StopIteration:
                    debug('unpacker needs more data...')
                    break

        self.stream.loop_start(data_cb, error_cb)
        debug('exiting msgpack stream loop')


    def loop_stop(self):
        self.stream.loop_stop()
