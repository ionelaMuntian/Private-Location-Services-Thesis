from time import perf_counter


class StepTimer:
    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed_ms(self) -> float:
        return round((perf_counter() - self._start) * 1000.0, 3)