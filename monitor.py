import json
import math
import os
import sys
import time

import matplotlib

matplotlib.use("QtAgg")

import numpy as np
import zmq
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import message_config
from core import network_config

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Pyramid3DCanvas(FigureCanvasQTAgg):
    """
    三角錐の先端がステージ座標 (x, y, z)（高さ z mm）に来るように描画する。
    """

    def __init__(self, parent=None):
        self._fig = Figure(figsize=(5, 4), facecolor="#1e1e1e")
        super().__init__(self._fig)
        self.setParent(parent)
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._ax.set_facecolor("#1e1e1e")
        self._ax.set_xlabel("X (mm)", color="#cccccc")
        self._ax.set_ylabel("Y (mm)", color="#cccccc")
        self._ax.set_zlabel("Z (mm)", color="#cccccc")
        self._ax.tick_params(colors="#aaaaaa")
        self._ax.xaxis.pane.fill = False
        self._ax.yaxis.pane.fill = False
        self._ax.zaxis.pane.fill = False
        self._ax.xaxis.pane.set_edgecolor("#444444")
        self._ax.yaxis.pane.set_edgecolor("#444444")
        self._ax.zaxis.pane.set_edgecolor("#444444")
        self._ax.grid(True, alpha=0.3)
        self._pyramid_height_mm = 8.0
        self._base_radius_mm = 4.0
        self._last_xyz: tuple[float, float, float] | None = None

    def set_stage_position(self, x: float, y: float, z: float) -> None:
        if self._last_xyz is not None:
            ox, oy, oz = self._last_xyz
            if (
                abs(ox - x) < 1e-6
                and abs(oy - y) < 1e-6
                and abs(oz - z) < 1e-6
            ):
                return
        self._last_xyz = (x, y, z)
        self._ax.clear()
        self._ax.set_facecolor("#1e1e1e")
        self._ax.set_xlabel("X (mm)", color="#cccccc")
        self._ax.set_ylabel("Y (mm)", color="#cccccc")
        self._ax.set_zlabel("Z (mm)", color="#cccccc")
        self._ax.tick_params(colors="#aaaaaa")
        self._ax.xaxis.pane.fill = False
        self._ax.yaxis.pane.fill = False
        self._ax.zaxis.pane.fill = False
        self._ax.grid(True, alpha=0.3)

        h = self._pyramid_height_mm
        r = self._base_radius_mm
        tip = np.array([x, y, z])
        verts_up = []
        for k in range(3):
            ang = 2 * math.pi * k / 3.0 + math.pi / 2.0
            verts_up.append(
                np.array(
                    [x + r * math.cos(ang), y + r * math.sin(ang), z + h],
                    dtype=float,
                )
            )
        v1, v2, v3 = verts_up

        faces = [
            np.array([tip, v1, v2]),
            np.array([tip, v2, v3]),
            np.array([tip, v3, v1]),
            np.array([v1, v2, v3]),
        ]
        mesh = Poly3DCollection(
            faces,
            facecolors=("#e74c3c", "#c0392b", "#e74c3c", "#a93226"),
            edgecolors="#ffffff",
            linewidths=0.6,
            alpha=0.92,
        )
        self._ax.add_collection3d(mesh)

        half = max(25.0, abs(x) + 15.0, abs(y) + 15.0)
        self._ax.set_xlim(x - half, x + half)
        self._ax.set_ylim(y - half, y + half)
        z_lo = min(0.0, z - 5.0)
        z_hi = max(25.0, z + h + 8.0)
        self._ax.set_zlim(z_lo, z_hi)
        self._ax.set_box_aspect((1, 1, 0.45))
        self._ax.view_init(elev=22, azim=-60)
        self.draw()


class StageMonitorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stage Monitor")
        self.resize(920, 560)

        self._status_connected = False
        self._context = zmq.Context()
        self._sub = self._context.socket(zmq.SUB)
        self._sub.connect(network_config.pub_addr(network_config.STAGE_PUB_PORT))
        self._sub.setsockopt(zmq.SUBSCRIBE, message_config.TOPIC_STAGE_STATUS)

        self._cmd_pub = self._context.socket(zmq.PUB)
        self._cmd_pub.connect(network_config.pub_addr(network_config.STAGE_CMD_PORT))
        time.sleep(0.25)

        main_layout = QVBoxLayout(self)

        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel("Driver:"))
        self.driver_edit = QLineEdit()
        self.driver_edit.setPlaceholderText("dummy / prior / hsc103")
        self.driver_edit.setText("dummy")
        self.driver_edit.setFixedWidth(140)
        conn_row.addWidget(self.driver_edit)

        conn_row.addWidget(QLabel("Address:"))
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("COM3 など")
        self.address_edit.setText("COM3")
        self.address_edit.setFixedWidth(120)
        conn_row.addWidget(self.address_edit)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._on_connect)
        conn_row.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        conn_row.addWidget(self.btn_disconnect)

        conn_row.addStretch()
        main_layout.addLayout(conn_row)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step (mm):"))
        self.step_edit = QLineEdit()
        self.step_edit.setText("1.0")
        self.step_edit.setFixedWidth(100)
        step_row.addWidget(self.step_edit)
        hint = QLabel("パッド: 上=+Y / 下=-Y / 右=+X / 左=-X、Z±=高さ（相対移動）")
        hint.setStyleSheet("color: #888888;")
        step_row.addWidget(hint)
        step_row.addStretch()
        main_layout.addLayout(step_row)

        body = QHBoxLayout()
        info_panel = QWidget()
        info_panel.setFixedWidth(260)
        info_layout = QVBoxLayout(info_panel)

        self.conn_label = QLabel("Status: DISCONNECTED")
        self.conn_label.setAlignment(Qt.AlignCenter)
        self.conn_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: gray;"
        )
        info_layout.addWidget(self.conn_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        info_layout.addWidget(line)

        self.pos_label = QLabel("X: --- mm\nY: --- mm\nZ: --- mm")
        self.pos_label.setAlignment(Qt.AlignCenter)
        self.pos_label.setStyleSheet(
            "font-size: 20px; font-family: monospace; color: #333;"
        )
        info_layout.addWidget(self.pos_label)

        pad_outer = QHBoxLayout()
        pad_outer.addStretch()
        xy_grid = QGridLayout()
        xy_grid.setSpacing(4)

        def _pad_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setFixedSize(44, 36)
            b.setStyleSheet("font-size: 18px;")
            return b

        self._btn_up = _pad_btn("↑")
        self._btn_down = _pad_btn("↓")
        self._btn_left = _pad_btn("←")
        self._btn_right = _pad_btn("→")
        self._btn_z_up = _pad_btn("Z+")
        self._btn_z_down = _pad_btn("Z−")
        self._btn_up.clicked.connect(lambda: self._move_rel_xy(0.0, 1.0))
        self._btn_down.clicked.connect(lambda: self._move_rel_xy(0.0, -1.0))
        self._btn_left.clicked.connect(lambda: self._move_rel_xy(-1.0, 0.0))
        self._btn_right.clicked.connect(lambda: self._move_rel_xy(1.0, 0.0))
        self._btn_z_up.clicked.connect(lambda: self._move_rel_z(1.0))
        self._btn_z_down.clicked.connect(lambda: self._move_rel_z(-1.0))

        corner = QWidget()
        corner.setFixedSize(44, 36)
        xy_grid.addWidget(self._btn_up, 0, 1)
        xy_grid.addWidget(self._btn_left, 1, 0)
        xy_grid.addWidget(corner, 1, 1)
        xy_grid.addWidget(self._btn_right, 1, 2)
        xy_grid.addWidget(self._btn_down, 2, 1)

        z_col = QVBoxLayout()
        z_col.setSpacing(4)
        z_col.addWidget(self._btn_z_up)
        z_col.addWidget(self._btn_z_down)

        pad_outer.addLayout(xy_grid)
        pad_outer.addLayout(z_col)
        pad_outer.addStretch()
        info_layout.addLayout(pad_outer)

        self.state_label = QLabel("---")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setStyleSheet("font-size: 18px; color: gray;")
        info_layout.addWidget(self.state_label)
        info_layout.addStretch()

        self.pyramid_canvas = Pyramid3DCanvas()
        body.addWidget(info_panel)
        body.addWidget(self.pyramid_canvas, stretch=1)
        main_layout.addLayout(body, stretch=1)

        self.timer = QTimer()
        self.timer.timeout.connect(self._poll_zmq)
        self.timer.start(30)

    def _parse_step_mm(self) -> float:
        try:
            v = float(self.step_edit.text().strip())
            if v <= 0:
                return 1.0
            return v
        except ValueError:
            return 1.0

    def _move_rel_xy(self, dir_x: float, dir_y: float) -> None:
        if not self._status_connected:
            return
        step = self._parse_step_mm()
        self._send_cmd(
            {
                "action": "move_rel",
                "dx": dir_x * step,
                "dy": dir_y * step,
                "dz": 0.0,
            }
        )

    def _move_rel_z(self, dir_z: float) -> None:
        if not self._status_connected:
            return
        step = self._parse_step_mm()
        self._send_cmd(
            {
                "action": "move_rel",
                "dx": 0.0,
                "dy": 0.0,
                "dz": dir_z * step,
            }
        )

    def _send_cmd(self, cmd: dict) -> None:
        try:
            self._cmd_pub.send_string(json.dumps(cmd))
        except Exception as e:
            QMessageBox.warning(self, "送信エラー", str(e))

    def _on_connect(self) -> None:
        driver = self.driver_edit.text().strip() or "dummy"
        port = self.address_edit.text().strip() or "COM3"
        self._send_cmd({"action": "connect", "driver": driver, "port": port})

    def _on_disconnect(self) -> None:
        self._send_cmd({"action": "disconnect"})

    def _poll_zmq(self) -> None:
        try:
            while True:
                topic = self._sub.recv(flags=zmq.NOBLOCK)
                status = self._sub.recv_json(flags=zmq.NOBLOCK)
                self._update_ui(status)
        except zmq.Again:
            pass
        except Exception as e:
            print(f"ZMQ Error in monitor: {e}")

    def _update_ui(self, status: dict) -> None:
        is_connected = status.get("connected", False)
        x = float(status.get("x", 0.0))
        y = float(status.get("y", 0.0))
        z = float(status.get("z", 0.0))
        is_moving = status.get("is_moving", False)

        self._status_connected = is_connected

        if is_connected:
            self.pyramid_canvas.set_stage_position(x, y, z)
            self.conn_label.setText("Status: CONNECTED")
            self.conn_label.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: #0078D7;"
            )
            self.pos_label.setText(
                f"X: {x:>8.3f} mm\nY: {y:>8.3f} mm\nZ: {z:>8.3f} mm"
            )
            self.pos_label.setStyleSheet(
                "font-size: 24px; font-family: monospace; color: #222;"
            )
            if is_moving:
                self.state_label.setText("MOVING...")
                self.state_label.setStyleSheet(
                    "font-size: 18px; font-weight: bold; color: #D13438;"
                )
            else:
                self.state_label.setText("IDLE")
                self.state_label.setStyleSheet(
                    "font-size: 18px; font-weight: bold; color: #107C10;"
                )
        else:
            self.conn_label.setText("Status: DISCONNECTED")
            self.conn_label.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: gray;"
            )
            self.pos_label.setText("X: --- mm\nY: --- mm\nZ: --- mm")
            self.pos_label.setStyleSheet(
                "font-size: 24px; font-family: monospace; color: #333;"
            )
            self.state_label.setText("---")
            self.state_label.setStyleSheet("font-size: 18px; color: gray;")

    def closeEvent(self, event):
        self._sub.close()
        self._cmd_pub.close()
        self._context.term()
        event.accept()


def main():
    app = QApplication(sys.argv)
    w = StageMonitorWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
