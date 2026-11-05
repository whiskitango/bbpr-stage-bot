"""A small web address that tells radio-metrics how many people are listening
on Discord: GET /status with "Authorization: Bearer <STATUS_TOKEN>" answers
the StatusReport as JSON. Nothing else is served, and nothing can be changed
through it.

The token is checked in constant time. The page is off unless STATUS_PORT is
set. By default it listens on this machine only (STATUS_HOST=127.0.0.1). To
reach it from another computer, give it a certificate (STATUS_TLS_CERT and
STATUS_TLS_KEY), because radio-metrics sends the token over plain http only
to this machine or the local network. The certificate is reloaded when its
file changes, so a renewal doesn't need a restart."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import ssl
from typing import Callable, Optional

from aiohttp import web

log = logging.getLogger('stagebot')

RELOAD_S = 6 * 3600
LOOPBACK = ('127.0.0.1', '::1', 'localhost')


class StatusServer:
    def __init__(self, host: str, port: int, token: str, report: Callable[[], dict],
                 tls_cert: str = '', tls_key: str = ''):
        self.host = host
        self.port = port
        self.token = token
        self.report = report
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self.tls: Optional[ssl.SSLContext] = None
        self.tls_stamp = None
        self.runner: Optional[web.AppRunner] = None
        self.reloader: Optional[asyncio.Task] = None

    @staticmethod
    def same_secret(a: str, b: str) -> bool:
        # Hashed first, so tokens of different lengths take the same time.
        left = hashlib.sha256(a.encode()).digest()
        right = hashlib.sha256(b.encode()).digest()
        return hmac.compare_digest(left, right)

    def authorized(self, header: str) -> bool:
        scheme, _, given = (header or '').partition(' ')
        return bool(self.token) and scheme.lower() == 'bearer' and self.same_secret(given.strip(), self.token)

    async def status(self, request: web.Request) -> web.Response:
        if not self.authorized(request.headers.get('Authorization', '')):
            return web.json_response({'error': 'unauthorized'}, status=401,
                                     headers={'WWW-Authenticate': 'Bearer'})
        return web.json_response(self.report(), headers={'Cache-Control': 'no-store'})

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get('/status', self.status)
        return app

    def cert_stamp(self):
        return tuple(os.stat(path).st_mtime_ns for path in (self.tls_cert, self.tls_key))

    def load_tls(self) -> Optional[ssl.SSLContext]:
        if not (self.tls_cert and self.tls_key):
            return None
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(self.tls_cert, self.tls_key)
        self.tls_stamp = self.cert_stamp()
        return context

    async def reload_tls(self) -> None:
        """Pick up a renewed certificate. Connections already open keep the
        old one; new ones get the new one."""
        while True:
            await asyncio.sleep(RELOAD_S)
            try:
                if self.cert_stamp() != self.tls_stamp:
                    self.tls.load_cert_chain(self.tls_cert, self.tls_key)
                    self.tls_stamp = self.cert_stamp()
                    log.info('[status] reloaded the certificate')
            except (OSError, ssl.SSLError) as err:
                log.warning(f'[status] could not reload the certificate: {err}')

    async def start(self) -> bool:
        """Starts serving. False (and logged) if it can't, so the bot plays on
        without it."""
        try:
            self.tls = self.load_tls()
            self.runner = web.AppRunner(self.app(), access_log=None)
            await self.runner.setup()
            await web.TCPSite(self.runner, self.host, self.port, ssl_context=self.tls).start()
        except (OSError, ssl.SSLError) as err:
            log.error(f'[status] could not serve the status page on {self.host}:{self.port}: {err}')
            await self.stop()
            return False
        scheme = 'https' if self.tls else 'http'
        log.info(f'[status] listener counts at {scheme}://{self.host}:{self.port}/status')
        if not self.tls and self.host not in LOOPBACK:
            log.warning('[status] the status page is open to other computers without https; '
                        'radio-metrics will only use it from the local network')
        if self.tls:
            self.reloader = asyncio.create_task(self.reload_tls())
        return True

    async def stop(self) -> None:
        task, self.reloader = self.reloader, None
        if task:
            task.cancel()
        runner, self.runner = self.runner, None
        if runner:
            await runner.cleanup()
