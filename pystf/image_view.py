from pura import WebViewServer, WebView
import trio
from .events import MouseEvent
from trio_util import periodic

FRAME_RATE = 20

class Images(WebView):
    def __init__(self, device):
        super().__init__(frame_rate=FRAME_RATE, input_consumer=1)
        send_channel, receive_channel = trio.open_memory_channel(0)
        self.send_channel = send_channel
        self.width = 352
        self.height = 730
        self.device = device
        self.device.receive_input_channel = receive_channel
        self.device.start_input_queue()
        self.device.nursery.start_soon(self.device.handle_input_queue)
        self.device.nursery.start_soon(self.start_input_queue)
        self.external = b""

    def convert_browser_to_device(self, X, Y):
        scale_width = self.device.width / self.width
        scale_height = self.device.height / self.height
        return X * scale_width, Y * scale_height

    def draw(self):
        self.image(self.device.decoded_fe, 0, 0)

    async def start_input_queue(self):
        async for _ in periodic(0.1):
            while self.inputEvents:
                event_name, coords = self.inputEvents.pop()
                # for event_name, coords in self.inputEvents:
                # print("sending through", event_name)
                if len(coords) == 2:
                    X, Y = coords
                    X, Y = self.convert_browser_to_device(X, Y)
                    await self.send_channel.send(MouseEvent(event_name, X, Y))