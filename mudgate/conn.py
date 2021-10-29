import random
import string
import time
from typing import List
from .shared import (
    ConnectionDetails,
    ConnectionInMessageType,
    ConnectionOutMessage,
    ConnectionInMessage,
    ConnectionOutMessageType,
    MudProtocol,
)
from enum import IntEnum

from rich.console import Console
from rich.color import ColorSystem
from rich.console import _null_highlighter
from rich.traceback import Traceback
from rich import box

from xml.etree import ElementTree

from rich.text import Text, Segment
from rich.color import Color
from rich.style import Style


COLOR_MAP = {
    ColorSystem.STANDARD: "standard",
    ColorSystem.EIGHT_BIT: "256",
    ColorSystem.TRUECOLOR: "truecolor",
    ColorSystem.WINDOWS: "windows",
}


class PrintMode(IntEnum):
    LINE = 0
    TEXT = 1
    PROMPT = 2


class StyleOptions(IntEnum):
    BOLD = 1
    DIM = 2
    ITALIC = 4
    UNDERLINE = 8
    BLINK = 16
    BLINK2 = 32
    REVERSE = 64
    CONCEAL = 128
    STRIKE = 256
    UNDERLINE2 = 512
    FRAME = 1024
    ENCIRCLE = 2048
    OVERLINE = 4096


class MudConnection:
    listener = None

    def __init__(self, details: ConnectionDetails):
        details.connected = time.time()
        self.running: bool = False
        self.started: bool = False
        self.ended: bool = False
        self.details = details
        self.in_events = list()
        self.console = Console(color_system=None, file=self, record=True)
        self.server_data = None

    @property
    def conn_id(self):
        return self.details.client_id

    def write(self, b: str):
        pass

    def flush(self):
        """
        Do not remove this method. It's needed to trick Console into treating this object
        as a file.
        """

    def print(self, *args, **kwargs):
        self.console.print(*args, highlight=False, **kwargs)
        return self.do_print()

    def do_print(self):
        return self.console.export_text(clear=True, styles=True)

    def generate_name(self) -> str:
        prefix = f"{self.listener.name}_"

        attempt = f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        while attempt in self.listener.service.mudconnections:
            attempt = f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        return attempt

    async def process_out_event(self, ev: ConnectionOutMessage):
        if ev.msg_type == ConnectionOutMessageType.GAMEDATA:
            await self.process_out_gamedata(ev)
        elif ev.msg_type == ConnectionOutMessageType.MSSP:
            await self.process_out_mssp(ev)
        elif ev.msg_type == ConnectionOutMessageType.DISCONNECT:
            await self.process_out_disconnect(ev)

    async def process_out_gamedata(self, ev: ConnectionOutMessage):
        if ev.data["processor"].lower() == "xml":
            await self.process_xml(ev.data["body"])

    async def process_out_mssp(self, ev: ConnectionOutMessage):
        pass

    async def process_out_disconnect(self, ev: ConnectionOutMessage):
        pass

    def on_start(self):
        self.started = True
        self.in_events.append(
            ConnectionInMessage(
                ConnectionInMessageType.READY, self.conn_id, self.details
            )
        )

    def check_ready(self):
        pass

    async def process_xml(self, body):
        for entry in body:
            mode = entry.get("mode", "line")
            rendered = self.print_xml(entry["data"])
            await self.send_text_data(mode.lower(), self.print(rendered))

    async def send_text_data(self, mode: str, data: str):
        pass

    async def send_oob_data(self, cmd: str, *args, **kwargs):
        pass

    async def send_mssp_data(self, **kwargs):
        pass

    def extract_style(self, element):
        if not element.attrib:
            return None
        kwargs = dict()
        attribs = element.attrib.copy()
        options = int(attribs.pop("options")) if "options" in attribs else 0
        no_options = int(attribs.pop("no_options"))  if "no_options" in attribs else 0
        s = StyleOptions

        for c in ("color", "bgcolor", "link", "tag"):
            if c in attribs:
                if attribs[c].lower() in ("none", "null"):
                    kwargs[c] = None
                else:
                    kwargs[c] = attribs[c]

        if options or no_options:
            for code, kw in ((s.BOLD, "bold"), (s.DIM, "dim"), (s.ITALIC, "italic"), (s.UNDERLINE, "underline"),
                             (s.BLINK, "dim"), (s.BLINK2, "dim"), (s.REVERSE, "dim"), (s.CONCEAL, "dim"),
                             (s.STRIKE, "dim"), (s.UNDERLINE2, "dim"), (s.FRAME, "dim"), (s.ENCIRCLE, "dim"),
                             (s.OVERLINE, "dim")):
                if code & options:
                    kwargs[kw] = True
                if code & no_options:
                    kwargs[kw] = False

        kwargs["xml_attr"] = attribs
        return Style(**kwargs)

    def print_xml(self, entry):
        tree = ElementTree.fromstring(entry)
        if tree.tag.lower() == "text":
            return self.render_xml_text(tree)

    def render_xml_text(self, element):
        """
        Renders a <text> element and its <span> contents into a single Text object.
        """
        style = self.extract_style(element)
        t = Text(element.text, style=style)
        for i in range(len(element)):
            e = element[i]
            t.append(Text(e.text, style=self.extract_style(e)))
            if e.tail:
                t.append(e.tail)
        if element.tail:
            t.append(element.tail)
        return t
