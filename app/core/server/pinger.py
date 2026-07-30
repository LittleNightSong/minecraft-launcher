import asyncio
import time

import msgspec

from app.core.models.server_meta import ServerMeta
from app.core.server.protocol import encode_ping, encode_handshake, encode_status_request, decode_status_response, \
    encode_varint


def parse_addr(addr, default_port=25565):
    sep = addr.rfind(':')
    if sep == -1:
        host = addr
        port = default_port
    else:
        host = addr[:sep]
        port = int(addr[sep + 1:])

    return host, port


async def read_varint(reader: asyncio.StreamReader, timeout=None) -> tuple[int, int]:
    """从流中读取一个 VarInt，返回 (值, 读取字节数)"""
    result = 0
    bytes_read = 0
    for i in range(5):
        byte = await asyncio.wait_for(reader.readexactly(1), timeout=timeout)
        bytes_read += 1
        result |= (byte[0] & 0x7F) << (7 * i)
        if (byte[0] & 0x80) == 0:
            # 补码转换
            if result & (1 << 31):
                result -= (1 << 32)
            return result, bytes_read
    raise ValueError("VarInt too long (max 5 bytes)")


async def read_packet(reader: asyncio.StreamReader, timeout=None) -> bytes:
    length = (await read_varint(reader, timeout))[0]
    if length < 0:
        raise ValueError("Invalid VarInt length")

    return await asyncio.wait_for(
        reader.readexactly(length),
        timeout=timeout
    )


async def write_packet(writer: asyncio.StreamWriter, payload: bytes, timeout: int | float | None = None):
    length = len(payload)
    assert length > 0

    data = encode_varint(length) + payload
    writer.write(data)
    await asyncio.wait_for(writer.drain(), timeout=timeout)


async def ping_server(addr: str, timeout: int | None = None):
    host, port = parse_addr(addr)

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port),
        timeout=timeout
    )

    await write_packet(
        writer,
        encode_handshake(
            0, host, port, 1
        ),
        timeout
    )  # 发送 intention，设置状态
    await write_packet(writer, encode_status_request(), timeout=timeout)  # 发送 status 请求

    pkg = await read_packet(reader, timeout)  # 接收一个数据包
    assert pkg[0] == 0x00  # 确保是一个 status_response 类型的包
    response = decode_status_response(pkg)

    # if response:
    #     print(response)

    await  write_packet(writer, encode_ping(int(time.monotonic())), timeout)
    pong = await read_packet(reader, timeout)

    assert pong[0] == 0x01

    delay = int(time.monotonic()) - int.from_bytes(pong[1:])

    writer.close()

    return msgspec.json.decode(response, type=ServerMeta), delay


if __name__ == '__main__':
    from rich import print


    async def run(addr):
        response, delay = await ping_server(addr)  # 获取服务器信息
        print(response)
        print("延迟：", delay)


    async def main():
        await run('mc.hypixel.net')


    asyncio.run(main())
