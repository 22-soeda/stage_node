from ctypes import WinDLL, create_string_buffer, c_int
import os
import time
import re
from typing import Tuple

class PriorStageHelper:
    """X軸の座標系の反転を吸収するヘルパー層"""
    def __init__(self, dll_path: str):
        self.sessionID = -1
        self.sdk = None
        self.rx = create_string_buffer(1000)
        self.dll_path = dll_path
        self._is_initialized = False

    def initialize_stage(self, com_port_str: str) -> bool:
        original_cwd = os.getcwd() 
        dll_full_path = os.path.abspath(self.dll_path)
        dll_dir = os.path.dirname(dll_full_path)
        
        try:
            if not os.path.exists(dll_full_path):
                print(f"Error: DLL not found at {dll_full_path}")
                return False

            os.chdir(dll_dir) 

            ftd_dll_path = os.path.join(dll_dir, "ftd2xx.dll")
            if os.path.exists(ftd_dll_path):
                try:
                    WinDLL(ftd_dll_path)
                except Exception as e:
                    print(f"Warning: Failed to preload {ftd_dll_path}: {e}")
            
            self.sdk = WinDLL(dll_full_path)
            
            if self.sdk.PriorScientificSDK_Initialise():
                return False

            self.sessionID = self.sdk.PriorScientificSDK_OpenNewSession()
            if self.sessionID < 0:
                return False

            match = re.search(r'(\d+)$', com_port_str)
            if not match:
                return False
            com_port_number = match.group(1)
            
            ret, response = self._send_command(f"controller.connect {com_port_number}")
            if ret != 0:
                print(f"Connection failed ({com_port_str}): {response}")
                return False
                
            self._is_initialized = True
            return True

        except Exception as e:
            print(f"Unexpected error during initialization: {e}")
            self._is_initialized = False
            return False
        
        finally:
            os.chdir(original_cwd)

    def _send_command(self, command_str: str) -> Tuple[int, str]:
        if not self.sdk or self.sessionID < 0:
            return -1, "SDK not initialized"
            
        self.rx.value = b""
        cmd_bytes = create_string_buffer(command_str.encode('utf-8'))
        
        ret = self.sdk.PriorScientificSDK_cmd(
            c_int(self.sessionID), 
            cmd_bytes, 
            self.rx
        )
        return ret, self.rx.value.decode('utf-8').strip() 

    def close(self):
        if self._is_initialized:
            self._send_command("controller.disconnect")
        
        if self.sdk and self.sessionID >= 0:
            self.sdk.PriorScientificSDK_CloseSession(c_int(self.sessionID))
            
        self._is_initialized = False
        self.sdk = None

    def set_origin_to_current(self) -> bool:
        ret, _ = self._send_command("controller.stage.position.set 0 0")
        return ret == 0

    def get_position(self) -> Tuple[float, float]:
        ret, response = self._send_command("controller.stage.position.get")
        if ret == 0:
            try:
                parts = response.split(',')
                # コントローラのX座標を反転させて実際の座標に合わせる
                return -float(parts[0]), float(parts[1])
            except (IndexError, ValueError):
                pass
        return 0.0, 0.0

    # --- prior_helper.py の該当部分を修正・追加 ---

    def move_to_position(self, x: float, y: float):
        """ 
        指定された (x, y) 座標に移動を開始する (単位: microns) 
        (修正: 完了を待たずにすぐリターンする)
        """
        x_controller = -x
        ret, response = self._send_command(f"controller.stage.goto-position {x_controller} {y}")
        
        if ret != 0:
            print(f"移動開始エラー: {response} (戻り値: {ret})")
            
        # ※ここにあった while self._is_initialized: ... の待機ループを削除

    def is_moving(self) -> bool:
        """ ステージが現在移動中かどうかを確認する (新規追加) """
        if not self._is_initialized:
            return False
            
        ret, busy_response = self._send_command("controller.stage.busy.get")
        if ret == 0:
            try:
                status = int(busy_response.split(',')[0]) 
                return status != 0  # 0以外なら移動中
            except (IndexError, ValueError):
                pass
        return False

    def stop_move(self):
        self._send_command("controller.stage.move-at-velocity 0 0")