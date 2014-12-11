"""CLI for the tkinter/curses UI provided by this package."""
import StringIO
import cProfile
import click
import pstats

from .tkinter import NvimTk
from .. import attach


@click.command()
@click.option('--profile',
              default='disable',
              type=click.Choice(['ncalls', 'tottime', 'percall', 'cumtime',
                                 'disable']))
def main(profile):
    """Entry point."""
    nvim = attach('child', argv=['nvim', '--embed'])
    ui = NvimTk(nvim)
    do_profile = profile is not 'disable'
    if do_profile:
        pr = cProfile.Profile()
        pr.enable()
    ui.run()
    if do_profile:
        pr.disable()
        s = StringIO.StringIO()
        ps = pstats.Stats(pr, stream=s)
        ps.strip_dirs().sort_stats(profile).print_stats(15)
        print s.getvalue()
