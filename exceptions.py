class StageError(Exception):
    """ステージ操作に関する一般的なエラーの基底クラス"""
    pass

class StageConnectionError(StageError):
    """ステージの接続・切断時に発生するエラー"""
    pass