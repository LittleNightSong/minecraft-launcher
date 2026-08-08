import asyncio
import os
import re
import subprocess
from pathlib import Path

import athreading
from loguru import logger

_matcher = re.compile(r'(\w+) version "(.+)"\s*(\d{4}-\d{2}-\d{2})?')


async def detect_java_version(path):
    logger.info("开始检测位于 {} 的 java 二进制可执行文件", path)

    path = Path(path)
    # 检查几个重要文件
    for e in java_executables:
        if not (path / e).exists():
            return None

    # 通过命令行获取 java 版本号
    ps = await asyncio.create_subprocess_exec(
        path / 'java.exe', '-version',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    output, _ = await ps.communicate()
    string = output.decode()

    logger.debug("已获取到输出 {:100}", string)

    # 获取第一行
    line = string.split('\n', 1)[0].strip()
    logger.info("提取到第一行 {}", line)

    # 尝试匹配
    result = _matcher.match(line)
    if result:
        type = result.group(1)
        version = result.group(2)
        # 无论如何, 只信任第一位版本号(主版本号)
        if version.startswith('1.8'):  # java 1.8 就是 java 8
            logger.info("检测结果: {}, {}", type, 8)
            return type if type != 'java' else 'jre', 8
        else:
            major = int(version.split('.', 1)[0])
            logger.info("检测结果: {}, {}", type, major)
            return type, major

    else:
        logger.info("无法匹配")
        return None


if os.name == 'nt':
    java_executables = ('java.exe', 'javaw.exe')
else:
    java_executables = ('java', 'javaw')


def _s_serach_java(path, max_depth=None, depth=0):
    # java 的目录结构特征是包含 bin 目录, 且 目录下有 java.exe, javaw.exe 等文件 (Windows)
    # Posix 系统不包含拓展名
    logger.info("准备检查位置 {}", path)

    bin = os.path.join(path, 'bin')
    if os.path.isdir(bin):
        logger.info("在 {} 发现 bin 目录, 开始查找")
        for i in _s_serach_java(bin, max_depth, depth=float('inf')):  # 这里传 inf 是为了防止进一步搜索子目录
            yield i
            return  # 这里不可能找到第二个 java 了, 拿到一个就直接退出

    # 先在给出的 path 中尝试查找
    for e in java_executables:  # 当缺少任何其中一个可执行文件都退出
        if not os.path.isfile(os.path.join(path, e)):
            # 说明它不是 java 目录, 开始搜索子目录

            # 先检查深度, 不要多创建 task
            if max_depth is not None and depth > max_depth:
                logger.info("已达到最大搜索深度 {}, 不再检查子目录", max_depth)
                return

            # 随后在子目录中查找
            for i in os.scandir(path):
                if i.is_dir():
                    # logger.info("发现子目录 {:100}", i.name)
                    yield from _s_serach_java(i.path, max_depth, depth + 1)
            return

    yield path  # 此时可以确定是一个 java 目录, 返回 path
    return




@athreading.iterate
def _serach_java(path, max_depth=None, depth=0):
    yield from _s_serach_java(path, max_depth, depth)


async def search_java(path, max_depth=None):
    # 相对于同步版本, 它添加了后处理
    # 现在它将生成 (path, type, major) 的三元组, 并且自动跳过无法解析的 java
    logger.info("开始从 {} 搜索 Java", path)
    async with _serach_java(path, max_depth) as generator:
        async for path in generator:
            logger.info("发现一个疑似 java 的路径 {:100}", path)
            try:
                result = await detect_java_version(path)

                if result is None:
                    logger.info("{} 不是 java 路径", path)
                    continue

                logger.info("{} 是 java 路径", path)
                yield path, *result
            except (PermissionError, FileNotFoundError) as e:
                logger.error("在获取版本中发生错误")
                logger.opt(exception=e)

                continue


async def detect_java_from_java_home():
    logger.info("尝试从 JAVA_HOME 中提取 java 位置")
    if java_home := os.getenv('JAVA_HOME', None):
        logger.info("成功获取到 JAVA_HOME={}", java_home)
        type, major = await detect_java_version(os.path.join(java_home, 'bin'))
        if type is not None:
            return java_home, type, major
    else:
        logger.info("无 JAVA_HOME")
    return None


async def detect_java_from_path_env():
    """从 PATH 环境变量中查找 java 可执行文件，解析出 JAVA_HOME 并检测版本"""
    logger.info("尝试从 PATH 环境变量中解析 java 位置")

    path_env = os.getenv('PATH', '')
    for dir_path in path_env.split(os.pathsep):
        if not dir_path.strip():
            continue

        # 尝试查找 java 可执行文件（跨平台）
        for exe in java_executables:
            exe_path = os.path.join(dir_path, exe)
            logger.debug("拼接路径: {}", exe_path)
            # 检查是否为文件且可执行（Windows 下可执行性检查可能不同，但 os.access 可用）
            isfile = os.path.isfile(exe_path)
            access = os.access(exe_path, os.X_OK)

            logger.info("访问结果: isfile={}, X-Access={}", isfile, access)

            if isfile and access:
                logger.info("路径 {} 可用", exe_path)
                try:
                    # 解析软链接（Windows 下 os.path.realpath 也能处理 junction 等）
                    real_path = os.path.realpath(exe_path)
                    logger.info("追踪路径成功: {}", real_path)
                except Exception as e:
                    real_path = exe_path
                    logger.opt(exception=e).warning("在追踪路径时发生错误, 回退到未追踪状态")

                java_bin = os.path.dirname(real_path)
                logger.info("提取 Java Bin 为 {}", java_bin)
                try:
                    result = await detect_java_version(java_bin)
                    if result is not None:
                        logger.info("成功检测位于 {} 的 java 版本: {}", java_bin, result)
                        yield java_bin, *result
                    else:
                        logger.info("无法检测位于 {} 的 java 版本", java_bin)
                except (PermissionError, FileNotFoundError, subprocess.SubprocessError) as e:
                    logger.opt(exception=e).error("在检测位于 {} 的 java 时发生异常", java_bin)
                    continue
            else:
                logger.info("路径 {} 不可用", exe_path)


async def detect_java_from_programs():
    """从系统默认的 Java 安装目录中查找第一个有效的 Java 环境"""
    # 根据操作系统定义常见安装根目录
    if os.name == 'nt':  # Windows
        default_paths = [
            i
            for dev in 'CDEFGHIJKLMNOPQRSTUVWXYZAB'
            for i in (rf'{dev}:\Program Files', rf'{dev}:\Program Files (x86)')
            if os.path.exists(f'{dev}:\\')
        ]
    else:  # Linux / macOS / 其他 Unix-like
        default_paths = [
            '/usr/lib/jvm',
            '/usr/java',
            '/Library/Java/JavaVirtualMachines',  # macOS 专用
            '/opt/jdk',  # 一些自定义安装
            '/opt/java',
        ]

    for root in default_paths:
        if not os.path.isdir(root):
            continue
        try:
            async for path, type_, major in search_java(root, max_depth=3):
                yield path, type_, major
        except (PermissionError, OSError):
            # 无权限或目录不可读则跳过
            continue


def get_simple_type(type):
    type = str(type)
    if 'jdk' in type:
        return 'JDK'
    elif 'jre' in type:
        return 'JRE'
    else:
        return type


if __name__ == '__main__':

    async def main():
        import sys
        path = sys.argv[1]

        print(await detect_java_version(path))


    asyncio.run(main())
