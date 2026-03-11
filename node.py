import time
import zmq
import json
import queue

# coreパッケージから設定を読み込む
from core import network_config
from core import message_config

from .stage_controller import StageController
from .terminal_handler import TerminalHandler

class StageNode:
    """ZMQ通信とステージノードのメインループを管理するクラス"""
    def __init__(self):
        self.context = zmq.Context()
        
        # ステータス配信ソケット
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(network_config.ZMQ_URL_STAGE_PUB)

        # コマンド受信ソケット
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.bind(network_config.ZMQ_URL_STAGE_SUB)
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "") 

        # 内部コンポーネントの初期化
        self.cmd_queue = queue.Queue()
        self.stage_ctrl = StageController()
        self.terminal = TerminalHandler(self.cmd_queue)

    def run(self):
        print(f"Stage Node Started.")
        print(f"  Listening for commands on: {network_config.ZMQ_URL_STAGE_SUB}")
        print(f"  Publishing status on:      {network_config.ZMQ_URL_STAGE_PUB}")
        print(f"  Publishing topic:          {message_config.TOPIC_STAGE_STATUS.decode()}")
        
        # ターミナル入力の待ち受けスレッドを開始
        self.terminal.start()
        
        try:
            while True:
                # 1. ターミナル入力からのコマンド処理
                while not self.cmd_queue.empty():
                    cmd = self.cmd_queue.get_nowait()
                    self.stage_ctrl.handle_command(cmd)

                # 2. ZMQネットワークからのコマンド処理 (ノンブロッキング)
                try:
                    cmd_json = self.sub_socket.recv_string(flags=zmq.NOBLOCK)
                    cmd = json.loads(cmd_json)
                    self.stage_ctrl.handle_command(cmd)
                except zmq.Again:
                    pass
                except Exception as e:
                    print(f"[Node] Failed to parse ZMQ command: {e}")

                # 3. ステータス（座標など）の取得と配信
                status = self.stage_ctrl.get_status()
                self.pub_socket.send(message_config.TOPIC_STAGE_STATUS, zmq.SNDMORE)
                # JSONとしてシリアライズして送信（GUIノード等で扱いやすくするため）
                self.pub_socket.send_json(status)

                # ステージのステータス更新はカメラほど高頻度である必要がないため、少し長めのsleepでも可
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nShutting down Stage Node...")
        finally:
            self.stage_ctrl.cleanup()
            self.pub_socket.close()
            self.sub_socket.close()
            self.context.term()