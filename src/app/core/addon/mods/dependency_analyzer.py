# Written By DeepSeek
# Editten By LittleNightSong

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from app.core.models.mod import ModMeta, Dependency
from app.core.models.version_range import VersionRange, Version, merge_two, parse as parse_range, merge


type ModID = str

@dataclass
class ConflictReport:
    kind: str  # "constraint_conflict", "version_conflict", "version_mismatch"
    dependency_id: str
    involved_mods: List[ModMeta]
    detail: str
    # 扩展字段
    conflicting_ranges: Optional[List[Tuple[VersionRange, ModMeta]]] = None
    bad_version: Optional[Version] = None
    required_range: Optional[VersionRange] = None


@dataclass()
class AnalyzeState:
    constraints: dict[ModID, tuple[VersionRange, list[VersionRange]]]
    selected_mods: dict[ModID, ModMeta]

class Analyzer:
    def __init__(self):
        self.selected_mods: Dict[str, ModMeta] = {}
        self.global_constraints: Dict[str, VersionRange] = {}
        self.constraint_origins: Dict[str, List[Tuple[VersionRange, ModMeta]]] = defaultdict(list)

        # 冲突暂存
        self._last_conflict: Optional[ConflictReport] = None

    def add_mod(self, mod: ModMeta) -> bool:
        """尝试添加一个模组（包括它的版本本身），若成功返回 True，否则 False"""
        # 保存状态以备回滚
        old_selected = dict(self.selected_mods)
        old_constraints = dict(self.global_constraints)
        old_origins = {k: list(v) for k, v in self.constraint_origins.items()}

        try:
            # 1. 检查该模组本身的版本是否满足全局约束（如果该 ID 已被约束）
            if mod.id in self.global_constraints:
                required = self.global_constraints[mod.id]
                if not required.filter([mod.version]):
                    self._set_conflict_version_mismatch(mod.id, mod.version, required)
                    return False

            # 2. 检查同 ID 是否已选不同版本
            if mod.id in self.selected_mods:
                existing = self.selected_mods[mod.id]
                if existing.version != mod.version:
                    self._set_conflict_version_conflict(mod, existing)
                    return False

            # 3. 处理该模组的所有依赖（合并到全局约束）
            for dep in mod.dependencies:
                dep_range = parse_range(dep.version_range)
                if isinstance(dep_range, VersionRange):
                    dep_range = dep_range
                else:
                    # 如果是 Ranges，取所有范围的交集（AND 关系）
                    dep_range = merge(dep_range.ranges)

                if dep.id in self.global_constraints:
                    old_range = self.global_constraints[dep.id]
                    new_range = merge_two(old_range, dep_range)
                    if new_range is None:
                        self._set_conflict_constraint(dep.id, old_range, dep_range,
                                                       self.constraint_origins[dep.id], mod)
                        return False
                    self.global_constraints[dep.id] = new_range
                else:
                    self.global_constraints[dep.id] = dep_range
                self.constraint_origins[dep.id].append((dep_range, mod))

            # 4. 正式将该模组加入已选列表（在合并依赖后，但尚未验证所有已选模组）
            self.selected_mods[mod.id] = mod

            # 5. 验证所有已选模组的版本是否满足更新后的全局约束
            validation_error = self._validate_all_selected()
            if validation_error:
                self._last_conflict = validation_error
                return False

            # 成功，清除上次冲突记录
            self._last_conflict = None
            return True

        except Exception:
            # 发生异常回滚并重新抛出
            self._rollback(old_selected, old_constraints, old_origins)
            raise

        # 如果中途失败（如冲突），我们已经在内部回滚了，所以这里不会执行

    def _validate_all_selected(self) -> Optional[ConflictReport]:
        """检查所有已选模组的版本是否满足全局约束"""
        for mod_id, mod in self.selected_mods.items():
            if mod_id in self.global_constraints:
                required = self.global_constraints[mod_id]
                if not required.filter([mod.version]):
                    # 找出提出最严格约束的模组（导致该版本不满足）
                    origins = self.constraint_origins.get(mod_id, [])
                    bad_origins = [m for rng, m in origins if not rng.filter([mod.version])]
                    return ConflictReport(
                        kind="version_mismatch",
                        dependency_id=mod_id,
                        involved_mods=bad_origins + [mod],
                        bad_version=mod.version,
                        required_range=required,
                        detail=f"模组 '{mod.display_name}' 的版本 {mod.version} 不满足全局约束 {required}。"
                               f"提出较严格要求的模组：{', '.join(m.display_name for m in bad_origins)}。"
                    )
        return None

    def _set_conflict_constraint(self, dep_id: str, old_range: VersionRange,
                                 new_range: VersionRange,
                                 old_origins: List[Tuple[VersionRange, ModMeta]],
                                 new_mod: ModMeta):
        """设置约束冲突报告，并回滚状态（由调用者负责回滚）"""
        conflicting_old = [m for rng, m in old_origins if merge_two(rng, new_range) is None]
        self._last_conflict = ConflictReport(
            kind="constraint_conflict",
            dependency_id=dep_id,
            involved_mods=conflicting_old + [new_mod],
            detail=f"依赖 '{dep_id}' 的版本约束冲突：已有约束 {old_range} 与新增约束 {new_range} 不兼容。"
        )
        # 注意：回滚由调用者做

    def _set_conflict_version_conflict(self, new_mod: ModMeta, existing_mod: ModMeta):
        self._last_conflict = ConflictReport(
            kind="version_conflict",
            dependency_id=new_mod.id,
            involved_mods=[existing_mod, new_mod],
            detail=f"模组 '{new_mod.id}' 已选版本 {existing_mod.version}，"
                   f"尝试添加版本 {new_mod.version}，但同一模组只能安装一个版本。"
        )

    def _set_conflict_version_mismatch(self, dep_id: str, version: Version, required: VersionRange):
        self._last_conflict = ConflictReport(
            kind="version_mismatch",
            dependency_id=dep_id,
            involved_mods=[],  # 后续可补充来源
            bad_version=version,
            required_range=required,
            detail=f"模组 '{dep_id}' 的版本 {version} 不满足当前约束 {required}。"
        )

    def _rollback(self, old_selected, old_constraints, old_origins):
        self.selected_mods = old_selected
        self.global_constraints = old_constraints
        self.constraint_origins = old_origins

    def get_last_conflict_report(self) -> Optional[ConflictReport]:
        return self._last_conflict

    def suggest_fix(self, report: ConflictReport) -> List[str]:
        """生成修复建议（简化版）"""
        suggestions = []
        if report.kind == "constraint_conflict":
            mods = report.involved_mods
            if len(mods) >= 2:
                suggestions.append(f"考虑升级/降级 {mods[0].display_name} 或 {mods[1].display_name}，"
                                   f"使它们对 '{report.dependency_id}' 的要求兼容。")
                suggestions.append(f"或者移除其中一个：{mods[0].display_name} 或 {mods[1].display_name}。")
        elif report.kind == "version_conflict":
            mods = report.involved_mods
            suggestions.append(f"只能选择一个版本的模组 '{report.dependency_id}'，"
                               f"已选 {mods[0].version}，冲突版本 {mods[1].version}。")
            suggestions.append("请移除一个或调整版本。")
        elif report.kind == "version_mismatch":
            suggestions.append(f"当前版本 {report.bad_version} 不满足要求 {report.required_range}。")
            suggestions.append(f"请将 '{report.dependency_id}' 升级到符合要求的版本。")
            if report.involved_mods:
                strict_mods = [m for m in report.involved_mods if m.id != report.dependency_id]
                if strict_mods:
                    suggestions.append(f"尤其是 {', '.join(m.display_name for m in strict_mods)} 提出了严格要求。")
        return suggestions


