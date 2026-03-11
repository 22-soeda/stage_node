from abc import ABC, abstractmethod

class AbstractStage(ABC):
    """
    全てのリニアステージ実装が従うべき抽象基底クラス(インターフェース)。
    座標系はミリメートル (mm) を想定。
    """

    @abstractmethod
    def connect(self) -> None:
        """
        ステージに接続します。
        失敗した場合は例外 (例: core.exceptions.StageConnectionError) を送出します。
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        ステージとの接続を切断します。
        """
        pass

    @abstractmethod
    def move_abs(self, x: float, y: float) -> None:
        """
        絶対座標 (x, y) に移動します。
        移動が完了するまでブロック (待機) するか、
        非同期で移動を開始するかは実装によります (完了待機が望ましい)。
        """
        pass

    @abstractmethod
    def move_rel(self, dx: float, dy: float) -> None:
        """
        現在位置から相対座標 (dx, dy) だけ移動します。
        """
        pass

    @abstractmethod
    def get_position(self) -> tuple[float, float]:
        """
        現在のステージ座標 (x, y) を取得します。
        
        :return: (x, y) タプル
        """
        pass

    @abstractmethod
    def set_origin(self) -> None:
        """
        現在の座標を原点 (0, 0) として設定します。
        """
        pass

    @abstractmethod
    def is_moving(self) -> bool:
        """
        ステージが現在移動中か確認します。
        """
        pass

    @abstractmethod
    def wait_for_move(self) -> None:
        """
        ステージの移動が完了するまで待機します。
        """
        pass
        
    @abstractmethod
    def is_connected(self) -> bool:
        """
        ステージが現在接続されているか確認します。
        """
        pass