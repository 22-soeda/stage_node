import time
import threading
from .abstract_stage import AbstractStage
from ..exceptions import StageConnectionError 

class DummyStage(AbstractStage):
    def __init__(self):
        self._connected = False
        self._x = 0.0 
        self._y = 0.0
        self._origin_x = 0.0 
        self._origin_y = 0.0
        self._moving = False
        self._move_thread = None # スレッド管理用
        print("[DummyStage] Initialized (Offset-based).")

    def connect(self) -> None:
        if self._connected:
            print("[DummyStage] Already connected.")
            return

        print("[DummyStage] Connecting...")
        time.sleep(0.5)
        self._connected = True
        print("[DummyStage] Connected.")

    def disconnect(self) -> None:
        if not self._connected:
            return
            
        print("[DummyStage] Disconnecting...")
        time.sleep(0.1)
        self._connected = False
        print("[DummyStage] Disconnected.")

    def move_abs(self, x: float, y: float) -> None:
        if not self._connected:
            raise StageConnectionError("Dummy stage is not connected.")
        
        target_abs_x = self._origin_x + x
        target_abs_y = self._origin_y + y
            
        print(f"[DummyStage] Move command to (App: {x:.2f}, {y:.2f})...")
        
        # 既存の移動スレッドがあれば待機してリセット
        if self._move_thread and self._move_thread.is_alive():
            self.wait_for_move()

        # 別スレッドで移動をシミュレーション
        self._move_thread = threading.Thread(
            target=self._simulate_movement, 
            args=(target_abs_x, target_abs_y),
            daemon=True
        )
        self._move_thread.start()

    def _simulate_movement(self, target_x: float, target_y: float):
        """別スレッドで座標を少しずつ更新する"""
        self._moving = True
        start_x, start_y = self._x, self._y
        
        distance = ((start_x - target_x)**2 + (start_y - target_y)**2)**0.5
        move_time = max(0.1, distance / 10.0) # 10mm/secで移動
        
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed >= move_time:
                break
            
            # 進行度(0.0 ~ 1.0)に応じて現在位置を補間
            progress = elapsed / move_time
            self._x = start_x + (target_x - start_x) * progress
            self._y = start_y + (target_y - start_y) * progress
            time.sleep(0.02) # 50Hzで更新
            
        self._x = target_x
        self._y = target_y
        self._moving = False

    def move_rel(self, dx: float, dy: float) -> None:
        if not self._connected:
            raise StageConnectionError("Dummy stage is not connected.")
            
        current_x, current_y = self.get_position()
        self.move_abs(current_x + dx, current_y + dy)

    def get_position(self) -> tuple[float, float]:
        if not self._connected:
            raise StageConnectionError("Dummy stage is not connected.")
            
        app_x = self._x - self._origin_x
        app_y = self._y - self._origin_y
        return (app_x, app_y)

    def set_origin(self) -> None:
        if not self._connected:
            raise StageConnectionError("Dummy stage is not connected.")
            
        self._origin_x = self._x
        self._origin_y = self._y
        print(f"[DummyStage] Origin set to internal offset ({self._origin_x:.2f}, {self._origin_y:.2f})")

    def is_moving(self) -> bool:
        return self._moving

    def wait_for_move(self) -> None:
        while self._moving:
            time.sleep(0.01)
            
    def is_connected(self) -> bool:
        return self._connected