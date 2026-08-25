"""
Minecraft 核心模块。

导出 Minecraft 版本管理相关的核心模型和工具类。
"""

from .mvl import parse as parse_mvl, VersionExpr as MVLParseResult
from .features import generate_features
from .version import MinecraftVersion
from .matcher import match,match_one
from .directories import *
