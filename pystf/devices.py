import attr
import trio
from .scrcpy import Scrcpy
from typing import List
from .device import Device, list_devices
from loguru import logger
import sys



@attr.s
class Devices:
    scrcpy: Scrcpy = attr.ib(repr=False)
    nursery: trio.Nursery = attr.ib(repr=False)
    _devices: Device = attr.ib(default=[])

    async def start(self, *, task_status=trio.TASK_STATUS_IGNORED):
        await self.get_devices()
        task_status.started()

    async def get_devices(self):
        process = await trio.run_process(["adb", "devices"], capture_stdout=True)
        out = process.stdout.decode("utf-8")
        self._devices = list_devices(out, self.nursery)

    async def woke_the_devices(self):
        async def main(device):
            await trio.serve_tcp(device.start_recording, 12345)

        async with trio.open_nursery() as woke_nursery:
            woke_nursery.start_soon(self.scrcpy.setup)
            woke_nursery.start_soon(self.run_client)
            for device in self.devices:
                images = Images(device)
                woke_nursery.start_soon(device.wake_up)
                woke_nursery.start_soon(device.start_screenshot, images)
                woke_nursery.start_soon(images._serve_webview, server, 352, 730)
                print("Waking up the device", device)
