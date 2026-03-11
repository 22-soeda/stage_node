import threading
import queue

class TerminalHandler:
    """ターミナルからの標準入力を別スレッドで処理するクラス"""
    def __init__(self, cmd_queue: queue.Queue):
        self.cmd_queue = cmd_queue
        # daemon=True にすることで、メインプログラム終了時に自動でスレッドも終了する
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        print("\n--- Terminal Command Help ---")
        print("  connect [driver] [port]  (e.g., connect prior COM3, connect dummy)")
        print("  disconnect")
        print("  move_abs [x] [y]         (e.g., move_abs 10.5 5.0)")
        print("  move_rel [dx] [dy]       (e.g., move_rel 1.0 -1.0)")
        print("  set_origin")
        print("-----------------------------\n")
        
        while True:
            try:
                line = input().strip()
                if not line: continue
                
                parts = line.split()
                action = parts[0].lower()
                cmd = {"action": action}
                
                if action == "connect":
                    cmd["driver"] = parts[1] if len(parts) > 1 else "dummy"
                    cmd["port"] = parts[2] if len(parts) > 2 else "COM3"
                
                elif action == "move_abs":
                    if len(parts) > 2:
                        cmd["x"] = float(parts[1])
                        cmd["y"] = float(parts[2])
                    else:
                        print(f"[Terminal] Missing value. Format: {action} [x] [y]")
                        continue
                
                elif action == "move_rel":
                    if len(parts) > 2:
                        cmd["dx"] = float(parts[1])
                        cmd["dy"] = float(parts[2])
                    else:
                        print(f"[Terminal] Missing value. Format: {action} [dx] [dy]")
                        continue
                
                elif action not in ["disconnect", "set_origin"]:
                    print(f"[Terminal] Unknown command: {action}")
                    continue
                        
                # キューにコマンドを積む
                self.cmd_queue.put(cmd)
                
            except ValueError:
                print("[Terminal] Invalid number format. Please enter valid floats.")
            except EOFError:
                break
            except Exception as e:
                print(f"[Terminal] Input error: {e}")