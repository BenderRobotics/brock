from brock.config.config import Config


def test_full_config():
    config = Config('example_brock.yml')
    assert str(config.version) == '0.0.4'
    assert config.project == 'someprojectname'
    assert config.help == 'brock --help message'

    assert len(config.commands.keys()) == 5
    assert config.commands.default == 'build'

    assert config.commands.clean.default_executor == 'atollic'
    assert config.commands.clean.chdir == 'foo/bar'
    assert config.commands.clean.help == 'Help message for this command'
    assert config.commands.clean.steps == ['make clean']

    assert config.commands.build.depends_on == ['clean']
    assert config.commands.build.steps == ['@atollic make', 'make tests', '@host echo \'Building finished\'']

    assert config.commands.rebuild.depends_on == ['clean', 'build']

    assert len(config.commands.service.steps) == 1
    assert config.commands.service.steps[0].executor == 'atollic'
    assert config.commands.service.steps[0].shell == 'powershell'
    assert config.commands.service.steps[0].script == \
        '$ServiceName = \'EventLog\'\n$ServiceInfo = Get-Service -Name $ServiceName\nWrite-Output $ServiceInfo\n'

    assert len(config.executors.keys()) == 4

    assert config.executors.default == 'python'

    assert config.executors.atollic.type == 'docker'
    assert config.executors.atollic.help == 'Executor --help message'
    assert config.executors.atollic.dockerfile == 'path/to/Dockerfile'
    assert config.executors.atollic.platform == 'windows'
    assert len(config.executors.atollic.env.keys()) == 2
    assert config.executors.atollic.env.SOME_VAR == 'foo'
    assert config.executors.atollic.env.OTHER_VAR == 123
    assert config.executors.atollic.devices == ['class/{interface class GUID}']
    assert config.executors.atollic.default_shell == 'powershell'

    assert config.executors.python.type == 'docker'
    assert config.executors.python.image == 'python:3.9'
    assert config.executors.python.sync.type == 'rsync'
    assert config.executors.python.sync.exclude == ['foo/bar']
    assert config.executors.python.devices == ['/dev/ttyUSB0:/dev/ttyUSB0:rwm']
    assert config.executors.python.prepare == [
        'pip install -r requirements.txt',
        'echo "Foo bar"',
    ]

    assert config.executors.remote.type == 'ssh'
    assert config.executors.remote.host == 'somesite.example.com:1235'
    assert config.executors.remote.username == 'foobar'
    assert config.executors.remote.password == 'strongpassword'
