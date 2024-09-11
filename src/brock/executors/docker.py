import os
import sys
import subprocess
import docker
import time

from typing import Optional, Union, Sequence, Dict, List, Any, Union
from brock.log import get_logger
from brock.executors import Executor
from brock.config.config import Config
from brock.exception import ConfigError, ExecutorError


class Container:
    '''Docker container abstraction'''

    def __init__(
        self,
        name: str,
        platform: Optional[str] = 'linux',
        image: Optional[str] = None,
        dockerfile: Optional[str] = None,
        env: Dict[str, Any] = {},
        mac_address: str = None,
        ports: Dict[Union[str, int], int] = {},
        devices: List[str] = [],
        volumes: Dict[str, Dict[str, Any]] = {},
        run_endpoint: str = None
    ):
        self.name = name
        self._platform = platform
        self._dockerfile = dockerfile
        self._env = env
        self._mac_address = mac_address
        self._ports = ports
        self._devices = devices
        self._volumes = volumes
        self._run_endpoint = run_endpoint

        self._log = get_logger()

        if self._dockerfile:
            image_parts = [self.name]
        elif image:
            image_parts = image.split(':')
        else:
            raise ExecutorError('Image or dockerfile must be defined')

        if len(image_parts) == 2:
            self._image_name = image_parts[0]
            self._image_tag = image_parts[1]
        elif len(image_parts) == 1:
            self._image_name = image_parts[0]
            self._image_tag = 'latest'
        else:
            raise ExecutorError('Invalid docker image')

    @property
    def _docker_run(self) -> docker.DockerClient:
        try:
            if self._run_endpoint:
                return docker.DockerClient(base_url=self._run_endpoint)
            else:
                return docker.from_env()
        except docker.errors.DockerException:
            raise ExecutorError('Docker engine is not running')

    @property
    def _docker(self) -> docker.DockerClient:
        try:
            return docker.from_env()
        except docker.errors.DockerException:
            raise ExecutorError('Docker engine is not running')

    @property
    def _container(self):
        try:
            return self._docker.containers.get(self.name)
        except docker.errors.NotFound:
            raise ExecutorError('Docker container not found')

    @property
    def _image(self):
        try:
            return self._docker.images.get(f'{self._image_name}:{self._image_tag}')
        except docker.errors.ImageNotFound:
            return None

    @property
    def _isolation(self) -> Optional[str]:
        if self._platform == 'windows':
            if self._image is None:
                raise ExecutorError('Docker is probably switched to incorrect platform')
            image_version = self._image.attrs['OsVersion'].split('.')[:3]
            info = self._docker.info()
            os_version = info['OSVersion'].split('.')[:3]
            if '.'.join(image_version) == '.'.join(os_version):
                return 'process'
            return 'hyperv'
        return None

    def _create_volumes(self) -> None:
        '''Creates named volumes used by the container'''
        try:
            volumes = map(lambda x: x.name, self._docker.volumes.list())
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to list volumes: {ex}')

        for name in self._volumes:
            # volume tied to physical path
            if os.path.exists(name):
                continue

            if name not in volumes:
                self._log.extra_info(f'Creating volume {name}')
                try:
                    self._docker.volumes.create(name)
                except docker.errors.APIError as ex:
                    raise ExecutorError(f'Failed to create volume: {ex}')

    def _build(self):
        self._log.info(f'Building Docker image from {self._dockerfile}')
        dockerdir = os.path.dirname(self._dockerfile)
        try:
            generator = self._docker.api.build(
                path=dockerdir, platform=self._platform, tag=f'{self._image_name}:{self._image_tag}', decode=True
            )
            try:
                for chunk in generator:
                    if 'stream' in chunk:
                        print(chunk['stream'], end='')
            except KeyboardInterrupt:
                self._log.warning('Execution interrupted')

        except (docker.errors.BuildError, docker.errors.APIError) as e:
            raise ExecutorError(f'Unable to build image: {str(e)}')

    def _pull(self):
        self._log.info(f'Pulling image {self._image_name}:{self._image_tag}')
        try:
            generator = self._docker.api.pull(
                self._image_name, self._image_tag, platform=self._platform, stream=True, decode=True
            )
            try:
                for chunk in generator:
                    if 'progress' not in chunk and 'status' in chunk:
                        print(f"{chunk.get('id', '')} -> {chunk['status']}")
            except KeyboardInterrupt:
                self._log.warning('Execution interrupted')

        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to pull image: {ex}')

    def is_running(self) -> bool:
        try:
            self._docker.containers.get(self.name)
        except docker.errors.NotFound as ex:
            return False
        return True

    def start(self) -> None:
        if self.is_running():
            return

        if self._image is None:
            self.update()

        self._log.info(f'Starting container {self.name}')
        self._create_volumes()
        try:
            res = self._docker_run.containers.run(
                image=f'{self._image_name}:{self._image_tag}',
                name=self.name,
                auto_remove=True,
                detach=True,
                stdin_open=True,
                environment=self._env,
                mac_address=self._mac_address,
                ports=self._ports,
                platform=self._platform,
                isolation=self._isolation,
                devices=self._devices,
                volumes=self._volumes,
            )
            self._log.debug(res)
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to start container: {ex}')

    def stop(self) -> None:
        if not self.is_running():
            return
        self._log.info(f'Stopping container {self.name}')
        self._container.stop()

    def update(self) -> None:
        if self._dockerfile:
            self._build()
        else:
            self._pull()

        if self.is_running():
            self.stop()

    def exec(self, command: Union[str, Sequence[str]], work_dir: str) -> int:
        if not self.is_running():
            self.start()

        self._log.extra_info(f'Executing command in container {self.name}: {command}')
        self._log.debug(f'Work dir: {work_dir}')

        try:
            exec_id = self._container.client.api.exec_create(
                self._container.id, command, workdir=work_dir, environment=self._env
            )['Id']
            output = self._container.client.api.exec_start(exec_id, stream=True, demux=True)
            try:
                for chunk in output:
                    if chunk[0]:
                        print(chunk[0].decode('utf-8', 'replace'), end='')
                    if chunk[1]:
                        print(chunk[1].decode('utf-8', 'replace'), end='', file=sys.stderr)
            except KeyboardInterrupt:
                self._log.warning('Execution interrupted')

            res = self._container.client.api.exec_inspect(exec_id)
            exit_code = res['ExitCode']

            self._log.debug(f'Exit code: {exit_code}')
            return exit_code
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to execute command: {ex}')

    def shell(self, shell: str, work_dir: str) -> int:
        if not self.is_running():
            self.start()

        command = ['docker', 'exec', '-it', '-w', work_dir, self.name, shell]

        self._log.extra_info(f'Starting shell ({shell}) in container {self.name}')
        self._log.debug(f'Work dir: {work_dir}')
        return subprocess.run(command, env=self._env).returncode


