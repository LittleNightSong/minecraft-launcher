# __init__.py
"""
Minecraft 核心模块。

提供 Minecraft 启动所需的数据模型和工具类，包括：
- 文件信息管理 (FileInfo, ValidateResult)
- 库文件管理 (Library)
- 启动上下文 (LaunchContext, BasicJVMContext)
- 版本元数据 (VersionMeta)
- 服务器元数据 (ServerMeta)
- 实例管理 (InstanceMeta)
- 环境检测 (Environment)
"""

from .file import *
from .maven_coordinate import MavenCoordinate
from .maven_coordinate import MavenCoordinate as Library