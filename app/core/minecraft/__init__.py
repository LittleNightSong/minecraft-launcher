"""
Minecraft 核心模块。

导出 Minecraft 版本管理相关的核心模型和工具类。
"""

from .api import MinecraftAPI
from .mvl import parse as parse_mvl, VersionExpr as MVLParseResult
from .minecraft_version import MinecraftVersion
from .model_asset_index import AssetIndexModel
from .model_version_manifest import VersionManifestModel
from .model_version_meta import VersionMetaModel
from .features import generate_features
from .matcher import rules_matcher
from .resources import *
