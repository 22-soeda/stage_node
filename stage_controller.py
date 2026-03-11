from .drivers.dummy_stage import DummyStage
from .drivers.prior_sdk import PriorSdk

class StageController:
    """ステージドライバのライフサイクルと操作を管理するクラス"""
    def __init__(self):
        self.stage = None

    def _create_driver(self, driver_type: str, port: str):
        if driver_type.lower() == "prior":
            return PriorSdk(com_port_str=port)
        return DummyStage()

    def handle_command(self, cmd: dict):
        """辞書型のコマンドを受け取り、ステージを操作する"""
        action = cmd.get("action")
        
        if action == "connect":
            self.cleanup() # 既存の接続があれば切断
            driver_type = cmd.get("driver", "dummy")
            port = cmd.get("port", "COM9")
            self.stage = self._create_driver(driver_type, port)
            try:
                self.stage.connect()
                print(f"[StageController] Connected to {driver_type} on {port}.")
            except Exception as e:
                print(f"[StageController] Connection failed: {e}")
                self.stage = None

        elif action == "disconnect":
            self.cleanup()
            print("[StageController] Disconnected.")

        # 以下、ステージが接続されている場合のみ有効なコマンド
        elif self.stage is not None and self.stage.is_connected():
            try:
                if action == "move_abs":
                    self.stage.move_abs(cmd.get("x", 0.0), cmd.get("y", 0.0))
                elif action == "move_rel":
                    self.stage.move_rel(cmd.get("dx", 0.0), cmd.get("dy", 0.0))
                elif action == "set_origin":
                    self.stage.set_origin()
            except Exception as e:
                print(f"[StageController] Error executing {action}: {e}")
        else:
            if action not in ["connect", "disconnect"]:
                print(f"[StageController] Stage is not connected. Ignored command: {action}")

    def get_status(self):
        """現在の座標や移動状態を取得する"""
        if self.stage is not None and self.stage.is_connected():
            try:
                x, y = self.stage.get_position()
                is_moving = self.stage.is_moving()
                return {"connected": True, "x": x, "y": y, "is_moving": is_moving}
            except Exception:
                pass
        
        return {"connected": False, "x": 0.0, "y": 0.0, "is_moving": False}

    def cleanup(self):
        """終了処理・切断処理"""
        if self.stage is not None:
            self.stage.disconnect()
            self.stage = None