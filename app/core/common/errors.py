class ExceptionForUser(Exception):
    def __init__(self, exc):
        self.exc = exc

    def __str__(self):
        return f'({self.exc.__class__.__name__}) {self.exc}'



class MaximumRetry(Exception):
    ...

class Conflict(Exception):
    ...

class InvaildInstance(Exception):
    ...

class RepositoryNotFound(Exception):
    ...


