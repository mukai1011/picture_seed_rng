from datetime import datetime, timedelta
from multiprocessing import Process
from time import perf_counter
from typing import List, Tuple
from typing_extensions import Protocol

from .protocol import Event

class Operation(Protocol):
    def run(self):
        pass

def _sleep(wait_time: timedelta, event: Event):
    """指定時間待機する（別プロセスで実行することを想定したビジーウェイト）

    Args:
        wait_time (timedelta): 待機する時間
        event (Event): 中断用`Event`オブジェクト
    """
    total_seconds = wait_time.total_seconds()
    current_time = perf_counter()
    while perf_counter() < current_time + total_seconds and not event.is_set():
        pass

class TimerInterruptedError(Exception):
    """タイマーが中断で終了したことを伝える内部例外クラス
    """
    pass

def _run_and_wait_in_parallel(operations: List[Operation], wait: Process, event: Event):
    """待機している間、ほかの操作を実行する。
    """
    wait.start()
    
    for op in operations:
        op.run()
    
    #
    # 正常に待機が完了
    # => joinは正常に終了する。
    #
    # GUIのStopにより中断
    # => set_if_not_aliveによってeventがセットされ、joinは正常に終了する。
    #    呼び出し元にタイマーが中断されたことを伝える
    # 
    wait.join()
    if event.is_set():
        raise TimerInterruptedError()

def _get_eta(td: timedelta):
    return datetime.now() + td

def execute(
    operations: Tuple[Operation, Operation, Operation, Operation, Operation], 
    wait_times: Tuple[timedelta, timedelta],
    event: Event
):
    """絵画seed乱数調整を実行する。

    Args:
        operations (Tuple[Operation, Operation, Operation, Operation, Operation]): 各操作を定義したオブジェクトのタプル
        wait_seconds (Tuple[float, float]): 指定する待機時間のタプル
        event (Event): 中断用`Event`オブジェクト
    """
    
    reset, load_game, see_picture, move_to_destination, encounter = operations
    td_seeing, td_encountering = wait_times
    
    wait_seeing = Process(target=_sleep, args=(td_seeing, event))
    wait_encountering = Process(target=_sleep, args=(td_encountering, event))

    try:
        reset.run()

        print(f"タイマーを開始しました。ETA:{_get_eta(td_seeing)}")
        try:
            _run_and_wait_in_parallel(
                [
                    load_game
                ], 
                wait_seeing, event
            )
        except TimerInterruptedError:
            # タイマーが中断された場合はreturnすれば、次のcheckIfAliveでStopThreadがraiseされて正常に停止する... はず
            return

        print(f"タイマーを開始しました。ETA:{_get_eta(td_encountering)}")
        try:
            _run_and_wait_in_parallel(
                [
                    see_picture, 
                    move_to_destination
                ], 
                wait_encountering, event
            )
        except TimerInterruptedError:
            return

        encounter.run()

    finally:
        # 例外処理は呼び出し元に投げるが、Processは破棄する
        print("タイマーを破棄します。")
        for proc in [proc for proc in [wait_seeing, wait_encountering] if proc.is_alive()]:
            proc.join()
