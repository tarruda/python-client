"""CLI for the tkinter/curses UI provided by this package."""
import click
import shlex

from .tkinter import NvimTk
from .. import attach


@click.command(context_settings=dict(allow_extra_args=True))
@click.option('--nvim-command', default='nvim --embed')
@click.option('--profile',
              default='disable',
              type=click.Choice(['ncalls', 'tottime', 'percall', 'cumtime',
                                 'disable']))
@click.pass_context
def main(ctx, nvim_command, profile):
    """Entry point."""
    nvim = attach('child', argv=shlex.split(nvim_command) + ctx.args)
    ui = NvimTk(nvim)
    do_profile = profile != 'disable'
    if do_profile:
        import StringIO
        import cProfile
        import pstats
        pr = cProfile.Profile()
        pr.enable()
    ui.run()
    if do_profile:
        pr.disable()
        s = StringIO.StringIO()
        ps = pstats.Stats(pr, stream=s)
        ps.strip_dirs().sort_stats(profile).print_stats(30)
        print s.getvalue()
