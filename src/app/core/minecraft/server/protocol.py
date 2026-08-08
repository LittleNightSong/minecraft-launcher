"""
对于 java 版部分数据包协议的编码和解码实现
主要围绕 Server Ping 功能

Mainly Written by `DeepSeek`
According to `Minecraft Wiki`
"""
import struct

import msgspec
from qh3.quic import packet


def encode_varint(n):
    """将整数编码为 Minecraft VarInt（修正版）"""
    # 先用 struct 转为 4 字节补码（小端序）
    packed = struct.pack('<i', n)
    # 转为无符号整数以便按位操作
    n = int.from_bytes(packed, 'little', signed=False)

    result = bytearray()

    for _ in range(5):  # VarInt 最多 5 字节
        byte = n & 0x7F  # 取出低 7 位
        n >>= 7  # 右移 7 位

        if n != 0:
            byte |= 0x80  # 设置续传标志位
            result.append(byte)
        else:
            result.append(byte)  # 最后一个字节不设续传标志
            break
    else:
        # 如果循环正常结束（没有 break），说明数值超出范围
        raise ValueError("VarInt too large (max 5 bytes)")

    return bytes(result)


def decode_varint(data):
    """
    从字节流中解码一个 VarInt

    :param data: bytes 或 bytearray，至少包含 1 个字节

    :return: (value, length), 解码出的整数值和消耗的字节数

    :raise ValueError: 如果数据不足或 VarInt 超过 5 字节
    """
    if not data:
        raise ValueError("No data to decode VarInt")

    result = 0
    bytes_read = 0

    for i in range(5):  # VarInt 最多 5 字节
        if i >= len(data):
            raise ValueError(f"Incomplete VarInt: only {len(data)} bytes available")

        byte = data[i]
        bytes_read += 1

        # 取出低 7 位数据
        result |= (byte & 0x7F) << (7 * i)

        # 如果最高位为 0，表示这是最后一个字节
        if (byte & 0x80) == 0:
            break
    else:
        # 循环正常结束（没有 break），说明 VarInt 超过 5 字节
        raise ValueError("VarInt too long (max 5 bytes)")

    # 将解码出的无符号整数转换为有符号整数（补码转换）
    # VarInt 是 32 位有符号整数，所以检查第 31 位
    if result & (1 << 31):
        result -= (1 << 32)

    return result, bytes_read


def encode_string(s):
    """将字符串编码为 Minecraft String（前缀 VarInt 长度）"""
    if len(s) > 32767:  # Minecraft 字符串最大长度限制
        raise ValueError(f"String too long: {len(s)} > 32767")

    # 先编码长度
    encoded_str = s.encode('utf-8')
    length_prefix = encode_varint(len(encoded_str))

    return length_prefix + encoded_str


def decode_string(data):
    """
    从字节流中解码一个 Minecraft String

    返回:
        (value, length): 解码出的字符串和消耗的字节数
    """
    str_len, bytes_read = decode_varint(data)

    if str_len < 0:
        raise ValueError(f"Invalid string length: {str_len}")

    if str_len > 32767:
        raise ValueError(f"String too long: {str_len} > 32767")

    # 检查数据是否足够
    if len(data) < bytes_read + str_len:
        raise ValueError(f"Incomplete string: need {str_len} bytes, have {len(data) - bytes_read}")

    # 解码字符串内容
    str_data = data[bytes_read:bytes_read + str_len]
    try:
        value = str_data.decode('utf-8')
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid UTF-8 string: {e}")

    return value, bytes_read + str_len


def encode_handshake(protocol_version, server_address, server_port, next_state):
    """
    编码 Handshake 数据包（数据包 ID: 0x00）

    参数:
        protocol_version: 协议版本（如 776）
        server_address: 服务器地址（如 "localhost"）
        server_port: 服务器端口（如 25565）
        next_state: 下一状态（1 为状态查询，2 为登录）

    返回:
        bytes: 完整的 Handshake 数据包（包含数据包长度前缀）
    """
    # 构建数据包负载
    payload = bytearray()
    payload.extend(encode_varint(0x00))  # 数据包 ID
    payload.extend(encode_varint(protocol_version))
    payload.extend(encode_string(server_address))
    payload.extend(struct.pack('>H', server_port))  # 无符号短整型（大端序）
    payload.extend(encode_varint(next_state))

    return bytes(payload)


def encode_status_request():
    """
    编码 Status Request 数据包（数据包 ID: 0x00）

    返回:
        bytes:  Status Request 负载
    """
    # 数据包 ID
    return encode_varint(0x00)


def decode_status_response(data):
    """
    解码 Status Response 数据包（数据包 ID: 0x00）

    :return: 返回一个 json 字符串
    """

    # 读取数据包 ID
    packet_id, id_bytes = decode_varint(data)

    if packet_id != 0x00:
        raise ValueError(f"Unexpected packet ID: {packet_id}, expected 0x00")

    # 读取 JSON 响应字符串
    json_response, _ = decode_string(data[id_bytes:])

    return json_response


def encode_ping(payload: int):
    """
    编码 Ping 数据包（数据包 ID: 0x01）

    参数:
        payload: 8 字节的 long 类型负载（通常是时间戳）

    返回:
        bytes: 完整的 Ping 数据包
    """
    # 构建数据包负载
    packet = encode_varint(0x01)  # 数据包 ID
    packet += struct.pack('>q', payload)  # 8 字节有符号长整型（大端序）

    return packet


# ============= 使用示例 =============
if __name__ == "__main__":
    # 测试 VarInt 编解码
    test_values = [0, 1, 127, 128, 255, 256, 2147483647, -1, -5, -2147483648]
    print("=" * 50)
    print("测试 VarInt 编解码")
    print("=" * 50)
    for val in test_values:
        encoded = encode_varint(val)
        decoded, bytes_read = decode_varint(encoded)
        print(f"原始: {val:>12} -> 编码: {encoded.hex():>10} -> 解码: {decoded:>12} (消耗 {bytes_read} 字节)")

    print("\n" + "=" * 50)
    print("测试字符串编解码")
    print("=" * 50)
    test_strings = ["Hello, World!", "Minecraft", "中文测试", "🔥🎮"]
    for s in test_strings:
        encoded = encode_string(s)
        decoded, bytes_read = decode_string(encoded)
        print(f"原始: '{s}' -> 解码: '{decoded}' (消耗 {bytes_read} 字节)")

    print("\n" + "=" * 50)
    print("测试 Handshake 数据包")
    print("=" * 50)
    handshake = encode_handshake(776, "localhost", 25565, 1)
    print(f"Handshake 数据包长度: {len(handshake)} 字节")
    print(f"Hex: {handshake.hex()}")

    print("\n" + "=" * 50)
    print("测试 Status Request 数据包")
    print("=" * 50)
    status_req = encode_status_request()
    print(f"Status Request 长度: {len(status_req)} 字节")
    print(f"Hex: {status_req.hex()}")
