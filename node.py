"""
stage_node: ZMQ PUB (STAGE topic) + REP (commands).

Compatible with sequence_node NodeClient: cmd/get_status style JSON.
"""

from __future__ import annotations

import json
import queue
import threading
import time

import zmq

from core import message_config as msg
from core import network_config as net

from stage_node.stage_controller import StageController
from stage_node.terminal_handler import TerminalHandler


class StageNode:
    def __init__(self, interval_ms: int = 200, dummy: bool = True, port: str = "COM3"):
        self._interval_ms = interval_ms
        self._running = False
        self._start_time = 0.0
        self._controller = StageController(dummy=dummy, port=port)
        self._cmd_queue: queue.Queue = queue.Queue()
        self._pub_queue: queue.Queue = queue.Queue()
        self._terminal = TerminalHandler(self._cmd_queue)

        self._ctx = zmq.Context()
        self._pub = self._ctx.socket(zmq.PUB)
        self._pub.bind(net.bind_addr(net.STAGE_PUB_PORT))
        self._rep = self._ctx.socket(zmq.REP)
        self._rep.bind(net.bind_addr(net.STAGE_CMD_PORT))

    def run(self) -> None:
        self._running = True
        self._start_time = time.time()

        threading.Thread(target=self._measure_loop, daemon=True, name="stage-pub").start()
        self._terminal.start()

        poller = zmq.Poller()
        poller.register(self._rep, zmq.POLLIN)

        print(
            f"[stage_node] Running.\n"
            f"  PUB  {net.bind_addr(net.STAGE_PUB_PORT)}  topic={msg.TOPIC_STAGE.decode()}\n"
            f"  REP  {net.bind_addr(net.STAGE_CMD_PORT)}\n",
            flush=True,
        )

        try:
            while True:
                while not self._pub_queue.empty():
                    payload = self._pub_queue.get_nowait()
                    self._pub.send_multipart(
                        [msg.TOPIC_STAGE, json.dumps(payload).encode()]
                    )

                while not self._cmd_queue.empty():
                    cmd = self._cmd_queue.get_nowait()
                    resp = self._controller.handle_command(cmd)
                    self._print_response(resp)

                events = dict(poller.poll(10))
                if self._rep in events:
                    raw = self._rep.recv()
                    cmd = json.loads(raw.decode())
                    resp = self._controller.handle_command(cmd)
                    self._rep.send(json.dumps(resp).encode())

        except KeyboardInterrupt:
            print("\n[stage_node] Shutting down...", flush=True)
        finally:
            self._running = False
            self._controller.cleanup()
            self._pub.close()
            self._rep.close()
            self._ctx.term()

    @staticmethod
    def _print_response(resp: dict) -> None:
        if resp.get("status") == "error":
            print(f"[Error] {resp.get('error')}", flush=True)
        else:
            items = {k: v for k, v in resp.items() if k != "status"}
            if items:
                print(f"[OK] {items}", flush=True)

    def _measure_loop(self) -> None:
        interval = self._interval_ms / 1000.0
        while self._running:
            snap = self._controller.get_snapshot()
            now = time.time()
            connected = snap.get("connected", False)
            node_status = "measuring" if connected else "idle"
            self._pub_queue.put(
                {
                    "timestamp": now,
                    "elapsed": now - self._start_time,
                    **snap,
                    "node_status": node_status,
                }
            )
            time.sleep(interval)
