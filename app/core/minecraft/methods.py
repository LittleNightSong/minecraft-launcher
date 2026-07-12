from app.core.minecraft.mc_version_lang import VersionExpr


def generate_instance_name(version_expr: VersionExpr):
    if version_expr.name:
        return version_expr.name
    else:
        base_name = version_expr.full_version.version

