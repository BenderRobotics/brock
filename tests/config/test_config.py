import pytest

from brock import __version__
from brock.config.config import Config
from brock.exception import ConfigError


def test_example_config():
    '''Test the config attached as an example.'''
    config = Config(['example_brock.yml'])
    assert str(config.version) == '0.1.0'
    assert config.project == 'someprojectname'
    assert config.help == 'brock --help message'

    assert len(config.commands.keys()) == 5
    assert config.commands.default == 'build'

    assert config.commands.clean.default_executor == 'atollic'
    assert config.commands.clean.chdir == 'foo/bar'
    assert config.commands.clean.help == 'Help message for this command'
    assert config.commands.clean.steps == ['make clean']

    assert config.commands.build.depends_on == ['clean']
    assert config.commands.build.steps == [
        '@atollic make', 'make tests', '@host echo \'Building finished\'', 'run ${VERY_FAST}', 'run ${VERY_SLOW}',
        'run ${SPEED}'
    ]

    assert config.commands.rebuild.depends_on == ['clean', 'build']

    assert len(config.commands.service.steps) == 1
    assert config.commands.service.steps[0].executor == 'atollic'
    assert config.commands.service.steps[0].shell == 'powershell'
    assert config.commands.service.steps[0].script == \
        '$ServiceName = \'EventLog\'\n$ServiceInfo = Get-Service -Name $ServiceName\nWrite-Output $ServiceInfo\n'

    assert len(config.executors.keys()) == 5

    assert config.executors.default == 'python'

    assert config.executors.atollic.type == 'docker'
    assert config.executors.atollic.help == 'Executor --help message'
    assert config.executors.atollic.dockerfile == 'path/to/Dockerfile'
    assert config.executors.atollic.platform == 'windows'
    assert len(config.executors.atollic.env.keys()) == 2
    assert config.executors.atollic.env.SOME_VAR == 'foo'
    assert config.executors.atollic.env.OTHER_VAR == 123
    assert config.executors.atollic.mac_address == '88:99:aa:bb:cc:dd'
    assert config.executors.atollic.ports == {5000: 5000, '6000/udp': 6000}
    assert config.executors.atollic.devices == ['class/{interface class GUID}']
    assert config.executors.atollic.default_shell == 'powershell'

    assert config.executors.python.type == 'docker'
    assert config.executors.python.image == 'python:3.9'
    assert config.executors.python.sync.type == 'rsync'
    assert config.executors.python.sync.options == ['-avm']
    assert config.executors.python.sync.filter == ['+ foo/', '+ foo/**/', '+ foo/**.c', '+ foo/src/**', '- *']
    assert config.executors.python.sync.include == ['foo/bar']
    assert config.executors.python.sync.exclude == ['foo/bar']
    assert config.executors.python.devices == ['/dev/ttyUSB0:/dev/ttyUSB0:rwm']
    assert config.executors.python.prepare == [
        'pip install -r requirements.txt',
        'echo "Foo bar"',
    ]

    assert config.executors.gcc.type == 'docker'
    assert config.executors.gcc.image == 'gcc'
    assert config.executors.gcc.sync.type == 'mutagen'

    assert config.executors.remote.type == 'ssh'
    assert config.executors.remote.host == 'somesite.example.com:1235'
    assert config.executors.remote.username == 'foobar'
    assert config.executors.remote.password == 'strongpassword'


def test_empty_config():
    '''Test empty config raises error (#5813).'''
    with pytest.raises(ConfigError) as ex:
        config = Config(['\n'])
    assert ex.value.message == 'Invalid config file: Config file is empty'


def test_invalid_version():
    '''Test invalid config version raises error - config version must be lower or equal to brock version.'''
    with pytest.raises(ConfigError) as ex:
        config = Config(['version: 5.0.0\nproject: test\n'])
    assert ex.value.message.startswith('Current config requires Brock of version at least')


def test_multiple_configs_in_one_dir():
    '''Test multiple config files in one directory raises error.'''
    with pytest.raises(ConfigError) as ex:
        config = Config(config_file_names=['example_brock.yml', '.brock.yml'])
    assert ex.value.message.startswith('Multiple brock config files found in')


def test_empty_executors():
    '''Test executors config section is empty or missing.'''
    config = Config(['version: 0.0.6\nproject: test\nexecutors: {}\n'])
    assert len(config.executors) == 0

    config = Config(['version: 0.0.6\nproject: test\n'])
    assert len(config.executors) == 0
