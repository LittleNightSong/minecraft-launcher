import time


class SimpleStopWatch:
    __slots__ = ('_res', '_start')

    def __init__(self):
        self._start = None
        self._res = None

    def start(self):
        self._start = time.time() * 1000
        return self

    def stop(self, restart=False):
        self._res = time.time() * 1000 - self._start
        self._start = None

        if restart:
            self.start()

        return self._res

    @property
    def start_time(self):
        return self._start

    @property
    def elapsed_time(self):
        if self._start is None:
            return self._res
        return time.time() * 1000 - self._start

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
