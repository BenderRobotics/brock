import click

import brock.log as log


class State:

    def __init__(self, project):
        self.verbosity = 0
        self.no_color = False
        self.project = project
        self.error = None


def set_verbosity(ctx, param, value):
    if value == 0:
        log.VERBOSITY = log.INFO
    elif value == 1:
        log.VERBOSITY = log.EXTRA_INFO
    else:
        log.VERBOSITY = log.DEBUG

    state = ctx.find_object(State)
    if state:
        state.verbosity = value
        state.project.update_logger()

    return value


def set_no_color(ctx, param, value):
    if value:
        log.LOGGER = 'normal'

    state = ctx.find_object(State)
    if state:
        state.no_color = value
        state.project.update_logger()

    return value


pass_state = click.make_pass_decorator(State)
