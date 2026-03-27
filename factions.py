from dataclasses import dataclass

from ursina import color


@dataclass(frozen=True)
class FactionTheme:
    key: str
    name: str
    command_label: str
    primary: object
    secondary: object
    accent: object
    metal: object
    panel: object
    glow: object
    selection: object


FACTIONS = {
    "alliance": FactionTheme(
        key="alliance",
        name="Alliance",
        command_label="Alliance Command",
        primary=color.rgb32(83, 126, 181),
        secondary=color.rgb32(182, 199, 219),
        accent=color.rgb32(228, 196, 116),
        metal=color.rgb32(67, 82, 100),
        panel=color.rgb32(36, 54, 77),
        glow=color.rgb32(117, 226, 240),
        selection=color.rgb32(112, 217, 237),
    ),
    "soviet": FactionTheme(
        key="soviet",
        name="Soviet",
        command_label="Soviet Warfront",
        primary=color.rgb32(163, 66, 59),
        secondary=color.rgb32(133, 84, 72),
        accent=color.rgb32(236, 188, 88),
        metal=color.rgb32(73, 67, 71),
        panel=color.rgb32(98, 41, 37),
        glow=color.rgb32(239, 137, 86),
        selection=color.rgb32(241, 148, 112),
    ),
}

PLAYER_FACTION_KEY = "alliance"
ENEMY_FACTION_KEY = "soviet"


def get_faction_theme(key: str) -> FactionTheme:
    if key not in FACTIONS:
        raise KeyError(f"Unknown faction: {key}")
    return FACTIONS[key]


def get_opposing_faction_key(key: str) -> str:
    for candidate in FACTIONS:
        if candidate != key:
            return candidate
    raise KeyError(f"No opposing faction configured for: {key}")
