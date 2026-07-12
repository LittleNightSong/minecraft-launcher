from app.core.minecraft.launch_context import LaunchContext


def generate_features(launch_context: LaunchContext):
    lc = launch_context
    f = {}

    # 自定义分辨率
    if lc.width is not None and lc.height is not None:
        f['has_custom_resolution'] = True

    # 快速启动支持（路径存在即表示支持）
    if lc.quick_play_path is not None:
        f['has_quick_plays_support'] = True

    # 具体快速启动类型
    if lc.quick_play_single_player is not None:
        f['is_quick_play_singleplayer'] = True

    if lc.quick_play_multi_player is not None:
        f['is_quick_play_multiplayer'] = True

    if lc.quick_play_realms is not None:
        f['is_quick_play_realms'] = True

    # is_demo_user 默认不设置，视为 False
    return f