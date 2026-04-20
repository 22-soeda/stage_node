import time
import os
from .abstract_stage import AbstractStage
from .prior_helper import PriorStageHelper
from ..exceptions import StageConnectionError, StageError

class PriorSdk(AbstractStage):
    """Prior製ステージ用ラッパークラス。mm(AbstractStage)とμm(PriorStageHelper)の単位変換を担う"""
    
    def __init__(self, com_port_str: str, dll_path: str = "PriorScientificSDK.dll"):
        self.com_port = com_port_str
        
        # drivers/Prior_driver/ フォルダ内のDLLを参照するようにパスを構築
        if not os.path.isabs(dll_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sdk_dir = os.path.join(current_dir, "Prior_driver") 
            self.resolved_dll_path = os.path.join(sdk_dir, dll_path)
        else:
            self.resolved_dll_path = dll_path
        
        self.helper: PriorStageHelper | None = None
        self._connected = False
        self._moving = False

    def connect(self) -> None:
        if self._connected:
            return

        try:
            print(f"[PriorSdk] Connecting to {self.com_port}...")
            self.helper = PriorStageHelper(dll_path=self.resolved_dll_path)
            
            if not self.helper.initialize_stage(self.com_port):
                self.helper = None
                raise StageConnectionError(f"Priorステージ ({self.com_port}) の初期化に失敗しました。")
                
            self._connected = True
            print(f"[PriorSdk] Connected to {self.com_port}.")
            
        except Exception as e:
            self.helper = None
            raise StageConnectionError(f"Priorステージ接続エラー: {e}")

    def disconnect(self) -> None:
        if self.helper and self._connected:
            print(f"[PriorSdk] Disconnecting from {self.com_port}...")
            try:
                self.helper.close()
            except Exception as e:
                print(f"[PriorSdk] クローズ中にエラー: {e}")
            
            self._connected = False
            self.helper = None
            print("[PriorSdk] Disconnected.")
        
        self._connected = False

    def move_abs(self, x: float, y: float, z: float = 0.0) -> None:
        if not self._connected or not self.helper:
            raise StageError("Priorステージに接続されていません。")

        if z != 0.0:
            print("[PriorSdk] Z 軸は非対応のため z は無視されます。")

        x_microns = x * 1000.0
        y_microns = y * 1000.0

        print(f"[PriorSdk] Move command sent (mm: {x:.3f}, {y:.3f})...")
        try:
            # helper側がノンブロッキングになったため、指示を出してすぐ戻ってくる
            self.helper.move_to_position(x_microns, y_microns) 
        except Exception as e:
            raise StageError(f"Priorステージ移動エラー: {e}")

    def move_rel(self, dx: float, dy: float, dz: float = 0.0) -> None:
        if not self._connected or not self.helper:
            raise StageError("Priorステージに接続されていません。")

        if dz != 0.0:
            print("[PriorSdk] Z 軸は非対応のため dz は無視されます。")
        current_x_mm, current_y_mm, _z = self.get_position()
        self.move_abs(current_x_mm + dx, current_y_mm + dy, 0.0)

    def get_position(self) -> tuple[float, float, float]:
        if not self._connected or not self.helper:
            raise StageError("Priorステージに接続されていません。")

        try:
            x_microns, y_microns = self.helper.get_position()
            return (x_microns / 1000.0, y_microns / 1000.0, 0.0)
        except Exception as e:
            raise StageError(f"Priorステージ位置取得エラー: {e}")

    def set_origin(self) -> None:
        if not self._connected or not self.helper:
            raise StageError("Priorステージに接続されていません。")
            
        try:
            if not self.helper.set_origin_to_current():
                raise StageError("SDKが原点設定に失敗しました。")
            print("[PriorSdk] Origin set to (0, 0).")
        except Exception as e:
            raise StageError(f"Priorステージ原点設定エラー: {e}")

    def is_moving(self) -> bool:
        if not self._connected or not self.helper:
            return False
        return self.helper.is_moving()

    def wait_for_move(self) -> None:
        """ 移動完了まで待機する (GUIなどから明示的にブロックしたい場合用) """
        while self.is_moving():
             time.sleep(0.01)
        
    def is_connected(self) -> bool:
        return self._connected