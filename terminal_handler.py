"""
stage_node/terminal_handler.py - CLI input handler for stage_node.
"""

from core.terminal_handler import TerminalHandlerBase


class TerminalHandler(TerminalHandlerBase):
    HELP_LINES = [
        "Stage Node  (DummyStage virtual | future hardware)",
        "─" * 42,
        "connect [dummy|mock] [port]                 mock is alias for dummy",
        "disconnect",
        "status",
        "home  OR  home <0|1> <0|1> <0|1>          axes x y z (1=homing)",
        "set_origin                                  current position -> app origin",
        "move_absolute <x> <y> [z]                   alias: move_abs  (µm)",
        "move_relative <dx> <dy> [dz]                alias: move_rel  (µm)",
        "wait_stop [timeout_sec]                     default 30",
        "help",
    ]

    def _parse(self, line: str) -> dict | None:
        parts = line.split()
        if not parts:
            return None
        action = parts[0].lower()

        if action == "connect":
            driver = parts[1] if len(parts) > 1 else "dummy"
            port = parts[2] if len(parts) > 2 else "COM3"
            return {"action": "connect", "driver": driver, "port": port}

        if action in ("disconnect", "status"):
            return {"action": action}

        if action == "home":
            if len(parts) == 1:
                return {"action": "home"}
            if len(parts) == 4:
                try:
                    axes = [bool(int(parts[1])), bool(int(parts[2])), bool(int(parts[3]))]
                except ValueError:
                    print("[Terminal] Axes must be 0 or 1.")
                    return None
                return {"action": "home", "axes": axes}
            print("[Terminal] Usage: home  OR  home <0|1> <0|1> <0|1>")
            return None

        if action == "set_origin":
            return {"action": "set_origin"}

        if action in ("move_absolute", "move_abs"):
            if len(parts) < 3:
                print("[Terminal] Usage: move_absolute <x_um> <y_um> [z_um]")
                return None
            try:
                cmd: dict = {
                    "action": "move_absolute",
                    "x": float(parts[1]),
                    "y": float(parts[2]),
                }
                if len(parts) > 3:
                    cmd["z"] = float(parts[3])
                return cmd
            except ValueError:
                print("[Terminal] Invalid number.")
                return None

        if action in ("move_relative", "move_rel"):
            if len(parts) < 3:
                print("[Terminal] Usage: move_relative <dx_um> <dy_um> [dz_um]")
                return None
            try:
                cmd = {
                    "action": "move_relative",
                    "dx": float(parts[1]),
                    "dy": float(parts[2]),
                }
                if len(parts) > 3:
                    cmd["dz"] = float(parts[3])
                return cmd
            except ValueError:
                print("[Terminal] Invalid number.")
                return None

        if action == "wait_stop":
            try:
                timeout = float(parts[1]) if len(parts) > 1 else 30.0
            except ValueError:
                print("[Terminal] Invalid timeout.")
                return None
            return {"action": "wait_stop", "timeout": timeout}

        print(f"[Terminal] Unknown command: '{action}'  (type 'help' for list)")
        return None