# ========== 测试 ==========
if __name__ == "__main__":

    # 构建测试模组
    mod_a = ModMeta(
        id="A", version="1.0.0", display_name="Mod A", description="",
        icon="", urls={}, environment="all",
        dependencies=[Dependency(id="C", version_range=">=1.0", environment="all")],
        breaks=[]
    )
    mod_b = ModMeta(
        id="B", version="1.0.0", display_name="Mod B", description="",
        icon="", urls={}, environment="all",
        dependencies=[Dependency(id="C", version_range=">=2.0", environment="all")],
        breaks=[]
    )
    mod_c_1_5 = ModMeta(
        id="C", version="1.5.0", display_name="Mod C v1.5", description="",
        icon="", urls={}, environment="all",
        dependencies=[],
        breaks=[]
    )
    mod_c_2_0 = ModMeta(
        id="C", version="2.0.0", display_name="Mod C v2.0", description="",
        icon="", urls={}, environment="all",
        dependencies=[
            Dependency(id='D', version_range='>1', environment='all')
        ],
        breaks=[]
    )
    mod_d = ModMeta(
        id="D", version='11.45.14', display_name="Mod D", description="",
        urls={},
        dependencies=[
            Dependency(id='C', version_range='>1', environment='all')  # 构建循环依赖
        ],
        breaks=[]
    )

    analyzer = Analyzer()

    print("=== 场景：先添加 C 1.5，再添加 A（可以），再添加 B（冲突）===")
    print("添加 C 1.5:", analyzer.add_mod(mod_c_1_5))
    print("添加 A:", analyzer.add_mod(mod_a))
    print("添加 B:", analyzer.add_mod(mod_b))
    report = analyzer.get_last_conflict_report()
    if report:
        print("冲突报告:", report.detail)
        print("建议:", analyzer.suggest_fix(report))
    else:
        print("无冲突")
    print("全局约束:", analyzer.global_constraints)
    print("已选模组:", {k: v.version for k, v in analyzer.selected_mods.items()})

    # 重置
    print("\n=== 场景：先添加 C 2.0，再添加 A，再添加 B（全部通过）===")
    analyzer2 = Analyzer()
    analyzer2.add_mod(mod_c_2_0)
    analyzer2.add_mod(mod_a)
    print("添加 B:", analyzer2.add_mod(mod_b))
    report2 = analyzer2.get_last_conflict_report()
    if report2:
        print("冲突报告:", report2.detail)
    else:
        print("无冲突")
    print("全局约束:", analyzer2.global_constraints)

    # 重置
    print("\n=== 场景：先添加 C 2.0，再添加 A、D、 B（全部通过）===")
    analyzer3 = Analyzer()
    analyzer3.add_mod(mod_c_2_0)
    analyzer3.add_mod(mod_a)
    analyzer3.add_mod(mod_d)
    print("添加 B:", analyzer3.add_mod(mod_b))
    report2 = analyzer3.get_last_conflict_report()
    if report2:
        print("冲突报告:", report2.detail)
    else:
        print("无冲突")
    print("全局约束:", analyzer3.global_constraints)