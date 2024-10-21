import click
from typing import Optional

from brock.exception import UsageError, BaseBrockException
from brock.log import get_logger, init_logging
from .state import State, pass_state
from click.exceptions import ClickException

init_logging()
log = get_logger()


class ArgumentWithHelp(click.Argument):

    def __init__(self, param_decls, required=None, help=None, **attrs):
        super().__init__(param_decls, required=required, **attrs)
        self.help = help

    def get_help_record(self, ctx):
        """Return help record for custom argument if needed by a custom help command."""
        if self.help:
            return (f'<{self.human_readable_name}>', self.help)
        return None


def create_command(cmd: str, help: Optional[str] = None):
    '''Returns click command function for brock commands'''

    @click.command(name=cmd, help=help)
    @pass_state
    def f(state):
        return state.project.exec(cmd)

    return f


def create_command_with_options(cmd: str, options: dict, help: Optional[str] = None):
    '''Returns click command function for brock commands'''
    click_options = []
    for option_n, value in options.items():
        if value.flag is not None:
            if value.short_name is not None:
                click_options.append(
                    click.Option(
                        param_decls=[f'--{option_n}', value.short_name], flag_value=value.flag, help=value.help
                    )
                )
            else:
                click_options.append(
                    click.Option(param_decls=[f'--{option_n}'], flag_value=value.flag, help=value.help)
                )
        elif value.argument is not None:
            if '*' == value.argument:
                click_options.append(
                    ArgumentWithHelp(param_decls=[option_n], required=value.required, nargs=-1, help=value.help)
                )
            else:
                click_options.insert(
                    int(value.argument) - 1,
                    ArgumentWithHelp(param_decls=[option_n], required=value.required, help=value.help)
                )
        elif value.option:
            if value.choice:
                mapping_table = str.maketrans({',': '|', ' ': '', "'": '', '[': '(', ']': ')'})
                help_opt = f'{value.help} {str(value.choice).translate(mapping_table)}'
            else:
                help_opt = f'{value.help}'
            if value.required and value.default is not None:
                if value.short_name is not None:
                    click_options.append(
                        click.Option(
                            param_decls=[f'--{option_n}', value.short_name], help=help_opt, flag_value=value.default
                        )
                    )
                else:
                    click_options.append(
                        click.Option(param_decls=[f'--{option_n}'], help=help_opt, default=value.default)
                    )
            else:
                if value.short_name is not None:
                    click_options.append(
                        click.Option(
                            param_decls=[f'--{option_n}', value.short_name], help=help_opt, required=value.required
                        )
                    )
                else:
                    click_options.append(
                        click.Option(param_decls=[f'--{option_n}'], help=help_opt, required=value.required)
                    )

    @click.command(name=cmd, help=help, params=click_options)
    @pass_state
    def f(state, **kwargs):
        for option_n, value in options.items():
            current_value_name = value.name.replace('-', '_').lower()
            if current_value_name in kwargs:
                if value.option and value.short_name is not None:
                    try:
                        if '=' in kwargs[current_value_name]:
                            kwargs[current_value_name] = kwargs[value.name].replace('=', '')
                    except TypeError:
                        pass
                if value.default is not None and (
                    kwargs[current_value_name] is None or 0 == len(kwargs[current_value_name])
                ):
                    kwargs[current_value_name] = value.default
                if value.argument is not None:
                    if value.choice or (kwargs[value.name.lower()] is None and value.choice):
                        val = check_choice(kwargs[value.name.lower()], value.choice)

        step_options = {key: kwargs[key] for key in kwargs if kwargs[key] is not None}
        return state.project.exec(cmd, step_options)

    return f


def check_choice(option, choice_list):
    if choice_list:
        if option not in choice_list:
            raise BaseBrockException('Provided option is not in a set choice list')
        else:
            return True


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
