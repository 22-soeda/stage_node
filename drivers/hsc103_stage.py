import os
import re
import threading
import time

import serial

from .abstract_stage import AbstractStage
from ..exceptions import StageConnectionError, StageError


def _fmt_step(v: int) -> str:
    if v >= 0:
        return str(v)
    return "-" + str(abs(v))


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return float(raw)


def _default_steps_per_mm() -> tuple[float, float, float]:
    """
    Q: / M: / A: で扱うステップ数と mm の換算。

    旧デフォルト 1000 steps/mm では、実機で指令に対し約 1/100 しか移動しない例があった
    （例: 10mm 指令 → 約 0.1mm）。コントローラのステップ解像度に合わせ 100000 を既定とする。

    上書き: MEASUREMENT_HSC103_STEPS_PER_MM（全軸）、
    または MEASUREMENT_HSC103_STEPS_PER_MM_X / _Y / _Z（軸別）。
    """
    base = _float_env("MEASUREMENT_HSC103_STEPS_PER_MM", 100_000.0)
    return (
        _float_env("MEASUREMENT_HSC103_STEPS_PER_MM_X", base),
        _float_env("MEASUREMENT_HSC103_STEPS_PER_MM_Y", base),
        _float_env("MEASUREMENT_HSC103_STEPS_PER_MM_Z", base),
    )


