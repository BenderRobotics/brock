from __future__ import annotations
import pytest
from pathlib import Path
from copy import deepcopy
import yaml
import os
from unittest.mock import patch
import brock
from brock.cli.main import main
from brock.config.config import Config

project_template = {
    'version': '0.0.9',
    'project': 'test',
    'commands': {},
    'executors': {
        'alpine': {
            'type': 'docker',
            'image': 'alpine',
        },
    },
}
command_template = {'default_executor': 'alpine', 'options': {}, 'steps': [{'script': ''}]}


def mock_config(config: str):
    c = Config(configs=[config])
    setattr(c, 'base_dir', str(Path(__file__).parent))
    setattr(c, 'work_dir', str(Path().cwd()))

    common_prefix = os.path.commonprefix([c.work_dir, c.base_dir])
    work_dir_rel = os.path.relpath(c.work_dir, common_prefix).replace('\\', '/')
    setattr(c, 'work_dir_rel', work_dir_rel)
    return c


def create_config(options, script: str):
    command = deepcopy(command_template)
    command['options'].update(options)
    command['steps'][0]['script'] = script
    project = deepcopy(project_template)
    project['commands'].update({'test_cmd': command})
    return mock_config(yaml.dump(project))


def execute_brock(args: list[any], config: str) -> int:
    with patch('brock.cli.main.Config') as brock_config:
        with patch('brock.cli.main.exit') as exit_fn:
            brock_config.return_value = config
            main(args)

            return exit_fn.call_args[0][0]


@pytest.mark.parametrize(
    'option,args,expected', [
        ({
            'verbose': {
                'flag': '--my_flag'
            }
        }, [], ('VERBOSE', '')),
        ({
            'verbose': {
                'flag': '--my_flag'
            }
        }, ['--verbose'], ('VERBOSE', '--my_flag')),
        ({
            'verbose': {
                'flag': '--my_flag'
            }
        }, ['--verbose', '--verbose'], ('VERBOSE', '--my_flag')),
        ({
            'short-verbose': {
                'flag': '--my-flag',
                'short_name': '-v'
            }
        }, ['-v'], ('SHORT_VERBOSE', '--my-flag')),
    ]
)
def test_brock_options_flag(option, args, expected):
    """ Test combination of flags that should execute without errors. """
    config = create_config(
        option, f'printenv\n ret=$([[ "${{{expected[0]}}}" != "{expected[1]}" ]] && echo 1 || echo 0)\n exit $ret'
    )
    ret = execute_brock(['test_cmd', *args], config)
    assert ret == 0, 'Brock failed to execute a command'


@pytest.mark.parametrize(
    'option,args,expected',
    [
        ({
            'arg1': {
                'argument': 1
            }
        }, ['foo'], ('ARG1', 'foo')),
        ({
            'arg1': {
                'argument': 1
            },
            'arg2': {
                'argument': 2
            }
        }, ['foo', 'boo'], ('ARG2', 'boo')),
        ({
            'arg1': {
                'argument': 1
            },
            'arg2': {
                'argument': 4
            }
        }, ['foo', 'boo'], ('ARG2', 'boo')),  # order is important not the continuity
        ({
            'arg1': {
                'argument': 1
            },
            'arg2': {
                'argument': 2
            }
        }, ['foo'], ('ARG2', '')),
        ({
            'arg1': {
                'argument': 1,
                'required': True
            }
        }, ['foo'], ('ARG1', 'foo')),
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect']
            }
        }, ['sel'], ('ARG1', 'sel')),
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect']
            }
        }, ['ect'], ('ARG1', 'ect')),
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect'],
                'required': True
            }
        }, ['ect'], ('ARG1', 'ect')),
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect'],
                'default': 'ect'
            }
        }, [], ('ARG1', 'ect')),
        ({
            'argN': {
                'argument': '*'
            }
        }, ['arg1', 'arg2'], ('ARGN', 'arg1 arg2')),
        ({
            'argN': {
                'argument': '*'
            }
        }, [], ('ARGN', '')),
        ({
            'argN': {
                'argument': '*',
                'default': 'blob'
            }
        }, [], ('ARGN', 'blob')),
    ]
)
def test_brock_argument_valid(option, args, expected):
    """ Test combination of argument that should execute without errors. """
    config = create_config(
        option, f'printenv\n ret=$([[ "${{{expected[0]}}}" != "{expected[1]}" ]] && echo 1 || echo 0)\n exit $ret'
    )
    ret = execute_brock(['test_cmd', *args], config)
    assert ret == 0, 'Brock failed to execute a command'


