"""
Stage command handling: DummyStage (virtual) or future hardware.
外部 API の座標は µm。DummyStage 内部は mm のため境界で換算する。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from stage_node.drivers.abstract_stage import AbstractStage
from stage_node.drivers.dummy_stage import DummyStage
from stage_node.exceptions import StageConnectionError

UM_PER_MM = 1000.0


class StageController:
    """REQ/REP / CLI からのコマンドを処理し、接続済み DummyStage または将来の実機で座標を管理する。"""

    def __init__(self, dummy: bool = True, port: str = "COM3"):
        self._dummy_mode = dummy
        self._port = port
        self._lock = threading.Lock()
        self._driver: AbstractStage | None = None
        self._driver_name = "none"

        if self._dummy_mode:
            self._driver = DummyStage()
            self._driver.connect()
            self._driver_name = "dummy"

    def handle_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        action = (cmd.get("action") or cmd.get("cmd") or "").lower()

        if action in ("get_status", "status"):
            return self._status_response()
        if action == "connect":
            return self._handle_connect(cmd)
        if action == "disconnect":
            return self._disconnect()
        if action == "home":
            return self._home(cmd.get("axes"))
        if action == "set_origin":
            return self._set_origin()
        if action == "move_absolute":
            return self._move_absolute(cmd)
        if action == "move_relative":
            return self._move_relative(cmd)
        if action == "wait_stop":
            return self._wait_stop(float(cmd.get("timeout", 30.0)))
        if action == "configure":
            return {"status": "ok"}
        if action == "set_param":
            return {"status": "ok", "note": "stage dummy: no-op"}

        return {"status": "error", "error": f"Unknown command: {action!r}"}

    def _ensure_connected(self) -> tuple[bool, dict[str, Any] | None]:
        if self._driver is None or not self._driver.is_connected():
            return False, {
                "status": "error",
                "error": "Not connected (use: connect dummy|prior|hsc103 <port>)",
            }
        return True, None

    def _handle_connect(self, cmd: dict[str, Any]) -> dict[str, Any]:
        driver = self._normalize_driver_name((cmd.get("driver") or "dummy").lower())
        self._port = str(cmd.get("port") or self._port)

        try:
            with self._lock:
                if self._driver is not None and self._driver.is_connected():
                    self._driver.disconnect()
                self._driver = self._create_driver(driver, self._port)
                self._driver.connect()
                self._driver_name = driver
        except StageConnectionError as e:
            return {"status": "error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": f"Connect failed for {driver!r}: {e}"}

        return {"status": "ok", "driver": self._driver_name, "port": self._port}

    def _disconnect(self) -> dict[str, Any]:
        with self._lock:
            if self._driver is not None and self._driver.is_connected():
                self._driver.disconnect()
        return {"status": "ok"}

    def _set_origin(self) -> dict[str, Any]:
        ok, err = self._ensure_connected()
        if not ok:
            return err  # type: ignore[return-value]
        try:
            with self._lock:
                assert self._driver is not None
                self._driver.set_origin()
        except StageConnectionError as e:
            return {"status": "error", "error": str(e)}
        return {"status": "ok"}

    def _status_response(self) -> dict[str, Any]:
        x_um, y_um, z_um = self._position_um()
        moving = False
        connected = False
        if self._driver is not None:
            connected = self._driver.is_connected()
            if connected:
                moving = self._driver.is_moving()
        return {
            "status": "ok",
            "connected": connected,
            "dummy": self._driver_name in ("dummy", "mock"),
            "driver": self._driver_name,
            "x_um": x_um,
            "y_um": y_um,
            "z_um": z_um,
            "moving": moving,
            "port": self._port,
        }

    def _home(self, axes: list | None) -> dict[str, Any]:
        ok, err = self._ensure_connected()
        if not ok:
            return err  # type: ignore[return-value]
        if axes is None:
            axes = [True, True, True]
        px, py, pz = self._position_um()
        tx = 0.0 if axes[0] else px
        ty = 0.0 if axes[1] else py
        tz = 0.0 if axes[2] else pz
        return self._move_absolute({"x": tx, "y": ty, "z": tz})

    def _move_absolute(self, cmd: dict[str, Any]) -> dict[str, Any]:
        ok, err = self._ensure_connected()
        if not ok:
            return err  # type: ignore[return-value]
        px, py, pz = self._position_um()
        tx = float(cmd["x"]) if "x" in cmd else px
        ty = float(cmd["y"]) if "y" in cmd else py
        tz = float(cmd["z"]) if "z" in cmd else pz
        try:
            with self._lock:
                assert self._driver is not None
                self._driver.move_abs(tx / UM_PER_MM, ty / UM_PER_MM, tz / UM_PER_MM)
        except StageConnectionError as e:
            return {"status": "error", "error": str(e)}
        return {"status": "ok"}

    def _move_relative(self, cmd: dict[str, Any]) -> dict[str, Any]:
        ok, err = self._ensure_connected()
        if not ok:
            return err  # type: ignore[return-value]
        dx = float(cmd.get("dx", 0.0))
        dy = float(cmd.get("dy", 0.0))
        dz = float(cmd.get("dz", 0.0))
        try:
            with self._lock:
                assert self._driver is not None
                self._driver.move_rel(dx / UM_PER_MM, dy / UM_PER_MM, dz / UM_PER_MM)
        except StageConnectionError as e:
            return {"status": "error", "error": str(e)}
        return {"status": "ok"}

    def _wait_stop(self, timeout: float) -> dict[str, Any]:
        ok, err = self._ensure_connected()
        if not ok:
            return err  # type: ignore[return-value]
        deadline = time.time() + max(0.0, timeout)
        while True:
            with self._lock:
                moving = self._driver is not None and self._driver.is_moving()
            if not moving:
                return {"status": "ok"}
            if time.time() >= deadline:
                return {"status": "error", "error": "wait_stop timeout"}
            time.sleep(0.01)

    def _position_um(self) -> tuple[float, float, float]:
        with self._lock:
            if self._driver is None or not self._driver.is_connected():
                return (0.0, 0.0, 0.0)
            try:
                x, y, z = self._driver.get_position()
            except StageConnectionError:
                return (0.0, 0.0, 0.0)
            return (x * UM_PER_MM, y * UM_PER_MM, z * UM_PER_MM)

    def get_snapshot(self) -> dict[str, Any]:
        x_um, y_um, z_um = self._position_um()
        moving = False
        connected = False
        if self._driver is not None:
            connected = self._driver.is_connected()
            if connected:
                moving = self._driver.is_moving()
        return {
            "x_um": x_um,
            "y_um": y_um,
            "z_um": z_um,
            "moving": moving,
            "connected": connected,
            "driver": self._driver_name,
        }

    def cleanup(self) -> None:
        with self._lock:
            if self._driver is not None and self._driver.is_connected():
                self._driver.disconnect()

    @staticmethod
    def _normalize_driver_name(driver: str) -> str:
        aliases = {
            "mock": "dummy",
            "hsc-103": "hsc103",
        }
        return aliases.get(driver, driver)

    def _create_driver(self, driver: str, port: str) -> AbstractStage:
        if driver == "dummy":
            return DummyStage()
        if driver == "prior":
            from stage_node.drivers.prior_sdk import PriorSdk

            return PriorSdk(com_port_str=port)
        if driver == "hsc103":
            from stage_node.drivers.hsc103_stage import Hsc103Stage

            return Hsc103Stage(com_port_str=port)
        raise StageConnectionError(
            f"Driver not implemented: {driver!r} (use dummy|prior|hsc103)"
        )
