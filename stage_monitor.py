import sys
import os
import zmq

# プロジェクトのルートディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import network_config
from core import message_config

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame
from PySide6.QtCore import QTimer, Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

class MapWidget(QWidget):
    """ステージの現在位置を2D平面上に描画するカスタムウィジェット"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)
        
        self.current_x = 0.0
        self.current_y = 0.0
        self.view_range_mm = 50.0  # マップの表示範囲 (中心から±50mm)
        self.trail = []            # 軌跡を保存するリスト
        self.max_trail_length = 50 # 軌跡の最大保存数

    def set_position(self, x: float, y: float):
        """座標を更新し、再描画を要求する"""
        # 座標が変化した場合のみ軌跡に追加
        if not self.trail or self.trail[-1] != (x, y):
            self.trail.append((x, y))
            if len(self.trail) > self.max_trail_length:
                self.trail.pop(0)
                
        self.current_x = x
        self.current_y = y
        self.update() # paintEventをトリガー

    def paintEvent(self, event):
        """ウィジェットの描画処理"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        
        # 1. 背景の描画 (ダークテーマ)
        painter.fillRect(0, 0, w, h, QColor("#1e1e1e"))

        # 中心座標とスケール計算 (ピクセル/mm)
        cx = w / 2
        cy = h / 2
        scale_x = cx / self.view_range_mm
        scale_y = cy / self.view_range_mm

        # 2. グリッドと軸の描画
        # 10mm間隔のサブグリッド
        grid_pen = QPen(QColor("#333333"), 1, Qt.DashLine)
        painter.setPen(grid_pen)
        step_mm = 10.0
        for i in range(int(-self.view_range_mm), int(self.view_range_mm) + 1, int(step_mm)):
            x_px = cx + (i * scale_x)
            y_px = cy - (i * scale_y)
            painter.drawLine(x_px, 0, x_px, h) # 縦線
            painter.drawLine(0, y_px, w, y_px) # 横線

        # X/Y の主軸 (0, 0)
        axis_pen = QPen(QColor("#777777"), 2)
        painter.setPen(axis_pen)
        painter.drawLine(0, cy, w, cy) # X軸
        painter.drawLine(cx, 0, cx, h) # Y軸

        # 3. 軌跡(トレイル)の描画
        if len(self.trail) > 1:
            trail_pen = QPen(QColor("#55aaff"), 2, Qt.SolidLine)
            painter.setPen(trail_pen)
            
            for i in range(len(self.trail) - 1):
                p1_x, p1_y = self.trail[i]
                p2_x, p2_y = self.trail[i+1]
                
                # Y軸は画面上が負、下が正のため符号を反転させる
                pt1 = QPointF(cx + (p1_x * scale_x), cy - (p1_y * scale_y))
                pt2 = QPointF(cx + (p2_x * scale_x), cy - (p2_y * scale_y))
                painter.drawLine(pt1, pt2)

        # 4. 現在位置のマーカーを描画
        px = cx + (self.current_x * scale_x)
        py = cy - (self.current_y * scale_y)
        
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.setBrush(QBrush(QColor("#ff4444")))
        radius = 6
        painter.drawEllipse(QPointF(px, py), radius, radius)

        # 5. スケール情報のテキスト描画
        painter.setPen(QColor("#aaaaaa"))
        painter.drawText(10, 20, f"Map Range: ±{self.view_range_mm} mm")
        painter.drawText(10, 35, f"Grid: 10 mm")


class StageMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stage Status & Map Monitor")
        self.resize(650, 400)

        # ZMQ初期化 (Subscriber)
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect(network_config.ZMQ_URL_STAGE_PUB)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, message_config.TOPIC_STAGE_STATUS)

        # UI構築 (左右に分割)
        main_layout = QHBoxLayout()

        # --- 左側: 情報パネル ---
        info_panel = QWidget()
        info_layout = QVBoxLayout(info_panel)
        info_panel.setFixedWidth(250)

        self.conn_label = QLabel("Status: DISCONNECTED")
        self.conn_label.setAlignment(Qt.AlignCenter)
        self.conn_label.setStyleSheet("font-size: 16px; font-weight: bold; color: gray;")
        info_layout.addWidget(self.conn_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        info_layout.addWidget(line)

        self.pos_label = QLabel("X: --- mm\nY: --- mm")
        self.pos_label.setAlignment(Qt.AlignCenter)
        self.pos_label.setStyleSheet("font-size: 26px; font-family: monospace; color: #333;")
        info_layout.addWidget(self.pos_label)

        self.state_label = QLabel("---")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setStyleSheet("font-size: 18px; color: gray;")
        info_layout.addWidget(self.state_label)
        
        info_layout.addStretch() # 上寄せにするためのスペーサー

        # --- 右側: 2Dマップ ---
        self.map_widget = MapWidget()

        main_layout.addWidget(info_panel)
        main_layout.addWidget(self.map_widget)
        self.setLayout(main_layout)

        # ZMQ受信用のタイマー (30ms周期)
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_zmq)
        self.timer.start(30)

    def poll_zmq(self):
        try:
            while True:
                topic = self.sub_socket.recv(flags=zmq.NOBLOCK)
                status = self.sub_socket.recv_json(flags=zmq.NOBLOCK)
                self.update_ui(status)
        except zmq.Again:
            pass
        except Exception as e:
            print(f"ZMQ Error in monitor: {e}")

    def update_ui(self, status: dict):
        is_connected = status.get("connected", False)
        x = status.get("x", 0.0)
        y = status.get("y", 0.0)
        is_moving = status.get("is_moving", False)

        # マップの更新
        if is_connected:
            self.map_widget.set_position(x, y)

        # テキスト情報の更新
        if is_connected:
            self.conn_label.setText("Status: CONNECTED")
            self.conn_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0078D7;")
            self.pos_label.setText(f"X: {x:>8.3f} mm\nY: {y:>8.3f} mm")
            
            if is_moving:
                self.state_label.setText("MOVING...")
                self.state_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #D13438;")
            else:
                self.state_label.setText("IDLE")
                self.state_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #107C10;")
        else:
            self.conn_label.setText("Status: DISCONNECTED")
            self.conn_label.setStyleSheet("font-size: 16px; font-weight: bold; color: gray;")
            self.pos_label.setText("X: --- mm\nY: --- mm")
            self.state_label.setText("---")
            self.state_label.setStyleSheet("font-size: 18px; color: gray;")

    def closeEvent(self, event):
        self.sub_socket.close()
        self.context.term()
        event.accept()

def main():
    app = QApplication(sys.argv)
    monitor = StageMonitor()
    monitor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()