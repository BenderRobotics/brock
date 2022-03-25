import os
import docker
import hashlib
import time

from typing import Optional
from brock.executors import Executor
from brock.config.config import Config
from brock.exception import ConfigError, ExecutorError


class DockerExecutor(Executor):
    '''Executor for docker based toolchains

    The executor launches the docker container automatically when needed. The
    docker image is pulled/build from Docker file during each docker container
    startup.
    '''
    _HOST_PATH = '/host'

    _RSYNC_IMAGE_NAME = 'eeacms/rsync'
    _RSYNC_IMAGE_TAG = '2.3'
    _RSYNC_PLATFORM = 'linux'
    _RSYNC_PATH = '/rsync_volume'

    def __init__(self, config: Config, name: str, help: Optional[str] = None):
        '''Initializes Docker executor

        :param config: A whole brock configuration
        :param name: Name of the executor
        :param help: Optional help message
        '''
        super().__init__(config, name, help)

        self._base_dir = config.base_dir
        hashed_path = hashlib.md5(self._base_dir.encode('ascii')).hexdigest()
        self._name = f'brock-{config.project}-{name}-{hashed_path}'

        our_conf = config.executors[name]
        self._platform = our_conf.get('platform', 'linux')

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

        self._dockerfile = our_conf.get('dockerfile', None)
        if self._dockerfile:
            image_parts = [self._name]
        else:
            image_parts = our_conf.image.split(':')

        if len(image_parts) == 2:
            self._image_name = image_parts[0]
            self._image_tag = image_parts[1]
        elif len(image_parts) == 1:
            self._image_name = image_parts[0]
            self._image_tag = 'latest'
        else:
            raise ExecutorError('Invalid executor image')

        self._volume_sync = None
        if 'sync' in our_conf:
            if our_conf.sync.type != 'rsync':
                raise ConfigError('Invalid sync type')
            self._volume_sync = 'rsync'
            self._rsync_name = f'{self._name}-rsync'
            self._rsync_volume_name = f'{self._name}-rsync-volume'
            self._sync_exclude = our_conf.sync.get('exclude', [])

        self._env = our_conf.get('env', {})
        self._prepare = our_conf.get('prepare', [])
        self._devices = our_conf.get('devices', [])
        self._sync_needed = self._volume_sync == 'rsync'

    def on_exit(self):
        if self._volume_sync == 'rsync':
            self._rsync_out()

    def status(self) -> str:
        res = 'Stopped'
        if self._is_running():
            res = 'Running'
        res += f'\n\t{self._name}'
        if self._volume_sync == 'rsync':
            res += f'\n\t{self._rsync_name}'
        return res

    def stop(self):
        if self._is_running():
            self._stop_container(self._name)
            if self._volume_sync == 'rsync':
                self._stop_container(self._rsync_name)

    def exec(self, command: str, chdir: Optional[str] = None) -> int:
        if not self._is_running():
            self._log.info('Executor not running -> starting')
            self._start()

        if self._sync_needed:
            self._rsync_in()

        directory = self._work_dir
        if chdir:
            directory = self._mount_dir + '/' + chdir
        exit_code = self._exec_command(self._name, command, directory)

        return exit_code

    def restart(self) -> int:
        self.stop()
        time.sleep(1)
        return self._start()

    def update(self):
        if self._dockerfile:
            self._build()
        else:
            self._pull_image(self._image_name, self._image_tag, self._platform)

        if self._is_running():
            self.restart()

    @property
    def _docker(self):
        try:
            return docker.from_env()
        except docker.errors.DockerException:
            raise ExecutorError('Docker engine is not running')

    def _is_running(self):
        if not self._is_container_running(self._name):
            return False
        if self._volume_sync == 'rsync' and not self._is_container_running(self._rsync_name):
            return False

        return True

    def _get_container(self, container: str):
        try:
            return self._docker.containers.get(container)
        except docker.errors.NotFound as ex:
            raise ExecutorError('Container not running')
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to get container info: {ex}')

    def _stop_container(self, name: str):
        self._log.info(f'Stopping container {name}')

        container = self._get_container(name)
        try:
            container.stop()
        except docker.errors.NotFound as ex:
            self._log.warning('Container not running')
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to stop container: {ex}')

    def _build(self):
        self._log.info(f'Building Docker image from {self._dockerfile}')
        dockerfile = os.path.join(self._base_dir, self._dockerfile)
        dockerdir = os.path.dirname(dockerfile)

        try:
            image = self._docker.images.build(path=dockerdir, platform=self._platform, tag=self._name)
        except (docker.errors.BuildError, docker.errors.APIError) as e:
            raise ExecutorError(f'Unable to build image: {str(e)}')

    def _start(self) -> int:
        if self._volume_sync == 'rsync':
            rsync_volume = self._create_volume(self._rsync_volume_name)

            volumes_rsync = {
                rsync_volume.name: {
                    'bind': self._RSYNC_PATH,
                    'mode': 'rw'
                },
                self._base_dir: {
                    'bind': self._HOST_PATH,
                    'mode': 'rw'
                }
            }

            if not self._image_exists(self._RSYNC_IMAGE_NAME, self._RSYNC_IMAGE_TAG):
                self._pull_image(self._RSYNC_IMAGE_NAME, self._RSYNC_IMAGE_TAG, self._RSYNC_PLATFORM)

            self._start_container(
                f'{self._rsync_name}',
                self._RSYNC_IMAGE_NAME,
                self._RSYNC_IMAGE_TAG,
                platform=self._RSYNC_PLATFORM,
                volumes=volumes_rsync,
                entrypoint=''
            )

            self._rsync_in()

            volumes = {rsync_volume.name: {'bind': self._mount_dir, 'mode': 'rw'}}
        else:
            volumes = {self._base_dir: {'bind': self._mount_dir, 'mode': 'rw'}}

        if not self._image_exists(self._image_name, self._image_tag):
            self.update()

        isolation = self._get_isolation(self._image_name, self._image_tag)
        self._start_container(
            self._name,
            self._image_name,
            self._image_tag,
            environment=self._env,
            platform=self._platform,
            isolation=isolation,
            volumes=volumes,
            devices=self._devices
        )

        for command in self._prepare:
            exit_code = self._exec_command(self._name, command, self._mount_dir)
            if exit_code != 0:
                return exit_code
        return 0

    def _pull_image(self, image_name, image_tag, platform):
        self._log.info(f'Pulling image {image_name}:{image_tag}')
        try:
            res = self._docker.images.pull(image_name, image_tag, platform=platform)
            self._log.debug(res)
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to pull image: {ex}')

    def _image_exists(self, image_name, image_tag):
        try:
            self._docker.images.get(f'{image_name}:{image_tag}')
        except docker.errors.ImageNotFound:
            return False
        return True

    def _get_isolation(self, image_name, image_tag):
        if self._platform != 'windows':
            return None

        image = self._docker.images.get(f'{image_name}:{image_tag}')
        info = self._docker.info()
        image_version = image.attrs['OsVersion'].split('.')[:3]
        os_version = info['OSVersion'].split('.')[:3]
        if '.'.join(image_version) == '.'.join(os_version):
            return 'process'
        return 'hyperv'

    def _is_container_running(self, name):
        try:
            self._docker.containers.get(name)
            return True
        except docker.errors.NotFound as ex:
            return False
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to get container info: {ex}')

    def _start_container(self, name, image_name, image_tag, **kwargs):
        self._log.info(f'Starting container {name}')

        if self._is_container_running(name):
            self._log.warning('Container is already running')
            return

        try:
            res = self._docker.containers.run(
                image=f'{image_name}:{image_tag}',
                name=name,
                auto_remove=True,
                detach=True,
                stdin_open=True,
                **kwargs,
            )
            self._log.debug(res)
        except docker.errors.ImageNotFound as ex:
            raise ExecutorError(f'Image {image} not found.'
                                f'Try running brock init first')
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to start container: {ex}')

    def _exec_command(self, container, command, work_dir):
        self._log.extra_info(f'Executing command in container {container}: {command}')
        self._log.debug(f'Command: {command}')
        self._log.debug(f'Work dir: {work_dir}')
        container = self._get_container(container)

        try:
            exec_id = container.client.api.exec_create(container.id, command, workdir=work_dir)['Id']
            output = container.client.api.exec_start(exec_id, stream=True, demux=True)

            try:
                for chunk in output:
                    if chunk[0]:
                        for line in chunk[0].split(b'\n'):
                            self._log.stdout(line.decode())
                    if chunk[1]:
                        for line in chunk[1].split(b'\n'):
                            self._log.stderr(line.decode())
            except KeyboardInterrupt:
                self._log.warning('Execution interrupted')

            res = container.client.api.exec_inspect(exec_id)
            exit_code = res['ExitCode']

            self._log.debug(f'Exit code: {exit_code}')

            return exit_code
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to execute command: {ex}')

    def _create_volume(self, name):
        try:
            volumes = self._docker.volumes.list()
        except docker.errors.APIError as ex:
            raise ExecutorError(f'Failed to list volumes: {ex}')

        volume = next((v for v in volumes if v.name == name), None)

        if volume is None:
            self._log.extra_info(f'Creating volume {name}')
            try:
                volume = self._docker.volumes.create(name)
            except docker.errors.APIError as ex:
                raise ExecutorError(f'Failed to create volume: {ex}')

        return volume

    def _rsync_in(self):
        self._log.extra_info(f'Rsyncing data into executor')
        self._rsync(self._HOST_PATH, self._RSYNC_PATH)
        self._sync_needed = False

    def _rsync_out(self):
        if self._sync_needed:
            # only sync out when the data were synced in before
            return
        self._log.extra_info(f'Rsyncing data out of executor')
        self._rsync(f'{self._RSYNC_PATH}/{self._work_dir_rel}', f'{self._HOST_PATH}/{self._work_dir_rel}')
        self._sync_needed = True

    def _rsync(self, src, dest, options=['-a', '--delete']):
        for exclude in self._sync_exclude:
            options.append(f"--exclude '{exclude}'")

        exit_code = self._exec_command(f'{self._rsync_name}', f"rsync {' '.join(options)} {src}/ {dest}", '/')
        if exit_code != 0:
            raise ExecutorError(f'Failed to rsync data')
