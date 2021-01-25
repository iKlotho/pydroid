import trio
import re
import attr
import os
from pathlib import Path
import shlex
import subprocess
from loguru import logger

ERROR_STRINGS = [
    "exception",
]

SOURCE_FOLDER = Path("source/wssc")
CURRENT_PATH = Path.cwd()
SOURCE_DIR = CURRENT_PATH.parent /  SOURCE_FOLDER

@attr.s
class Scrcpy:
    """
        Extra params  user repr false if not CMD command
        https://github.com/Genymobile/scrcpy/blob/v1.15/server/src/main/java/com/genymobile/scrcpy/Options.java
        
        private Ln.Level logLevel;
        private int maxSize;
        private int bitRate;
        private int maxFps;
        private int lockedVideoOrientation;
        private boolean tunnelForward;
        private Rect crop;
        private boolean sendFrameMeta; // send PTS so that the client may record properly
        private boolean control;
        private int displayId;
        private boolean showTouches;
        private boolean stayAwake;
        private String codecOptions;
    """
    SCRCPY_VERSION: str = attr.ib(default="1.16-ws1")
    log_level: str = attr.ib(default="ERROR")
    max_size_string: str = attr.ib(default=0)
    bit_rate_string: str = attr.ib(default=8000000)
    max_fps_string: str = attr.ib(default=60)
    lock_video_orientation_string: str = attr.ib(default="-1")
    tunnel_forward: str = attr.ib(default="false")
    crop: str = attr.ib(default="-")
    frame_meta: str = attr.ib(default="false")
    control: str = attr.ib(default="true")
    display_id_string: str = attr.ib(default="0")
    show_touches: str = attr.ib(default="false")
    stay_awake: str = attr.ib(default="false")
    codec_options: str = attr.ib(default="-")
    server_type: str = attr.ib(default="web")
    port: int = attr.ib(default=8886)

    fullpath: str = attr.ib(
        default=SOURCE_DIR, repr=False
    )

    async def start(self, *, task_status=trio.TASK_STATUS_IGNORED):
        logger.info("Installing scrcpy")
        await self.install()
        await self.forward_port()
        task_status.started()

    async def install(self):
        # TODO use pathlib
        file = os.path.join(self.fullpath, "scrcpy-server.jar")
        cmd = ["adb", "push", file, "/data/local/tmp/"]
        logger.debug("Installed the scrcpy-server")
        process = await trio.run_process(cmd, capture_stdout=True)

    async def run(self, device_id: str, task_status=trio.TASK_STATUS_IGNORED):
        """
            Run by device
        """
        # TODO: passing static params, use device id ?
        params = attr.asdict(self, filter=lambda attr, value: attr.repr == True)
        run_cmd = (
            f"adb -s {device_id} shell CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / com.genymobile.scrcpy.Server "
            + " ".join(map(lambda x: str(x), list(params.values())))
        )
        logger.debug(f"run_cmd {run_cmd}")
        async with await trio.open_process(
            shlex.split(run_cmd), stdout=subprocess.PIPE, stdin=subprocess.PIPE
        ) as process:
            # TODO: check output and pid?
            task_status.started()
            async for out in process.stdout:
                # im.draw_custom(self.live_feed)
                log = out.decode("utf-8")
                """
                if any([keyword in log.strip().lower() for keyword in ERROR_STRINGS]):
                    # TODO: get why its failed and raise with that
                    logger.error(log)
                    raise Exception("Can't start scrcpy!")
                """

                logger.debug(log)

    async def forward_port(self):
        logger.debug(f"Forwarding scrcpy-server to port:{self.port}")
        cmd = f"adb forward tcp:{self.port} tcp:{self.port}"
        process = await trio.run_process(shlex.split(cmd), capture_stdout=True)