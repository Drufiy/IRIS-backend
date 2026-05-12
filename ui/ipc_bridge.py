"""Python WebSocket server that bridges IRIS core to the Tauri UI overlay."""

import asyncio
import json
import websockets
from loguru import logger


class IPCBridge:
    """
    WebSocket server on localhost:7788.
    Tauri overlay connects as a client and receives state_change events.
    Also handles approval_request/approval_response for DANGEROUS actions.
    """

    def __init__(self, port: int = 7788) -> None:
        self.port = port
        self.clients: set = set()
        self._pending_approvals: dict[str, asyncio.Future] = {}

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

    async def start(self) -> None:
        """Start the WebSocket server. Blocks forever."""
        logger.info(f"IPC bridge starting on ws://localhost:{self.port}")
        async with websockets.serve(self.handler, "localhost", self.port):
            await asyncio.Future()  # Run forever