class DockerExecutor(Executor):
    '''Executor for docker based toolchains

    The executor launches the docker container automatically when needed. If the
    image is not found, it's pulled before first run.
    '''
    _HOST_PATH = '/host'
    _RSYNC_PATH = '/rsync_volume'

    def __init__(self, config: Config, name: str):
        '''Initializes Docker executor

        :param config: A whole brock configuration
        :param name: Name of the executor
        '''
        super().__init__(config, name)

        self._platform = self._conf.get('platform', 'linux')
        self._prepare = self._conf.get('prepare', [])

        self.env_vars.update(self._conf.get('env', {}))

        if self._default_shell is None:
            if self._platform == 'windows':
                self._default_shell = 'cmd'
            else:
                self._default_shell = 'sh'

        if self._platform == 'windows':
            self._mount_dir = f'C:{self._HOST_PATH}'
        else:
            self._mount_dir = self._HOST_PATH
        self._work_dir_rel = config.work_dir_rel.replace('\\', '/')
        self._work_dir = os.path.join(self._mount_dir, self._work_dir_rel).replace('\\', '/')

        if 'sync' in self._conf:
            self._sync_options = self._conf.sync.get('options', None)
            self._sync_filter = self._conf.sync.get('filter', [])
            self._sync_include = self._conf.sync.get('include', [])
            self._sync_exclude = self._conf.sync.get('exclude', [])
            self._sync_type = self._conf.sync.type
        else:
            self._sync_type = None
        self._synced_in = False
        run_endpoint = None
        if self._sync_type == 'rsync':
            self._sync_exclude = self._conf.sync.get('exclude', [])

            self._rsync_volume_name = f'{config.project}-rsync-volume-{self._hashed_base_dir}'
            self._rsync_container = None

            self._rsync_container = Container(
                f'brock-{config.project}-rsync-{self._hashed_base_dir}',
                platform='linux',
                image='eeacms/rsync:2.3',
                volumes={
                    self._rsync_volume_name: {
                        'bind': self._RSYNC_PATH,
                        'mode': 'rw'
                    },
                    self._base_dir: {
                        'bind': self._HOST_PATH,
                        'mode': 'rw'
                    }
                }
            )
            volumes = {self._rsync_volume_name: {'bind': self._mount_dir, 'mode': 'rw'}}
        elif self._sync_type == 'mutagen':
            try:
                contexts = docker.context.ContextAPI.contexts()
                context = next(c for c in contexts if c.name == 'desktop-linux-mutagen')
                run_endpoint = context.endpoints['docker']['Host']
            except:
                self._log.warning('Failed to get mutagen context, is Mutagen Extension for Docker Desktop installed?')

            volumes = {self._base_dir: {'bind': self._mount_dir, 'mode': 'rw'}}
        else:
            volumes = {self._base_dir: {'bind': self._mount_dir, 'mode': 'rw'}}

        dockerfile = None
        if 'dockerfile' in self._conf:
            dockerfile = os.path.join(self._base_dir, self._conf['dockerfile'])

        self._container = Container(
            f'brock-{config.project}-{name}-{self._hashed_base_dir}',
            platform=self._platform,
            image=self._conf.get('image'),
            dockerfile=dockerfile,
            env=self.env_vars,
            mac_address=self._conf.get('mac_address', None),
            ports=self._conf.get('ports'),
            devices=self._conf.get('devices', []),
            volumes=volumes,
            run_endpoint=run_endpoint,
        )

    def sync_in(self):
        if self._sync_type is None:
            return

        if self._sync_type == 'rsync':
            if self._rsync_container is None:
                return
            self._log.extra_info(f'Rsyncing data into docker volume')
            self._rsync(self._HOST_PATH, self._RSYNC_PATH)
        elif self._sync_type == 'mutagen':
            pass
        else:
            raise ExecutorError('Unknown sync type')

        self._synced_in = True

    def sync_out(self):
        if not self._synced_in:
            return

        if self._sync_type == 'rsync':
            if self._rsync_container is None:
                return
            self._log.extra_info(f'Rsyncing data out of docker volume')
            self._rsync(self._RSYNC_PATH, self._HOST_PATH)
        elif self._sync_type == 'mutagen':
            pass
        else:
            raise ExecutorError('Unknown sync type')

        self._synced_in = False

    def status(self) -> str:
        res = 'Stopped'
        if self._container.is_running() and (self._rsync_container is None or self._rsync_container.is_running()):
            res = 'Running'
        res += f'\n\t{self._container.name}'
        if self._rsync_container is not None:
            res += f'\n\t{self._rsync_container.name}'
        return res

    def stop(self):
        self._container.stop()
        if 'sync' in self._conf and self._sync_type == 'rsync' and self._rsync_container:
            self._rsync_container.stop()

    def restart(self) -> int:
        self.stop()
        time.sleep(1)
        return self._start()

    def update(self):
        self._container.update()

    def exec(
        self,
        command: Union[str, Sequence[str]],
        chdir: Optional[str] = None,
        env_options: Optional[dict] = None
    ) -> int:
        if env_options is not None:
            self.env_vars.update(env_options)
        if not self._container.is_running():
            self._log.info('Executor not running -> starting')
            exit_code = self._start()
            if exit_code != 0:
                return exit_code
        if not self._synced_in:
            self.sync_in()

        directory = self._work_dir
        if chdir:
            directory = self._mount_dir + '/' + chdir
        return self._container.exec(command, directory)

    def shell(self) -> int:
        if not self._container.is_running():
            self._log.info('Executor not running -> starting')
            self._start()

        if not self._synced_in:
            self.sync_in()

        shell = self.default_shell
        if shell is None:
            raise ExecutorError('Shell is not defined')

        return self._container.shell(shell, self._work_dir)

    def _start(self) -> int:
        if self._container.is_running():
            return 0

        self.sync_in()
        self._container.start()
        for command in self._prepare:
            exit_code = self._container.exec(command, self._mount_dir)
            if exit_code != 0:
                self._log.error('Failed to execute prepare steps')
                self._container.stop()
                return exit_code
        return 0

    def _rsync(self, src: str, dest: str):
        if self._rsync_container is None:
            return 0

        if self._sync_options is not None:
            options = []
            for option in self._sync_options:
                options.append(f'{option}')
        else:
            # use default options
            options = ['-a', '--delete']

        for filter_ in self._sync_filter:
            options.append(f"--filter '{filter_}'")
        for include in self._sync_include:
            options.append(f"--include '{include}'")
        for exclude in self._sync_exclude:
            options.append(f"--exclude '{exclude}'")

        exit_code = self._rsync_container.exec(f"rsync {' '.join(options)} {src}/ {dest}", '/')
        if exit_code != 0:
            raise ExecutorError(f'Failed to rsync data')
        return exit_code
