from imp import new_module, find_module, load_module
import sys, logging, os.path
from traceback import format_exc

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)


class RedirectStream(object):
    def __init__(self, redirect_handler):
        self.redirect_handler = redirect_handler

    def write(self, data):
        self.redirect_handler(data)

    def writelines(self, seq):
        self.redirect_handler('\n'.join(seq))


class ScriptHost(object):
    """
    Class that transforms the python interpreter into a script host for Neovim.
    It emulates an environment for python code similar to the one provided by
    vim-python bindings.
    """
    def __init__(self, vim):
        self.vim = vim
        self.method_handlers = {
            'execute': self.execute_handler,
            'execute_file': self.execute_file_handler,
            'do_range': self.do_range_handler,
            'eval': self.eval_handler,
        }
        self.event_handlers = {}
        # context where all code will run
        self.module = new_module('__main__')
        # it seems some plugins assume 'sys' is already imported, so do it now
        # exec 'import sys' in self.module.__dict__

    def __enter__(self):
        vim = self.vim
        debug('install magic vim module')
        sys.modules['vim'] = self.vim
        debug('install import hook/path')
        self.hook = path_hook(vim)
        sys.path_hooks.append(self.hook)
        vim.VIM_SPECIAL_PATH = '_vim_path_'
        sys.path.append(vim.VIM_SPECIAL_PATH)
        debug('redirect sys.stdout and sys.stderr')
        self.saved_stdout = sys.stdout
        self.saved_stderr = sys.stderr
        sys.stdout = RedirectStream(lambda data: vim.out_write(data))
        sys.stderr = RedirectStream(lambda data: vim.err_write(data))
        return self

    def __exit__(self, type, value, traceback):
        debug('uninstall magic vim module')
        del sys.modules['vim']
        debug('uninstall import hook/path')
        sys.path.remove(vim.VIM_SPECIAL_PATH)
        sys.path_hooks.remove(self.hook)
        debug('restore sys.stdout and sys.stderr')
        sys.stdout = self.saved_stdout
        sys.stderr = self.saved_stderr

    def execute_handler(self, script):
        exec script in self.module.__dict__

    def execute_file_handler(self, file_path):
        execfile(file_path, self.module.__dict__)

    def do_range_handler(self, arg):
        vim = self.vim
        start = arg[0] - 1
        stop = arg[1] - 1
        fname = '_vim_pydo'
        # define the function
        function_def = 'def %s(line, linenr):\n %s' % (fname, arg[2],)
        exec function_def in self.module.__dict__
        # get the function
        function = self.module.__dict__[fname]
        while start <= stop:
            # Process batches of 5000 to avoid the overhead of making multiple
            # API calls for every line. Assuming an average line length of 100
            # bytes, approximately 488 kilobytes will be transferred per batch,
            # which can be done very quickly in a single API call.
            sstart = start
            sstop = min(start + 5000, stop)
            lines = vim.current.buffer.get_slice(sstart, sstop, True, True)
            for i, line in enumerate(lines):
                linenr = i + sstart + 1
                result = str(function(line, linenr))
                if result:
                    lines[i] = result
            start = sstop + 1
            vim.current.buffer.set_slice(sstart, sstop, True, True, lines)
        # delete the function
        del self.module.__dict__[fname]

    def eval_handler(self, arg):
        return eval(arg, self.module.__dict__)

    def on_message(self, message):
        method_handlers = self.method_handlers
        event_handlers = self.event_handlers
        if message.type == 'request':
            handler = method_handlers.get(message.name, None)
            if not handler:
                msg = 'no method handlers registered for %s' % message.name
                debug(msg)
                message.reply(msg , error=True)
                return
            try:
                debug("running method handler for '%s %s'", message.name,
                      message.arg)
                rv = handler(message.arg)
                debug("method handler for '%s %s' returns: %s",
                      message.name,
                      message.arg,
                      rv)
                message.reply(rv)
            except Exception as e:
                err_str = format_exc(5)
                warn("error caught while processing '%s %s': %s",
                     message.name,
                     message.arg,
                     err_str)
                message.reply(err_str, error=True)
        elif message.type == 'event':
            handler = event_handlers.get(message.name, None)
            if not handler:
                debug("no event handlers registered for %s", message.name)
                return
            debug('running event handler for %s', message.name)
        else:
            assert False

    def run(self):
        self.vim.message_loop(lambda m: self.on_message(m))



# This was copied/adapted from vim-python help
def path_hook(vim):
    is_py3 = sys.version_info >= (3, 0)

    def _get_paths():
        rv = []
        for i, path in enumerate(vim.list_runtime_paths()):
            path1 = os.path.join(path, 'pythonx')
            if is_py3:
                path2 = os.path.join(path, 'python3')
            else:
                path2 = os.path.join(path, 'python2')
            if os.path.exists(path1):
                rv.append(path1)
            if os.path.exists(path2):
                rv.append(path2)
        return rv

    def _find_module(fullname, oldtail, path):
        idx = oldtail.find('.')
        if idx > 0:
            name = oldtail[:idx]
            tail = oldtail[idx+1:]
            fmr = find_module(name, path)
            module = load_module(fullname[:-len(oldtail)] + name, *fmr)
            return _find_module(fullname, tail, module.__path__)
        else:
            fmr = find_module(fullname, path)
            return load_module(fullname, *fmr)

    class VimModuleLoader(object):
        def __init__(self, module):
            self.module = module

        def load_module(self, fullname, path=None):
            return self.module

    class VimPathFinder(object):
        @classmethod
        def find_module(cls, fullname, path=None):
            try:
                return VimModuleLoader(
                    _find_module(fullname, fullname, path or _get_paths()))
            except ImportError:
                return None

        @classmethod
        def load_module(cls, fullname, path=None):
            return _find_module(fullname, fullname, path or _get_paths())

    def hook(path):
        if path == vim.VIM_SPECIAL_PATH:
            return VimPathFinder
        else:
            raise ImportError

    return hook
