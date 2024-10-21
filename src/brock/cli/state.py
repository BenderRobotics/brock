import click

import brock.log as log
from brock import __version__
from brock.cli.analytics import init_analytics


class State:

    def __init__(self, project):
        self.verbosity = 0
        self.no_color = False
        self.project = project
        self.error = None


def set_verbosity(ctx, param, value):
    if value == 0:
        log.set_verbosity(log.INFO)
    elif value == 1:
        log.set_verbosity(log.EXTRA_INFO)
    else:
        log.set_verbosity(log.DEBUG)

    state = ctx.find_object(State)
    if state:
        state.verbosity = value

    return value


def set_analytics(ctx, param, analytics_disabled):
    if not analytics_disabled:
        init_analytics(False)


def set_analytics_dev(ctx, param, enable_dev_analytics):
    if enable_dev_analytics:
        init_analytics(True)


def set_no_color(ctx, param, value):
    if value:
        log.disable_color()

    state = ctx.find_object(State)
    if state:
        state.no_color = value

    return value


pass_state = click.make_pass_decorator(State)
