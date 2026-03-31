from ursina import color

from entities import (
    Airfield,
    Barracks,
    ConstructionVehicle,
    Dog,
    GemField,
    GoldField,
    Harvester,
    MachineGunBunker,
    MainBase,
    PowerPlant,
    Radar,
    Refinery,
    Soldier,
    Tank,
    TankFactory,
)

WINDOW_TITLE = "RTS RA3 Prototype"
GROUND_SIZE = 132
GROUND_EDGE_LIMIT = (GROUND_SIZE / 2) - 1.5
GROUND_TEXTURE_SCALE = 22
GROUND_BACKDROP_SIZE = 320
GROUND_BACKDROP_TEXTURE_SCALE = 40
CAMERA_START_POSITION = (0, 50, -46)
CAMERA_START_ROTATION_X = 58
CAMERA_FOV = 70
CAMERA_MOVE_SPEED = 32
CAMERA_ZOOM_STEP = 3
CAMERA_MIN_Y = 28
CAMERA_MAX_Y = 86
FORMATION_SPACING = 3.2
MOVE_TARGET_SEARCH_STEP = 1.6
MOVE_TARGET_SEARCH_RINGS = 4
STARTING_CREDITS = 1200
BUILD_CLEARANCE = 1.25

PLAYABLE_GROUND_COLOR = color.rgb32(78, 122, 83)
BACKDROP_GROUND_COLOR = color.rgb32(58, 92, 63)
TERRAIN_PATCHES = [
    ((-38, 0.02, 26), (30, 24), color.rgb32(92, 132, 79)),
    ((34, 0.025, 28), (34, 26), color.rgb32(101, 126, 78)),
    ((8, 0.02, -30), (40, 24), color.rgb32(86, 111, 73)),
    ((-42, 0.03, -36), (24, 22), color.rgb32(100, 118, 72)),
    ((44, 0.022, -18), (22, 18), color.rgb32(96, 124, 76)),
    ((-8, 0.02, 40), (28, 18), color.rgb32(106, 136, 88)),
]
ROAD_PATCHES = [
    ((0, 0.04, 4), (10, 110), color.rgba32(103, 102, 91, 150)),
    ((-16, 0.04, -6), (42, 8), color.rgba32(126, 113, 88, 135)),
    ((18, 0.04, 18), (36, 8), color.rgba32(116, 107, 84, 125)),
]

SIDEBAR_TABS = (
    ("structures", "Buildings"),
    ("defenses", "Defense"),
    ("barracks", "Barracks"),
    ("factory", "Factory"),
)
BUILDING_DEFINITIONS = {
    "power_plant": {
        "label": PowerPlant.display_name,
        "class": PowerPlant,
        "cost": PowerPlant.cost,
        "menu_tab": "structures",
        "requires": ("main_base",),
        "build_time": 6.0,
        "icon_text": "PP",
    },
    "refinery": {
        "label": Refinery.display_name,
        "class": Refinery,
        "cost": Refinery.cost,
        "menu_tab": "structures",
        "requires": ("power_plant",),
        "build_time": 8.0,
        "icon_text": "RF",
    },
    "barracks": {
        "label": Barracks.display_name,
        "class": Barracks,
        "cost": Barracks.cost,
        "menu_tab": "structures",
        "requires": ("power_plant",),
        "build_time": 7.0,
        "icon_text": "BR",
    },
    "radar": {
        "label": Radar.display_name,
        "class": Radar,
        "cost": Radar.cost,
        "menu_tab": "structures",
        "requires": ("barracks",),
        "build_time": 9.0,
        "icon_text": "RD",
        "factions": ("soviet",),
    },
    "airfield": {
        "label": Airfield.display_name,
        "class": Airfield,
        "cost": Airfield.cost,
        "menu_tab": "structures",
        "requires": ("barracks",),
        "build_time": 9.0,
        "icon_text": "AF",
        "factions": ("alliance",),
    },
    "tank_factory": {
        "label": TankFactory.display_name,
        "class": TankFactory,
        "cost": TankFactory.cost,
        "menu_tab": "structures",
        "requires": ("barracks",),
        "build_time": 11.0,
        "icon_text": "WF",
    },
    "pillbox": {
        "label": MachineGunBunker.display_name,
        "class": MachineGunBunker,
        "cost": MachineGunBunker.cost,
        "menu_tab": "defenses",
        "requires": ("barracks",),
        "build_time": 5.0,
        "icon_text": "MG",
    },
}

UNIT_DEFINITIONS = {
    "mcv": {
        "label": ConstructionVehicle.display_name,
        "class": ConstructionVehicle,
        "cost": ConstructionVehicle.cost,
        "build_time": 14.0,
        "menu_tab": "factory",
        "show_in_menu": False,
        "icon_text": "MC",
    },
    "soldier": {
        "label": Soldier.display_name,
        "class": Soldier,
        "cost": Soldier.cost,
        "build_time": 4.0,
        "menu_tab": "barracks",
        "icon_text": "GI",
    },
    "dog": {
        "label": Dog.display_name,
        "class": Dog,
        "cost": Dog.cost,
        "build_time": 5.0,
        "menu_tab": "barracks",
        "icon_text": "K9",
    },
    "harvester": {
        "label": Harvester.display_name,
        "class": Harvester,
        "cost": Harvester.cost,
        "build_time": 10.0,
        "menu_tab": "factory",
        "icon_text": "HV",
    },
    "tank": {
        "label": Tank.display_name,
        "class": Tank,
        "cost": Tank.cost,
        "build_time": 11.0,
        "menu_tab": "factory",
        "icon_text": "TN",
    },
}

BUILDING_TRAINING = {
    Refinery: ("harvester",),
    Barracks: ("soldier", "dog"),
    TankFactory: ("tank",),
}

PLAYER_STARTING_BUILDINGS = [
]

ENEMY_STARTING_BUILDINGS = [
]

PLAYER_STARTING_UNITS = [
    ("mcv", (-38, 0.5, -24)),
]

ENEMY_STARTING_UNITS = [
    ("mcv", (38, 0.5, 24)),
]

RESOURCE_FIELDS = [
    ("gold", (-12, 0.09, 16), 1600),
    ("gold", (15, 0.09, -14), 1600),
    ("gold", (3, 0.09, 4), 1300),
    ("gems", (9, 0.09, 18), 950),
    ("gems", (-7, 0.09, -8), 950),
    ("gems", (0, 0.09, -22), 900),
]

RESOURCE_FIELD_CLASSES = {
    "gold": GoldField,
    "gems": GemField,
}

DEFAULT_STATUS = "Select the MCV and press F to deploy Main Base. Build branches unlock from the base, and ready structures must be placed on the ground."
