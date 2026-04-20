"""
stage_node entry: PUB position + REP commands + CLI (>>> prompt).

  uv run python -m stage_node.main --interval-ms 200

仮想ステージ (DummyStage) は既定で有効。実装予定の実機のみ使う場合は ``--no-dummy``。

After launch, type ``connect dummy`` (optional; default is already connected), ``status``, ``move_abs ...``.
"""

import argparse

from stage_node.node import StageNode


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Node (DummyStage virtual hardware or future serial)")
    parser.add_argument(
        "--no-dummy",
        action="store_true",
        help="Disable DummyStage (real hardware; not yet implemented)",
    )
    parser.add_argument("--port", default="COM3", help="Serial port when using hardware (with --no-dummy)")
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