class Hsc103Stage(AbstractStage):
    """
    SIGMA KOKI HSC-103 コントローラ向けステージ (シリアル)。
    サンプル HSC-103.py のコマンド形式に準拠する。座標は AbstractStage どおり mm。

    軸マッピング: アプリ X→軸1、Y→軸2、Z(高さ)→軸3。
    steps_per_mm はコントローラのステップと mm の関係（実機依存）。未指定時は環境変数または _default_steps_per_mm()。
    """

    def __init__(
        self,
        com_port_str: str,
        baudrate: int = 38400,
        steps_per_mm: tuple[float, float, float] | None = None,
        move_tolerance_steps: int = 3,
        move_timeout_s: float | None = None,
        poll_interval_s: float = 0.05,
    ):
        self._port = com_port_str
        self._baudrate = baudrate
        if steps_per_mm is None:
            steps_per_mm = _default_steps_per_mm()
        self._steps_per_mm_x, self._steps_per_mm_y, self._steps_per_mm_z = steps_per_mm
        self._move_tolerance = move_tolerance_steps
        self._move_timeout_s = (
            move_timeout_s
            if move_timeout_s is not None
            else _float_env("MEASUREMENT_HSC103_MOVE_TIMEOUT_S", 300.0)
        )
        self._poll_interval_s = poll_interval_s

        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()
        self._connected = False
        self._origin_steps = (0, 0, 0)
        self._moving = False
        self._target_steps: tuple[int, int, int] | None = None
        self._move_thread: threading.Thread | None = None

    def connect(self) -> None:
        if self._connected:
            return
        try:
            self._ser = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=5,
                rtscts=True,
            )
            self._connected = True
            sx, sy, sz = self._query_steps_unlocked()
            self._origin_steps = (sx, sy, sz)
            print(
                f"[Hsc103Stage] Connected to {self._port}. "
                f"steps/mm=({self._steps_per_mm_x:.1f}, {self._steps_per_mm_y:.1f}, {self._steps_per_mm_z:.1f}). "
                f"Initial position treated as (0,0) mm (steps origin={self._origin_steps})."
            )
        except Exception as e:
            self._ser = None
            self._connected = False
            raise StageConnectionError(f"HSC-103 接続エラー: {e}") from e

    def disconnect(self) -> None:
        self.wait_for_move()
        with self._lock:
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception as e:
                    print(f"[Hsc103Stage] クローズ中にエラー: {e}")
                self._ser = None
            self._connected = False
            self._moving = False
            self._target_steps = None
            self._move_thread = None
        print("[Hsc103Stage] Disconnected.")

    def move_abs(self, x: float, y: float, z: float = 0.0) -> None:
        if not self._connected or not self._ser:
            raise StageError("HSC-103 に接続されていません。")

        self.wait_for_move()

        tx = self._origin_steps[0] + round(x * self._steps_per_mm_x)
        ty = self._origin_steps[1] + round(y * self._steps_per_mm_y)
        tz = self._origin_steps[2] + round(z * self._steps_per_mm_z)
        target = (tx, ty, tz)
        cmd = f"A:{_fmt_step(tx)},{_fmt_step(ty)},{_fmt_step(tz)}\r\n"
        self._issue_move(cmd, target)

    def move_rel(self, dx: float, dy: float, dz: float = 0.0) -> None:
        if not self._connected or not self._ser:
            raise StageError("HSC-103 に接続されていません。")

        self.wait_for_move()

        rx = round(dx * self._steps_per_mm_x)
        ry = round(dy * self._steps_per_mm_y)
        rz = round(dz * self._steps_per_mm_z)
        cur = self._query_steps()
        target = (cur[0] + rx, cur[1] + ry, cur[2] + rz)
        cmd = f"M:{_fmt_step(rx)},{_fmt_step(ry)},{_fmt_step(rz)}\r\n"
        self._issue_move(cmd, target)

    def get_position(self) -> tuple[float, float, float]:
        if not self._connected or not self._ser:
            raise StageError("HSC-103 に接続されていません。")

        sx, sy, sz = self._query_steps()
        x_mm = (sx - self._origin_steps[0]) / self._steps_per_mm_x
        y_mm = (sy - self._origin_steps[1]) / self._steps_per_mm_y
        z_mm = (sz - self._origin_steps[2]) / self._steps_per_mm_z
        return (x_mm, y_mm, z_mm)

    def set_origin(self) -> None:
        if not self._connected or not self._ser:
            raise StageError("HSC-103 に接続されていません。")

        self.wait_for_move()
        self._origin_steps = self._query_steps()
        print(f"[Hsc103Stage] Origin set (steps={self._origin_steps}).")

    def is_moving(self) -> bool:
        return self._moving

    def wait_for_move(self) -> None:
        t = self._move_thread
        if t is not None and t.is_alive():
            t.join()

    def is_connected(self) -> bool:
        return self._connected

    def _issue_move(self, cmd: str, target: tuple[int, int, int]) -> None:
        with self._lock:
            if not self._ser:
                raise StageError("シリアルが開いていません。")
            self._ser.write(cmd.encode("ascii"))
            self._ser.readline()

        self._target_steps = target
        self._moving = True

        def run() -> None:
            """
            目標ステップ到達を待つ。可動域外では物理位置が止まり目標に届かないため、
            ステップ誤差が改善しなくなったら打ち止めとして終了する（ノードが moving のまま固まらない）。
            """
            try:
                deadline = time.monotonic() + self._move_timeout_s
                start = time.monotonic()
                grace_s = _float_env("MEASUREMENT_HSC103_MOVE_GRACE_S", 0.5)
                stall_s = _float_env("MEASUREMENT_HSC103_MOVE_STALL_S", 2.0)
                best_err: float | None = None
                last_improve = start
                while time.monotonic() < deadline:
                    try:
                        cur = self._query_steps()
                        if self._close_enough(cur, target):
                            return
                        err = max(abs(cur[i] - target[i]) for i in range(3))
                        now = time.monotonic()
                        if best_err is None:
                            best_err = err
                            last_improve = now
                        elif err < best_err:
                            best_err = err
                            last_improve = now
                        elif (
                            now - start > grace_s
                            and now - last_improve > stall_s
                        ):
                            print(
                                "[Hsc103Stage] 移動が打ち止めになりました（可動域外・リミット等で目標ステップに届かない可能性） "
                                f"target={target} 現在={cur} err={err} steps"
                            )
                            return
                    except StageError:
                        pass
                    time.sleep(self._poll_interval_s)
                print(
                    f"[Hsc103Stage] 移動がタイムアウトしました (目標ステップ {target})."
                )
            finally:
                self._moving = False
                self._target_steps = None

        self._move_thread = threading.Thread(target=run, daemon=True)
        self._move_thread.start()

    def _query_steps_unlocked(self) -> tuple[int, int, int]:
        if not self._ser:
            raise StageError("シリアルが開いていません。")
        self._ser.write(b"Q:\r\n")
        line = self._ser.readline()
        return self._parse_q_line(line)

    def _query_steps(self) -> tuple[int, int, int]:
        with self._lock:
            return self._query_steps_unlocked()

    @staticmethod
    def _parse_q_line(line: bytes) -> tuple[int, int, int]:
        if not line:
            raise StageError("Q: 応答が空です。")
        s = line.decode(errors="replace").strip()
        nums = re.findall(r"-?\d+", s)
        if len(nums) < 3:
            raise StageError(f"Q: を解釈できませんでした: {s!r}")
        return (int(nums[0]), int(nums[1]), int(nums[2]))

    def _close_enough(
        self,
        cur: tuple[int, int, int],
        target: tuple[int, int, int],
    ) -> bool:
        for a, b in zip(cur, target, strict=True):
            if abs(a - b) > self._move_tolerance:
                return False
        return True
