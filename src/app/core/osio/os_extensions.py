import os


def read_all(fd, buffer_size=8192):
    data = bytearray()
    buffer = bytearray(buffer_size)

    while n := os.readinto(fd, buffer):
        data.extend(buffer[:n])

    return bytes(data)


