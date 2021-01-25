import trio
import time
import traceback
import attr
from pystf.scrcpy import Scrcpy
from pystf.devices import Devices
from loguru import logger


@attr.s
class Tridroid:
    scrcpy = attr.ib()
    devices = attr.ib()
    launcher_nursery = attr.ib()


    async def test(self):
        # run for 1 device
        device = self.devices._devices[0]

        async with trio.open_nursery() as stream_nursery:
            stream_nursery.start_soon(device.start_streaming, self.scrcpy)


async def Launcher():
    """
        Start the app

        - Listen video feed from scrpy
    """

    async with trio.open_nursery() as launcher_nursery:
        scrcpy = Scrcpy()
        devices = Devices(scrcpy, launcher_nursery)
        await launcher_nursery.start(devices.start)
        logger.info(f"Fetched the devices len-{len(devices._devices)}")
        if len(devices._devices) == 0:
            # TODO don't raise issue
            raise Exception("No device available")
        await launcher_nursery.start(scrcpy.start)
        logger.info("Scrcpy installed!")
        trd = Tridroid(scrcpy, devices, launcher_nursery)
        await trd.test()
        


    


if __name__ == "__main__":
    trio.run(Launcher)