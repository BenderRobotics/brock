import os
import docker
from getpass import getpass

from brock.exception import ToolchainError
from brock.log import getLogger


class Toolchain:
    def __init__(self, config):
        self._name = f"brock-{config.project.name}"
        self._base_dir = config.base_dir

        if config.toolchain.platform == "windows":
            self._mount_dir = "C:/host"
        else:
            self._mount_dir = "/host"
        self._work_dir = os.path.join(self._mount_dir, config.work_dir_rel).replace("\\", "/")

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

        try:
            self._docker.containers.get(self._name)
            self._log.info(f"Container {self._name} is running")
        except docker.errors.NotFound as ex:
            self._log.warning(f"Container {self._name} is not running")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to get container info: {ex}")

    def pull(self):
        self._log.extra_info(f"Pulling image {self._image_name}:{self._image_tag}")
        try:
            res = self._docker.images.pull(
                self._image_name, self._image_tag, platform=self._platform)
            self._log.debug(res)
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to pull image: {ex}")

    def start(self):
        self._log.extra_info(f"Starting container {self._name}")

        volumes = {
            self._base_dir: {
                "bind": self._mount_dir,
                "mode": "rw"
            }
        }

        try:
            self._docker.containers.get(self._name)
            self._log.warning("Container is already running")
            return
        except docker.errors.NotFound as ex:
            pass
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to get container info: {ex}")

        try:
            res = self._docker.containers.run(
                f"{self._image_name}:{self._image_tag}", name=self._name, platform=self._platform,
                isolation=self._isolation, volumes=volumes, auto_remove=True, detach=True,
                stdin_open=True)
            self._log.debug(res)
        except docker.errors.ImageNotFound as ex:
            raise ToolchainError(
                f"Image {self._image_name}:{self._image_tag} not found."
                f"Try running brock init first")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to start container: {ex}")

    def stop(self):
        self._log.extra_info(f"Stopping container {self._name}")

        try:
            container = self._docker.containers.get(self._name)
            container.stop()
        except docker.errors.NotFound as ex:
            self._log.warning("Container not running")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to stop container: {ex}")

    def exec(self, command):
        self._log.extra_info(f"Executing command in container {self._name}")
        self._log.debug(f"Command: {command}")
        self._log.debug(f"Work dir: {self._work_dir}")

        try:
            container = self._docker.containers.get(self._name)
        except docker.errors.NotFound as ex:
            raise ToolchainError("Container not running")
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to get container info: {ex}")

        try:
            res = container.exec_run(command, stream=True, demux=True, workdir=self._work_dir)
        except docker.errors.APIError as ex:
            raise ToolchainError(f"Failed to execute command: {ex}")

        try:
            for chunk in res.output:
                if chunk[0]:
                    for line in chunk[0].split(b"\n"):
                        self._log.info(line.decode())
                if chunk[1]:
                    for line in chunk[1].split(b"\n"):
                        self._log.warning(line.decode())
        except KeyboardInterrupt:
            self._log.warning("Execution interrupted")
