# Bender Robotics command management system
Brock is a Python-based automation tool for launching commands in various
executors like Docker or remote systems. It was designed mainly for building
and testing automation of embedded software in Docker-based executors.


## Installation

### Prerequisities
Brock needs Docker to be installed and configured properly:
1. Install [Windows Subsystem for Linux 2](https://docs.microsoft.com/cs-cz/windows/wsl/install-win10).
2. Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop).
3. Switch to Windows containers if the executor is Windows-based - click Docker
   Desktop icon and select Switch to Windows containers... (requires Windows Pro
   or Enterprise), or turn experimental features on - open Docker Desktop, go to
   Settings -> Docker Engine, set `"experimental": true` (allows to use Linux
   and Windows containers simultaneously).

### Brock
You can install Brock from BR's pypi, download wheel from release page or
build it yourself - see [Contributing](#Contributing)...
```shell
$ pip install brock
```

## Usage
Brock scans all directories from drive root to current directory and looks
for `.brock.yml` config files. The format of the files is described in
[example_brock.yml](example_brock.yml).

The configuration files are merged together, the highest priority config file
is the one in the current directory. Individual config files don't have to be
complete, however, the merged configuration must contain all required
parameters.

The lowest priority config file determines the base directory which will be
used as a working directory for the executor (e.g. mounted to docker, mounted
over SSH). The commands should not access files outside this directory.

The list of all available commands is provided by `brock --help`, let's assume
a command `test` was defined in the `.brock.yml`, you can run it like this:
```shell
$ brock test
>> Executor not running -> starting
>> Pulling image python:3.9
./debug/test -s

Unity test run 1 of 1

-----------------------
483 Tests 0 Failures 0 Ignored
OK
```

If the required executor is not running, it is started automatically when
executing a command. It stays running until it is explicitly stopped by
`brock --stop`. The executors can also be restarted (e.g. to fetch changes in
the brock configuration) by `brock --restart`. The current state of the
executors is printed by `brock --status`.

The docker image can be pulled again or rebuilt (if using Dockerfile) using
`brock --update`.

If needed, you can launch a custom command directly in the executor by
`brock exec`:
```shell
$ brock exec @python 'python --version'
Python 3.9.10
```

Optionally, quotes or double-dash (`--`) can be used to avoid brock collecting
options destined to the command launched by executor:
```shell
$ brock exec @python "python --version"
Python 3.9.10
$ brock exec @python -- python --version
Python 3.9.10

If using a custom Docker registry, do not forget to login into the registry
before using `brock` - use full registry path including image name and tag:
```shell
$ docker login $IMAGE_REGISTRY
Username: $USER_NAME
Password:
Login Succeeded
```

If using Docker executor, you can launch a shell using `brock shell` (default
executor will be used if ommited):
```shell
$ brock shell @gcc
root@6bf119cb7b6a:/host# exit
exit
```

Brock sets the following predefined environmental variables:
- `BROCK_HOST_PATH` - absolute path to current directory on host
- `BROCK_HOST_PROJECT_PATH` - absolute path to project root on host
- `BROCK_RELATIVE_PATH` - relative path from project root to current directory

Additional variables can be set using the config option `env` for each executor.

#### Options
Brock offers the possibility of options in commands.
Configuration of options in .brock.yaml (see example_brock.yml)

opt-name:
- flag: str | None -> option is a flag e.g. `brock build --verbose`

- argument: str | None  -> option is an argument e.g. `brock build something`,
can be * then an unlimited number of arguments is accepted

- default: any | None -> any value

- choice: list[str] -> list of acceptable values, brock checks input is in choice and also displays it in help

- variable: str | None -> optional custom name of the variable inside the session, to avoid any conflicts with built-in variables

- help: str | None


### Isolation types
The Brock can detect Windows version and the version of the Windows Docker
image, the needed isolation mode is determined automatically - if possible,
the image is started in `process` isolation, `hyperv` is used otherwise.

### Volume synchronization
To achieve satisfactory performance when using Linux containers on Windows
(or macOS), the project folder needs to be mounted more efficiently. For this
purpose, two volume synchronization mechanisms are available: Rsync or Mutagen.

#### Rsync
An additional container with Rsync is started - the project folder is mounted to
this container together with a named volume (that will reside inside the Linux
host) and these folders are then being synced using Rsync. To turn this feature
on, use the `sync` option in the config file.

Optionally, specific files/folders can be excluded from sync using
configuration option `exclude` under `sync` section.

#### Mutagen
Another option to synchronize volumes on macOS or Windows is to use
[Mutagen Extension](https://mutagen.io/documentation/docker-desktop-extension)
for Docker Desktop. Before use, it must be installed first:
```shell
docker extension install mutagenio/docker-desktop-extension:latest
```
Then, a cache must be created for each path which should be synchronized. Go to
Docker Desktop -> Extensions -> Mutagen, click Create Cache and enter the
project root path. Finally, configure the executor to use Mutagen
volume synchronization (see `example_brock.yml`).

### Devices in Docker executor
The docker can use the system devices if passed correctly, however this only
works when running a native container - e.g. a Windows container with the same
system version as the Windows host, or a Linux container under a Linux host.
Check the `devices` section of the config file.


## Build
Please first apply all steps in [contributing section](#Contributing).

After that you can call build scripts:
```shell
$ python build/build.py  # builds the package
```
You can find build artifacts in the newly created dist folder.

## Contributing
Here is a short guide to ease you up contributing.

Start by installing virtual environment package
```shell
$ pip install virtualenv
```
Then create your own virtual environment
```shell
$ virtualenv venv
```
Now you should see venv folder in the project structure.
Activate virtual environment
```shell
$ source venv/bin/activate  # on linux
$ venv\Scripts\activate.bat # on windows
```
After that you should see (venv) as prefix to your command line cursor.
Note you need to repeat activation every time you close the terminal.

To install the package in development mode call:
```shell
$ pip install -e .
```
Now you can call Brock directly from the command line and all changes to the
source code are instantly applied.
