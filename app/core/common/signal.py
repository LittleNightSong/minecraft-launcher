class SignalInstance:
    def __init__(self, signal: Signal):
        self.signal = signal


class Signal:
    def __get__(self, instance, owner):
        if instance is None:
            return self

        else:
            return 