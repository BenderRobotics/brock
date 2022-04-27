import click
from typing import Optional

from brock.exception import UsageError
from .state import State, pass_state


def create_command(cmd: str, help: Optional[str] = None):
    '''Returns click command function for brock commands'''

    @click.command(name=cmd, help=help)
    @pass_state
    def f(state):
        return state.project.exec(cmd)

    return f


@click.command()
@click.argument('executor', required=False)
@pass_state
def shell(state: State, executor=None):
    '''Open shell in executor'''
    if not executor:
        executor = state.project.default_executor
        if not executor:
            raise UsageError('Multiple executors available, you have to specify which one to use')
    elif executor[0] != '@':
        raise UsageError('Unknown executor name format, use @name')
    else:
        executor = executor[1:]

    return state.project.shell(executor)


@click.command()
@click.argument('input', nargs=-1, type=click.Path())
@pass_state
def exec(state: State, input=None):
    '''Run command in executor'''
    if len(input) == 0:
        raise UsageError('No command specified')
    elif input[0][0] != '@':
        executor = state.project.default_executor
        if not executor:
            raise UsageError('Multiple executors available, you have to specify which one to use')
        executor = '@' + executor
        command = input
    else:
        if len(input) < 2:
            raise UsageError('No command specified')
        executor = input[0]
        command = input[1:]

    executor = executor[1:]
    return state.project.exec_raw(' '.join(command), executor)
