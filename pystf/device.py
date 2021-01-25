"""
    Device related fields
"""
import struct
import re
import attr
import shlex
import time

import re
import trio
import subprocess
from trio_util import periodic
from .attr_fields import android_field, ANDROID_METADATA
from typing import List
from loguru import logger
from trio_websocket import open_websocket_url


@attr.s
class Power:
    nursery: trio.Nursery = attr.ib(repr=False)
    fetched: bool = attr.ib(default=False, repr=False)
    mWakefulness: str = android_field(default="")
    mWakefulnessChanging: bool = android_field(default=False)
    mSystemReady: str = android_field(default=False)

    def __attrs_post_init__(self):
        self.nursery.start_soon(self.worker)

    async def worker(self):
        async for _ in periodic(1):
            states = await dumpsys(
                "power",
                attr.asdict(
                    self,
                    filter=lambda attr, value: ANDROID_METADATA in attr.metadata.keys(),
                ),
            )
            for key, value in states.items():
                setattr(self, key, value)
            self.fetched = True


@attr.s
class Device:
    id: str = attr.ib()
    attach_type: str = attr.ib()
    nursery: trio.Nursery = attr.ib(repr=False)
    power: Power = attr.ib(default=None)
    width: int = android_field(default=0)
    height: int = android_field(default=0)
    img: bytes = attr.ib(default=b"", repr=False)
    live_feed = attr.ib(default=None, repr=False)
    decoded_feed = attr.ib(default=b"", repr=False)
    receive_input_channel = attr.ib(default=None, repr=False)
    WIDTH = attr.ib(default=0)
    HEIGHT = attr.ib(default=0)

    def __attrs_post_init__(self):
        self.get_screen_size()
        self.power = Power(nursery=self.nursery)

    def get_screen_size(self):
        cmd = "adb shell wm size"
        process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
        out, err = process.communicate()
        # TODO handle err
        m = re.search(r"(\d+)x(\d+)", out.decode("utf-8"))
        if m:
            self.width = int(m.group(1))
            self.height = int(m.group(2))

    async def start_streaming(self, scrcpy):
        async with trio.open_nursery() as nursery:
            await nursery.start(scrcpy.run, self.id)
            await trio.sleep(0.3)
            await nursery.start(self.run_client, scrcpy)

    async def read_from_ffplay(self, process):
        async for out in process.stdout:
            self.decoded_feed = out
            print("d", self.decoded_feed)

    async def video_stream(self, client_stream):
        send_channel, receive_channel = trio.open_memory_channel(0)
        self.live_feed = receive_channel
        logger.info("video_stream: started!")
        dummy_byte = await client_stream.receive_some(1)
        while not dummy_byte:
            logger.info("no dummy byte waiting")
            await trio.sleep(0.2)
            dummy_byte = await client_stream.receive_some(1)
        # TODO: check dummy
        device_name = await client_stream.receive_some(64)
        logger.debug(f"Device Name: {device_name.decode('utf-8')}")
        res = await client_stream.receive_some(4)
        self.WIDTH, self.HEIGHT = struct.unpack(">HH", res)
        logger.debug(f"W{self.WIDTH}xH{self.HEIGHT}")
        async for received in client_stream:
            await send_channel.send(received)

    async def control_stream(self, client_stream):
        logger.info("control_stream receiver: started!")
        async for data in client_stream:
            logger.debug(f"control_stream receiver: got data {data!r}")
        logger.debug("control_stream receiver: connection closed")

    async def websocket_client(self):
        try:
            # TODO: dynamic port
            async with open_websocket_url(f"ws://127.0.0.1:8886") as ws:
                async for data in ws._recv_channel:
                    print("Received message: %s" % data)
        except OSError as ose:
            print("Connection attempt failed: %s" % ose)

    async def run_client(self, scrcpy, task_status=trio.TASK_STATUS_IGNORED):
        logger.info(f"Running client at port:{scrcpy.port}")
        async with trio.open_nursery() as stream_nursery:
            stream_nursery.start_soon(self.websocket_client)
            task_status.started()

    async def start_recording(self):
        # @deprecated
        cmd = "adb exec-out screenrecord --output-format=h264 -"
        print(f"echo_server: started")
        async with await trio.open_process(
            shlex.split(cmd), stdout=subprocess.PIPE, stdin=subprocess.PIPE
        ) as process:
            async for out in process.stdout.replace(b"\r\n", b"\n"):
                self.live_feed = out
                print("feed", self.live_feed)

    async def wake_up(self):
        while not self.power.fetched:
            await trio.sleep(0.2)
        if self.power.mWakefulness == "Asleep":
            for cmd in get_wake_commands():
                await trio.run_process(shlex.split(cmd), capture_stdout=True)
        else:
            print(f"Device {self.id} is already awake!")

    async def tap(self, X, Y):
        cmd = f"adb shell input tap {X} {Y}"
        print("tap", cmd)
        await trio.run_process(shlex.split(cmd))

    async def swipe(self, X_start, Y_start, X_end, Y_end, dur):
        cmd = f"adb shell input swipe {X_start} {Y_start} {X_end} {Y_end} {dur}"
        print("swipe", cmd)
        await trio.run_process(shlex.split(cmd))


# HELPERS


async def dumpsys(which="power", states={}):
    # TODO: move to another file?
    cmd = ["adb", "shell", "dumpsys", which]
    proc = await trio.run_process(cmd, capture_stdout=True)

    changes = 0
    for line2 in proc.stdout.decode("utf-8").split("\n"):
        line = line2.strip()
        for state, value in states.items():
            m = re.search(r"{}=(.*)".format(state), line)
            if m:
                if value != m.group(1):
                    changes += 1
                    states[state] = m.group(1)
    return states


def list_devices(out: str, nursery: trio.Nursery) -> List[Device]:
    """
        TODO: move to another file?
        Parse list of devices
        with open("one_device", "w") as f:
            f.write(out)
    """
    # remove the header
    out = out.replace("List of devices attached", "").strip()

    device_data = []
    for data in out.split("\n"):
        # if there is data
        if data != "":
            device_id, attach_type = data.strip().split("\t")
            device_data.append(
                Device(id=device_id, attach_type=attach_type, nursery=nursery)
            )

    return device_data


def get_wake_commands():
    for cmd in (
        "adb shell input keyevent 26",
        "adb shell input keyevent 66",
    ):
        yield cmd
