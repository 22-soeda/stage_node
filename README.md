# Stage Node

自動顕微鏡イメージングシステムにおける、XYリニアステージの制御を担当するZeroMQベースの独立ノードです。
Prior Scientific社製のステージ（実機）の制御と、開発・テスト用のダミーステージ（シミュレータ）の両方に対応しています。

## 🌟 特徴
- **分散アーキテクチャ**: ZeroMQ (PUB/SUB) を用いて他のノード（シーケンスノードやGUIノードなど）と疎結合に通信します。
- **実機＆シミュレーション対応**: 実際のハードウェア（Priorステージ）を動かすモードと、ソフトウェア上で滑らかな移動をシミュレートするダミーモードを動的に切り替え可能です。
- **非同期制御**: ステージの移動中も処理をブロックせず、リアルタイムに現在の座標やステータス（移動中かどうか）を配信します。
- **2Dリアルタイムモニター**: PySide6を利用したGUIモニターを同梱しており、現在のステージ座標や直近の移動軌跡を視覚的に確認できます。

## 📁 ディレクトリ構成
```text
stage_node/
├── main.py                 # ノードの起動用エントリーポイント
├── node.py                 # ZMQ通信とメインループの管理
├── stage_controller.py     # コマンドの解釈とドライバの切り替え
├── stage_monitor.py        # 2Dマップ表示機能付きのステータスモニター (PySide6)
├── terminal_handler.py     # CUIからの手動コマンド入力ハンドラ
└── drivers/                # ハードウェアごとのドライバ実装
    ├── abstract_stage.py   # ステージドライバの共通インターフェース
    ├── dummy_stage.py      # シミュレーション用ダミーステージ
    ├── exceptions.py       # ステージ制御用のカスタム例外
    ├── prior_helper.py     # Prior製DLLとの通信・座標反転などを吸収する低レイヤー
    ├── prior_sdk.py        # Priorステージの高レイヤーラッパー
    └── Prior_driver/       # ※ここにベンダー提供のDLLを配置します
        ├── PriorScientificSDK.dll
        ├── ftd2xx.dll
        └── ...
```
**注意**: Priorステージを使用する場合は、`drivers/Prior_driver/` フォルダを作成し、対応するSDK（.dllファイル）を配置してください。

## 🚀 起動方法

### 1. ステージノードの起動
ターミナルを開き、プロジェクトのルートディレクトリ（microscope_auto_imaging/）から以下のコマンドを実行します。

```bash
python -m stage_node.main
```
起動すると、標準入力（ターミナル）からのコマンド待ち受けと、ZMQによるネットワークコマンドの待ち受けが開始されます。

### 2. ステージモニター（2Dマップ）の起動
別のターミナルを開き、同じくプロジェクトのルートディレクトリから以下のコマンドを実行します。（※実行には PySide6 がインストールされている必要があります）

```bash
python -m stage_node.stage_monitor
```
モニターを起動すると、ステージの現在位置（X, Y）、接続ステータス、移動状態（IDLE/MOVING）がリアルタイムに描画されます。

## ⌨️ 利用可能なコマンド
ターミナル入力、または ZMQ ネットワーク経由（JSON形式）で以下のコマンドを受け付けます。

| コマンド      | 説明                                         | 入力例 (ターミナル)   | ZMQメッセージ(JSON)例                                      |
|:--------------|:---------------------------------------------|:----------------------|:-----------------------------------------------------------|
| `connect`     | ステージに接続します。引数: driver (prior/dummy), port | `connect dummy 0`     | `{"action": "connect", "driver": "prior", "port": "COM3"}` |
|               |                                              | `connect prior COM3`  |                                                            |
| `disconnect`  | ステージから切断します。                     | `disconnect`          | `{"action": "disconnect"}`                               |
| `move_abs`    | 指定した絶対座標(mm)へ移動します。引数: x, y | `move_abs 10.5 -5.0`  | `{"action": "move_abs", "x": 10.5, "y": -5.0}`             |
| `move_rel`    | 現在地からの相対座標(mm)で移動します。引数: dx, dy | `move_rel 1.0 0.5`    | `{"action": "move_rel", "dx": 1.0, "dy": 0.5}`             |
| `set_origin`  | 現在の座標をソフトウェア的な原点(0,0)に設定します。 | `set_origin`          | `{"action": "set_origin"}`                               |

## 📡 ZMQ 通信仕様

### コマンド受信 (SUB)
- エンドポイント: `tcp://127.0.0.1:5551` (※ [`network_config.py`](core/network_config.py) に依存)
- 形式: JSON形式の文字列

### ステータス配信 (PUB)
- エンドポイント: `tcp://127.0.0.1:5556`
- トピック: `stage/status` (※ [`message_config.py`](core/message_config.py) に依存)
- 形式: Multipart通信 (Frame 1: Topic, Frame 2: JSON)

配信データ例:
```json
{
  "connected": true,
  "x": 10.523,
  "y": -5.001,
  "is_moving": false
}
```

## 🛠 依存ライブラリ
- `pyzmq` : ZeroMQ通信用
- `PySide6` : ステージモニター用（GUI）