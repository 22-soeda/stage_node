"""
stage_node entry: PUB position + REP commands + CLI (>>> prompt).

  uv run python -m stage_node.main --interval-ms 200

仮想ステージ (DummyStage) は既定で有効。実機を使う場合は起動後 `connect prior COMx` または
`connect hsc103 COMx` を実行してください（`--no-dummy` なら未接続で起動）。

After launch, type ``connect dummy`` (optional; default is already connected), ``status``, ``move_abs ...``.
"""

import argparse

from stage_node.node import StageNode


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Node (DummyStage virtual hardware or future serial)")
    parser.add_argument(
        "--no-dummy",
        action="store_true",
        help="Disable auto-connect DummyStage at startup",
    )
    parser.add_argument("--port", default="COM3", help="Default serial port for connect command")
    parser.add_argument("--interval-ms", type=int, default=200, help="PUB interval")
    args = parser.parse_args()

    node = StageNode(
        interval_ms=args.interval_ms,
        dummy=not args.no_dummy,
        port=args.port,
    )
    node.run()


if __name__ == "__main__":
    main()
