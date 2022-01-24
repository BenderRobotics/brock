import os
import docker

from brock.exception import ToolchainError
from brock.log import getLogger


class Toolchain:
    _HOST_PATH = "/host"

    _RSYNC_IMAGE_NAME = "eeacms/rsync"
    _RSYNC_IMAGE_TAG = "2.3"
    _RSYNC_PLATFORM = "linux"
    _RSYNC_PATH = "/rsync_volume"

    def __init__(self, config):
        self._name = f"brock-{config.project.name}"
        self._base_dir = config.base_dir

        if config.toolchain.platform == "windows":
            self._mount_dir = f"C:{self._HOST_PATH}"
        else:
            self._mount_dir = self._HOST_PATH
        self._work_dir_rel = config.work_dir_rel.replace("\\", "/")
        self._work_dir = os.path.join(self._mount_dir, self._work_dir_rel).replace("\\", "/")

        image_parts = config.toolchain.image.split(':')
        if len(image_parts) == 2:
            self._image_name = image_parts[0]
            self._image_tag = image_parts[1]
        elif len(image_parts) == 1:
            self._image_name = image_parts[0]
            self._image_tag = "latest"
        else:
            raise ToolchainError("Invalid toolchain image")

        self._platform = config.toolchain.get("platform", "linux")
        self._isolation = config.toolchain.get("isolation", None)
        self._volume_sync = config.toolchain.get("volume_sync", None)
        if self._volume_sync == "rsync":
            self._rsync_name = f"{self._name}-rsync"
            self._rsync_volume_name = f"{self._name}-rsync-volume"

        self._log = getLogger()
        self._docker = docker.from_env()

    def get_state(self):
        try:
            image_name = f"{self._image_name}:{self._image_tag}"
            self._docker.images.get(image_name)
            self._log.info(f"Image {image_name} is ready")
        except docker.errors.NotFound as ex:
            self._log.warning(f"Image {image_name} not found")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to get image info: {ex}")

        if self._is_container_running(self._name):
            self._log.info(f"Container {self._name} is running")
        else:
            self._log.warning(f"Container {self._name} is not running")

    def is_running(self):
        if not self._is_container_running(self._name):
            return False
        if self._volume_sync == "rsync" and not self._is_container_running(self._rsync_name):
            return False

        return True

    def pull(self):
        self._pull_image(self._image_name, self._image_tag, self._platform)

        if self._volume_sync == "rsync":
            self._pull_image(self._RSYNC_IMAGE_NAME, self._RSYNC_IMAGE_TAG, self._RSYNC_PLATFORM)

    def start(self):
        if self._volume_sync == "rsync":
            rsync_volume = self._create_volume(self._rsync_volume_name)

            volumes_rsync = {
                rsync_volume.name: {
                    "bind": self._RSYNC_PATH,
                    "mode": "rw"
                },
                self._base_dir: {
                    "bind": self._HOST_PATH,
                    "mode": "rw"
                }
            }

            self._start_container(
                f"{self._rsync_name}", self._RSYNC_IMAGE_NAME, self._RSYNC_IMAGE_TAG,
                platform=self._RSYNC_PLATFORM, volumes=volumes_rsync, entrypoint="")

            self._rsync_in()

            volumes = {
                rsync_volume.name: {
                    "bind": self._mount_dir,
                    "mode": "rw"
                }
            }
        else:
            volumes = {
                self._base_dir: {
                    "bind": self._mount_dir,
                    "mode": "rw"
                }
            }

        self._start_container(
            self._name, self._image_name, self._image_tag,
            platform=self._platform, isolation=self._isolation, volumes=volumes)

    def stop(self):
        self._stop_container(self._name)

        if self._volume_sync == "rsync":
            self._stop_container(f"{self._rsync_name}")

    def exec(self, command):
        if not self.is_running():
            self._log.info('Toolchain not running -> starting')
            self.start()

        if self._volume_sync == "rsync":
            self._rsync_in()

        exit_code = self._exec_command(self._name, command, self._work_dir)

        if self._volume_sync == "rsync":
            self._rsync_out()

        return exit_code

    def _pull_image(self, image_name, image_tag, platform):
        self._log.extra_info(f"Pulling image {image_name}:{image_tag}")
        try:
            res = self._docker.images.pull(image_name, image_tag, platform=platform)
            self._log.debug(res)
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to pull image: {ex}")

    def _is_container_running(self, name):
        try:
            self._docker.containers.get(name)
            return True
        except docker.errors.NotFound as ex:
            return False
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to get container info: {ex}")

    def _start_container(self, name, image_name, image_tag, **kwargs):
        self._log.extra_info(f"Starting container {name}")

        if self._is_container_running(name):
            self._log.warning("Container is already running")
            return

        try:
            res = self._docker.containers.run(
                image=f"{image_name}:{image_tag}", name=name, auto_remove=True, detach=True,
                stdin_open=True, **kwargs)
            self._log.debug(res)
        except docker.errors.ImageNotFound as ex:
            raise ToolchainError(
                f"Image {image} not found."
                f"Try running brock init first")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to start container: {ex}")

    def _stop_container(self, name):
        self._log.extra_info(f"Stopping container {name}")

        try:
            container = self._docker.containers.get(name)
            container.stop()
        except docker.errors.NotFound as ex:
            self._log.warning("Container not running")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to stop container: {ex}")

    def _exec_command(self, container, command, work_dir):
        self._log.extra_info(f"Executing command in container {container}")
        self._log.debug(f"Command: {command}")
        self._log.debug(f"Work dir: {work_dir}")

        try:
            container = self._docker.containers.get(container)
        except docker.errors.NotFound as ex:
            raise ToolchainError("Container not running")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to get container info: {ex}")

        try:
            exec_id = container.client.api.exec_create(
                container.id, command, workdir=work_dir)['Id']
            output = container.client.api.exec_start(
                exec_id, stream=True, demux=True)

            try:
                for chunk in output:
                    if chunk[0]:
                        for line in chunk[0].split(b"\n"):
                            self._log.stdout(line.decode())
                    if chunk[1]:
                        for line in chunk[1].split(b"\n"):
                            self._log.stderr(line.decode())
            except KeyboardInterrupt:
                self._log.warning("Execution interrupted")

            res = container.client.api.exec_inspect(exec_id)
            exit_code = res['ExitCode']

            self._log.debug(f"Exit code: {exit_code}")

            return exit_code
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to execute command: {ex}")

    def _create_volume(self, name):
        try:
            volumes = self._docker.volumes.list()
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to list volumes: {ex}")

        volume = next((v for v in volumes if v.name == name), None)

        if volume is None:
            self._log.extra_info(f"Creating volume {name}")
            try:
                volume = self._docker.volumes.create(name)
            except docker.errors.APIError as ex:
                raise ToolchainError(f"Failed to create volume: {ex}")

        return volume

    def _rsync_in(self):
        self._log.extra_info(f"Rsyncing data into toolchain")
        self._rsync(self._HOST_PATH, self._RSYNC_PATH)

    def _rsync_out(self):
        self._log.extra_info(f"Rsyncing data out of toolchain")
        self._rsync(
            f"{self._RSYNC_PATH}/{self._work_dir_rel}",
            f"{self._HOST_PATH}/{self._work_dir_rel}")

    def _rsync(self, src, dest, options=['-a', '--delete']):
        exit_code = self._exec_command(
            f"{self._rsync_name}",
            f"rsync {' '.join(options)} {src}/ {dest}", "/")
        if exit_code != 0:
            raise ToolchainError(f"Failed to rsync data")
