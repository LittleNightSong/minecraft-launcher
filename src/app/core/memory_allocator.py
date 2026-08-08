class MemoryAllocator:
    def __init__(self):
        self.extra_percent = 0.1
        self.reserve_percent = 0.2


    def allocate(self, free: int):
        # 用一个很简单的公式计算出分配给 JVM 堆的内存大小
        # 可用内存减去保留的（额外堆内存 + 预留系统内存）
        return int(free * (1 - (self.extra_percent + self.reserve_percent)))