from constants.gamemodes import GameMode


def cm_dm(mode, mods):
    gamemode = GameMode.vn_std
    if mode == "std" and mods == "rx":
        gamemode = GameMode.rx_std
    elif mode == "std" and mods == "ap":
        gamemode = GameMode.ap_std
    elif mode == "mania" and mods == "vn":
        gamemode = GameMode.vn_mania
    elif mode == "taiko" and mods == "vn":
        gamemode = GameMode.vn_taiko
    elif mode == "taiko" and mods == "rx":
        gamemode = GameMode.rx_taiko
    return gamemode
