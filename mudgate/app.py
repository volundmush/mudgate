import ssl
import uuid
import asyncio
import random
import string

from typing import List, Optional, Dict
from .telnet import TelnetManager
from .link import LinkManager


class MudGate:
    """
    The core of MudGate.
    """

    def __init__(self, config: Dict):
        self.name = config.get("name", "mudgate")
        self.config = config
        self.configured = False
        self.tls_context: Optional[ssl.SSLContext] = None
        self.game_clients: Dict[str] = dict()
        self.link = None
        self.telnet: Optional[TelnetManager] = None
        self.ws = None
        self.ssh = None
        self.web = None
        self.running_services = list()

    async def configure(self):

        interfaces = self.config.get("interfaces", {"internal": "127.0.0.1", "external": "0.0.0.0"})

        if (tls := self.config.get("tls", dict())):
            if not (pem := tls.get("pem", None)) and (key := tls.get("key", None)):
                raise ValueError("TLS config is missing pem or key fields.")
            # TODO: actually use the pem and key files
            self.tls_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

        if (tel := self.config.get("telnet", dict())):
            tel_plain = tel.get("plain", None)
            tel_tls = tel.get("tls", None)
            if tel_plain or tel_tls:
                self.telnet = TelnetManager(self, interfaces["external"], tel_plain, tel_tls)
                await self.telnet.setup()
                self.running_services.append(self.telnet.run())

        self.link = LinkManager(self, interfaces["internal"], self.config.get("link", 7000))
        self.running_services.append(self.link.run())


        self.running_services.append(self.please_wait_warmly())

        self.configured = True

    def generate_id(self, prefix: str):

        def gen():
            return f"{prefix}_{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"

        while (u := gen()) not in self.game_clients:
            return u

    async def run(self):
        await self.configure()

        await asyncio.gather(*self.running_services)

    async def please_wait_warmly(self):
        msg = f"No connection to {self.name}. Please standby..."
        while True:
            if not self.link.link:
                for k, v in self.game_clients.items():
                    await v.send_text_data(mode="line", data=msg)
            await asyncio.sleep(3)