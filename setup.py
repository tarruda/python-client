import platform
import sys

from setuptools import setup

install_requires = [
    'click>=3.0',
    'msgpack-python>=0.4.0',
]

if sys.version_info < (3, 4):
    # trollius is just a backport of 3.4 asyncio module
    install_requires.append('trollius')

if not platform.python_implementation() == 'PyPy':
    # pypy already includes an implementation of the greenlet module
    install_requires.append('greenlet')

setup(name='neovim',
      version='0.0.25',
      description='Python client to neovim',
      url='http://github.com/neovim/python-client',
      download_url='https://github.com/neovim/python-client/archive/0.0.25.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='MIT',
      packages=['neovim', 'neovim.api', 'neovim.msgpack_rpc',
                'neovim.msgpack_rpc.event_loop', 'neovim.plugin',
                'neovim.ui'],
      install_requires=install_requires,
      entry_points='''
      [console_scripts]
      pynvim=neovim.ui.cli:main
      ''',
      zip_safe=False)
