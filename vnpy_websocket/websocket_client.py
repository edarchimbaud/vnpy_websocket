import json
import sys
import traceback
from datetime import datetime
from types import coroutine
from threading import Thread
from asyncio import (
    get_running_loop,
    new_event_loop,
    set_event_loop,
    set_event_loop,
    run_coroutine_threadsafe,
    AbstractEventLoop,
)

from aiohttp import ClientSession, ClientWebSocketResponse


class WebsocketClient:
    """
    Asynchronous clients for various Websocket APIs

    * Overload the unpack_data method to implement the data unpacking logic.
    * Overload the on_connected method to realize the connection success callback processing.
    * Overload the on_disconnected method to implement the connection disconnected callback.
    * Overload the on_packet method to realize the data push callback processing.
    * Overload the on_error method to implement the exception catching callback handling.
    """

    def __init__(self):
        """Constructor"""
        self._active: bool = False
        self._host: str = ""

        self._session: ClientSession = None
        self._ws: ClientWebSocketResponse = None
        self._loop: AbstractEventLoop = None

        self._proxy: str = None
        self._ping_interval: int = 60  # 秒
        self._header: dict = {}

        self._last_sent_text: str = ""
        self._last_received_text: str = ""

    def init(
        self,
        host: str,
        proxy_host: str = "",
        proxy_port: int = 0,
        ping_interval: int = 60,
        header: dict = None,
    ):
        """
        Initializing the client
        """
        self._host = host
        self._ping_interval = ping_interval

        if header:
            self._header = header

        if proxy_host and proxy_port:
            self._proxy = f"http://{proxy_host}:{proxy_port}"

    def start(self):
        """
        Starting the client

        The on_connected callback function will be called automatically after a successful connection.

        Please wait until on_connected is called before sending packets.
        """
        self._active = True

        try:
            self._loop = get_running_loop()
        except RuntimeError:
            self._loop = new_event_loop()

        start_event_loop(self._loop)

        run_coroutine_threadsafe(self._run(), self._loop)

    def stop(self):
        """
        Stop the client
        """
        self._active = False

        if self._ws:
            coro = self._ws.close()
            run_coroutine_threadsafe(coro, self._loop)

        if self._loop and self._loop.is_running():
            self._loop.stop()

    def join(self):
        """
        Wait for the background thread to exit.
        """
        pass

    def send_packet(self, packet: dict):
        """
        Sends a packet dictionary to the server.

        If you need to send non-json data, please overload to implement this function.
        """
        if self._ws:
            text: str = json.dumps(packet)
            self._record_last_sent_text(text)

            coro: coroutine = self._ws.send_str(text)
            run_coroutine_threadsafe(coro, self._loop)

    def unpack_data(self, data: str):
        """
        Unpack string data in json format.

        If you need to use a format other than json, please overload this function.
        """
        return json.loads(data)

    def on_connected(self):
        """Callback for successful connection"""
        pass

    def on_disconnected(self):
        """Connection disconnected callback"""
        pass

    def on_packet(self, packet: dict):
        """Received data callback"""
        pass

    def on_error(self, exception_type: type, exception_value: Exception, tb) -> None:
        """Triggered exception callback"""
        try:
            print("WebsocketClient on error" + "-" * 10)
            print(self.exception_detail(exception_type, exception_value, tb))
        except Exception:
            traceback.print_exc()

    def exception_detail(
        self, exception_type: type, exception_value: Exception, tb
    ) -> str:
        """Formatting of exception messages"""
        text = "[{}]: Unhandled WebSocket Error:{}\n".format(
            datetime.now().isoformat(), exception_type
        )
        text += "LastSentText:\n{}\n".format(self._last_sent_text)
        text += "LastReceivedText:\n{}\n".format(self._last_received_text)
        text += "Exception trace: \n"
        text += "".join(traceback.format_exception(exception_type, exception_value, tb))
        return text

    async def _run(self):
        """
        The main thread running in the event loop
        """
        self._session = ClientSession()

        while self._active:
            # Catching runtime exceptions
            try:
                # Initiating a Websocket Connection
                self._ws = await self._session.ws_connect(
                    self._host, proxy=self._proxy, verify_ssl=False
                )

                # Calling the connection success callback
                self.on_connected()

                # Ongoing processing of incoming data
                async for msg in self._ws:
                    text: str = msg.data
                    self._record_last_received_text(text)

                    data: dict = self.unpack_data(text)
                    self.on_packet(data)

                # Removing the Websocket Connection Object
                self._ws = None

                # Calling the disconnect callback
                self.on_disconnected()
            # Handling of caught exceptions
            except Exception:
                et, ev, tb = sys.exc_info()
                self.on_error(et, ev, tb)

    def _record_last_sent_text(self, text: str):
        """Record the most recently sent data string"""
        self._last_sent_text = text[:1000]

    def _record_last_received_text(self, text: str):
        """Record the most recently received data string"""
        self._last_received_text = text[:1000]


def start_event_loop(loop: AbstractEventLoop) -> AbstractEventLoop:
    """Start the event loop"""
    # If the event loop is not running, create a background thread to run it
    if not loop.is_running():
        thread = Thread(target=run_event_loop, args=(loop,))
        thread.daemon = True
        thread.start()


def run_event_loop(loop: AbstractEventLoop) -> None:
    """Running the event loop"""
    set_event_loop(loop)
    loop.run_forever()