@pytest.mark.parametrize(
    'option,args,expected',
    [
        ({
            'arg1': {
                'argument': 1,
                'required': True
            }
        }, [], 'ARG1'),  # argument is required
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect']
            }
        }, ['foo'], 'ARG1'),  # value is not from selection
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect']
            }
        }, [], 'ARG1'),  # value is not from selection
        ({
            'arg1': {
                'argument': 1,
                'choices': ['sel', 'ect'],
                'default': 'ect'
            }
        }, ['foo'], 'ARG1'),  # value is not from selection
    ]
)
def test_brock_argument_invalid(option, args, expected):
    """ Test combination of argument that should error. """
    config = create_config(option, f'printenv\n ret=$([[ "${{{expected}}}" != "" ]] && echo 1 || echo 0)\n exit $ret')
    ret = execute_brock(['test_cmd', *args], config)
    assert ret != 0, 'Brock failed to execute a command'


@pytest.mark.parametrize(
    'option,args,expected',
    [
        ({
            'opt1': {
                'help': ''
            }
        }, ['--opt1=foo'], ('OPT1', 'foo')),
        ({
            'opt1': {
                'short_name': '-o'
            }
        }, ['-o=boo'], ('OPT1', 'boo')),
        ({
            'opt1': {
                'short_name': '-o'
            }
        }, ['-o', 'goo'], ('OPT1', 'goo')),
        ({
            'very-slow': {
                'help': ''
            }
        }, ['--very-slow=yes'], ('VERY_SLOW', 'yes')),
        ({
            'very-slow': {
                'help': ''
            }
        }, ['--very-slow', 'no'], ('VERY_SLOW', 'no')),
        ({
            'very-slow': {
                'required': True
            }
        }, ['--very-slow', 'no'], ('VERY_SLOW', 'no')),
        ({
            'very-slow': {
                'required': True,
                'default': 'goo'
            }
        }, [], ('VERY_SLOW', 'goo')),  # ok even if required there is default
        ({
            'very-slow': {
                'choices': ['foo', 'boo']
            }
        }, ['--very-slow', 'foo'], ('VERY_SLOW', 'foo')),
        ({
            'very-slow': {
                'choices': ['foo', 'boo']
            }
        }, ['--very-slow', 'goo'], ('VERY_SLOW', 'goo')),
        ({
            'very-slow': {
                'choices': ['foo', 'boo'],
                'default': 'foo'
            }
        }, [], ('VERY_SLOW', 'foo')),
        ({
            'very-slow': {
                'required': True,
                'choices': ['foo', 'boo'],
                'default': 'foo'
            }
        }, [], ('VERY_SLOW', 'foo')),  # ok even if required there is default
        ({
            'very-slow': {
                'short_name': '-v',
                'choices': ['foo', 'boo'],
                'default': 'foo'
            }
        }, ['-v', 'foo'], ('VERY_SLOW', 'foo')),
    ]
)
def test_brock_option_valid(option, args, expected):
    """ Test combination of option that should execute without error. """
    config = create_config(
        option, f'printenv\n ret=$([[ "${{{expected[0]}}}" != "{expected[1]}" ]] && echo 1 || echo 0)\n exit $ret'
    )
    ret = execute_brock(['test_cmd', *args], config)
    assert ret == 0, 'Brock failed to execute a command'


@pytest.mark.parametrize(
    'option,args,expected',
    [
        ({
            'very-slow': {
                'required': True
            }
        }, [], 'VERY_SLOW'),  # missing required thing
        ({
            'very-slow': {
                'short_name': '-v',
                'required': True
            }
        }, [], 'VERY_SLOW'),  # no choices without default
        ({
            'very-slow': {
                'choices': ['foo', 'boo'],
                'required': True
            }
        }, [], 'VERY_SLOW'),  # no choices without default
        ({
            'very-slow': {
                'choices': ['foo', 'boo']
            }
        }, ['--very-slow', 'goo'], 'VERY_SLOW'),  # invalid choices
        ({
            'very-slow': {
                'choices': ['foo', 'boo']
            }
        }, ['--very-slow'], 'VERY_SLOW'),  # expected value after option
        ({
            'very-slow': {
                'choices': ['foo', 'boo'],
                'default': 'goo'
            }
        }, [], 'VERY_SLOW'),  # invalid default
    ]
)
def test_brock_option_invalid(option, args, expected):
    """ Test combination of option that should error. """
    config = create_config(option, f'printenv\n ret=$([[ "${{{expected}}}" != "" ]] && echo 1 || echo 0)\n exit $ret')
    ret = execute_brock(['test_cmd', *args], config)
    assert ret != 0, 'Brock failed to execute a command'
