"""Python WebSocket server that bridges IRIS core to the Tauri UI overlay."""

import asyncio
import inspect
import json

from aiohttp import web
import websockets
from loguru import logger


class IPCBridge:
    """
    WebSocket server on localhost:7788.
    Tauri overlay connects as a client and receives state_change events.
    Also handles approval_request/approval_response for DANGEROUS actions.
    """

    def __init__(self, port: int = 7788, http_port: int = 7790, snapshot_provider=None) -> None:
        self.port = port
        self.http_port = http_port
        self.clients: set = set()
        self._pending_approvals: dict[str, asyncio.Future] = {}
        self.snapshot_provider = snapshot_provider

    async def handler(self, ws) -> None:
        """Handle a single WebSocket client connection."""
        self.clients.add(ws)
        logger.info(f"IPC client connected ({len(self.clients)} total)")
        try:
            async for message in ws:
                data = json.loads(message)
                if data.get("event") == "approval_response":
                    req_id = data["id"]
                    if req_id in self._pending_approvals:
                        self._pending_approvals[req_id].set_result(data["approved"])
                        logger.info(f"Approval response for {req_id}: {data['approved']}")
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)
            logger.info(f"IPC client disconnected ({len(self.clients)} remaining)")

    async def broadcast(self, state: str) -> None:
        """Send a state_change event to all connected UI clients."""
        msg = json.dumps({"event": "state_change", "state": state})
        for client in list(self.clients):
            try:
                await client.send(msg)
            except Exception:
                self.clients.discard(client)

    async def request_approval(self, action: str, params: dict, req_id: str) -> bool:
        """
        Send approval popup to UI, wait for user response.
        Returns True if approved, False on denial or 30s timeout.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_approvals[req_id] = future

        msg = json.dumps({
            "event": "approval_request",
            "action": action,
            "params": params,
            "id": req_id,
        })

        for client in list(self.clients):
            try:
                await client.send(msg)
            except Exception:
                self.clients.discard(client)

        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            logger.warning(f"Approval timeout for {req_id} — defaulting to denied")
            return False
        finally:
            self._pending_approvals.pop(req_id, None)

    def set_snapshot_provider(self, snapshot_provider) -> None:
        """Register a callable that returns the current desktop shell snapshot."""
        self.snapshot_provider = snapshot_provider

    @staticmethod
    def _cors_headers() -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

    async def _resolve_snapshot(self) -> dict:
        if self.snapshot_provider is None:
            return {
                "bootstrap": {
                    "appName": "IRIS Desktop",
                    "platform": "python-runtime",
                    "stage": "bridge unavailable",
                    "backendBridge": "snapshot provider not attached",
                },
                "state": "idle",
                "conversation": [],
                "actions": [],
                "providers": [],
                "memory": [],
                "settings": [],
                "approval": {
                    "title": "No approval data",
                    "summary": "Snapshot provider has not been attached yet.",
                    "consequence": "Desktop shell is receiving only fallback bridge data.",
                },
                "diagnostics": [],
            }

        snapshot = self.snapshot_provider()
        if inspect.isawaitable(snapshot):
            snapshot = await snapshot
        return snapshot

    async def _handle_health(self, _request: web.Request) -> web.Response:
        snapshot = await self._resolve_snapshot()
        return web.json_response(
            {
                "status": "ok",
                "ipcPort": self.port,
                "httpPort": self.http_port,
                "clients": len(self.clients),
                "pendingApprovals": len(self._pending_approvals),
                "state": snapshot.get("state", "idle"),
            },
            headers=self._cors_headers(),
        )

    async def _handle_shell_snapshot(self, _request: web.Request) -> web.Response:
        snapshot = await self._resolve_snapshot()
        return web.json_response(snapshot, headers=self._cors_headers())

    async def _handle_options(self, _request: web.Request) -> web.Response:
        return web.Response(status=204, headers=self._cors_headers())

    async def _start_http_server(self) -> None:
        app = web.Application()
        app.router.add_options("/health", self._handle_options)
        app.router.add_get("/health", self._handle_health)
        app.router.add_options("/shell_snapshot", self._handle_options)
        app.router.add_get("/shell_snapshot", self._handle_shell_snapshot)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", self.http_port)
        logger.info(f"IPC HTTP bridge starting on http://127.0.0.1:{self.http_port}")
        await site.start()
        try:
            await asyncio.Future()
        finally:
            await runner.cleanup()

    async def start(self) -> None:
        """Start the WebSocket server. Blocks forever."""
        logger.info(f"IPC bridge starting on ws://localhost:{self.port}")
        async with websockets.serve(self.handler, "localhost", self.port):
            await self._start_http_server()
