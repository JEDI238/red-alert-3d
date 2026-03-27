from collections import defaultdict
from heapq import heappop, heappush
from math import ceil, sqrt

from ursina import Entity, Vec2, Vec3, camera, color, destroy, distance, held_keys, mouse, time, window
from factions import FACTIONS, get_opposing_faction_key
from entities import MainBase

from .config import (
    BACKDROP_GROUND_COLOR,
    BUILD_CLEARANCE,
    BUILDING_DEFINITIONS,
    BUILDING_TRAINING,
    CAMERA_FOV,
    CAMERA_MAX_Y,
    CAMERA_MIN_Y,
    CAMERA_MOVE_SPEED,
    CAMERA_START_POSITION,
    CAMERA_START_ROTATION_X,
    CAMERA_ZOOM_STEP,
    DEFAULT_STATUS,
    ENEMY_STARTING_BUILDINGS,
    ENEMY_STARTING_UNITS,
    FORMATION_SPACING,
    GROUND_EDGE_LIMIT,
    GROUND_BACKDROP_SIZE,
    GROUND_BACKDROP_TEXTURE_SCALE,
    GROUND_SIZE,
    GROUND_TEXTURE_SCALE,
    MOVE_TARGET_SEARCH_RINGS,
    MOVE_TARGET_SEARCH_STEP,
    PLAYER_STARTING_BUILDINGS,
    PLAYER_STARTING_UNITS,
    PLAYABLE_GROUND_COLOR,
    RESOURCE_FIELD_CLASSES,
    RESOURCE_FIELDS,
    ROAD_PATCHES,
    TERRAIN_PATCHES,
    UNIT_DEFINITIONS,
    WINDOW_TITLE,
)
from .state import GameState
from .ui import MainMenuUI, SidebarUI


class RTSGame(Entity):
    def __init__(self):
        super().__init__()
        window.title = WINDOW_TITLE
        window.color = color.rgb32(32, 41, 54)

        self.state = GameState()
        self.player_faction = FACTIONS[self.state.player_faction_key]
        self.enemy_faction = FACTIONS[self.state.enemy_faction_key]
        self.units = []
        self.buildings = []
        self.resource_fields = []
        self.spawn_counts = defaultdict(int)
        self.battle_result = None

        self.ground = None
        self.backdrop_ground = None
        self.terrain_tiles = []
        self.selection_drag_origin = None
        self.selection_drag_additive = False
        self.selection_drag_threshold = 0.025
        self.preview_entity = Entity(
            model="cube",
            color=color.rgba32(
                self.player_faction.selection.r * 255,
                self.player_faction.selection.g * 255,
                self.player_faction.selection.b * 255,
                110,
            ),
            enabled=False,
            collider=None,
        )
        self.selection_box = Entity(
            parent=camera.ui,
            model="quad",
            color=color.rgba32(130, 193, 235, 38),
            enabled=False,
            collider=None,
            z=-0.01,
        )
        self.selection_box_border_top = Entity(
            parent=self.selection_box,
            model="quad",
            scale=(1, 0.06),
            y=0.5,
            color=color.rgba32(170, 224, 255, 180),
            collider=None,
        )
        self.selection_box_border_bottom = Entity(
            parent=self.selection_box,
            model="quad",
            scale=(1, 0.06),
            y=-0.5,
            color=color.rgba32(170, 224, 255, 180),
            collider=None,
        )
        self.selection_box_border_left = Entity(
            parent=self.selection_box,
            model="quad",
            scale=(0.06, 1),
            x=-0.5,
            color=color.rgba32(170, 224, 255, 180),
            collider=None,
        )
        self.selection_box_border_right = Entity(
            parent=self.selection_box,
            model="quad",
            scale=(0.06, 1),
            x=0.5,
            color=color.rgba32(170, 224, 255, 180),
            collider=None,
        )

        self._create_world()

        self.sidebar = SidebarUI(
            self.queue_building_purchase,
            self.train_unit,
            self.cancel_build_mode,
            command_title=self.player_faction.command_label,
        )
        self.main_menu = MainMenuUI(
            self.start_game,
            self.set_player_faction,
            selected_faction_key=self.state.player_faction_key,
            subtitle=self._menu_subtitle(),
        )
        self._apply_faction_ui()
        self._refresh_ui()

    def start_game(self):
        self.state = GameState(
            player_faction_key=self.state.player_faction_key,
            enemy_faction_key=self.state.enemy_faction_key,
        )
        self.player_faction = FACTIONS[self.state.player_faction_key]
        self.enemy_faction = FACTIONS[self.state.enemy_faction_key]
        self.battle_result = None
        self._apply_faction_ui()
        self._reset_battlefield()
        self.state.game_started = True
        self.state.status_message = f"{self.player_faction.name} MCV deployed. Select it and press F to unfold your Main Base."
        self.main_menu.hide()
        self.sidebar.show()
        self._refresh_ui()

    def set_player_faction(self, faction_key):
        self.state.player_faction_key = faction_key
        self.state.enemy_faction_key = get_opposing_faction_key(faction_key)
        self.player_faction = FACTIONS[self.state.player_faction_key]
        self.enemy_faction = FACTIONS[self.state.enemy_faction_key]
        self._apply_faction_ui()

    def update(self):
        if not self.state.game_started:
            return

        self._move_camera()
        self._update_selection_drag_visual()
        self._update_construction_queue()
        self._update_build_preview()
        self._cleanup_destroyed_entities()
        self._update_battle_result()

    def input(self, key):
        if key == "scroll up":
            self._zoom_camera(-CAMERA_ZOOM_STEP)
            return

        if key == "scroll down":
            self._zoom_camera(CAMERA_ZOOM_STEP)
            return

        if not self.state.game_started:
            return

        if key == "left mouse up" and self.selection_drag_origin is not None:
            self._finish_selection_drag()
            return

        if key == "escape":
            self._clear_selection_drag()
            if self.state.pending_building_key:
                self.cancel_build_mode()
            else:
                self.clear_selection()
                self.state.status_message = "Selection cleared."
                self._refresh_ui()
            return

        if key in ("f", "enter"):
            if self._deploy_selected_mcv():
                return

        if key == "left mouse down":
            if self._hovering_ui():
                return
            if self.state.pending_building_key:
                self._place_pending_building()
                return
            self._begin_selection_drag()
        elif key == "right mouse down":
            if self._hovering_ui():
                return
            self._clear_selection_drag()
            self._handle_right_click()

    def queue_building_purchase(self, building_key):
        definition = BUILDING_DEFINITIONS[building_key]
        if self.state.pending_building_key:
            if self.state.pending_building_key == building_key:
                self.state.status_message = f"{definition['label']} is already ready for placement."
            else:
                ready_definition = BUILDING_DEFINITIONS[self.state.pending_building_key]
                self.state.status_message = f"Place the ready {ready_definition['label']} first."
            self._refresh_ui()
            return

        if self.state.ready_building_key:
            if self.state.ready_building_key != building_key:
                ready_definition = BUILDING_DEFINITIONS[self.state.ready_building_key]
                self.state.status_message = f"Place the ready {ready_definition['label']} first."
                self._refresh_ui()
                return
            self.clear_selection()
            self.state.pending_building_key = building_key
            self.state.status_message = f"Placement mode: click ground to deploy {definition['label']}."
            self._refresh_ui()
            return

        if self.state.construction_building_key:
            active_definition = BUILDING_DEFINITIONS[self.state.construction_building_key]
            self.state.status_message = f"Construction queue busy with {active_definition['label']}."
            self._refresh_ui()
            return

        locked_reason = self._locked_building_reason(building_key)
        if locked_reason:
            self.state.status_message = locked_reason
            self._refresh_ui()
            return

        if self.state.credits < definition["cost"]:
            self.state.status_message = f"Not enough credits for {definition['label']}."
            self._refresh_ui()
            return

        self.state.credits -= definition["cost"]
        self.state.construction_building_key = building_key
        self.state.construction_total_time = definition.get("build_time", 0.0)
        self.state.construction_time_left = self.state.construction_total_time
        self.state.status_message = f"Construction started: {definition['label']}."
        self._refresh_ui()

    def cancel_build_mode(self):
        if self.state.pending_building_key is not None:
            definition = BUILDING_DEFINITIONS[self.state.pending_building_key]
            self.state.pending_building_key = None
            self.state.status_message = f"{definition['label']} is ready and waiting for placement."
        elif self.state.construction_building_key is not None:
            building_key = self.state.construction_building_key
            definition = BUILDING_DEFINITIONS[building_key]
            self.state.credits += definition["cost"]
            self.state.construction_building_key = None
            self.state.construction_time_left = 0.0
            self.state.construction_total_time = 0.0
            self.state.status_message = f"Construction cancelled: {definition['label']}."
        elif self.state.ready_building_key is None:
            self.state.status_message = DEFAULT_STATUS
        else:
            definition = BUILDING_DEFINITIONS[self.state.ready_building_key]
            self.state.status_message = f"{definition['label']} is ready and waiting for placement."
        self.preview_entity.enabled = False
        self._refresh_ui()

    def train_unit(self, unit_key):
        available_units = self._available_units_for_selection()
        if unit_key not in available_units:
            self.state.status_message = "Select a production building to train units."
            self._refresh_ui()
            return

        definition = UNIT_DEFINITIONS[unit_key]
        if self.state.credits < definition["cost"]:
            self.state.status_message = f"Not enough credits for {definition['label']}."
            self._refresh_ui()
            return

        spawn_position = self._find_spawn_position(
            self.state.selected_building,
            unit_radius=getattr(definition["class"], "footprint_radius", 1.2),
        )
        unit = self._spawn_unit(
            unit_key,
            spawn_position,
            faction_key=self.state.player_faction_key,
            owner="player",
        )
        self.state.credits -= definition["cost"]
        self.state.status_message = f"{unit.display_name} deployed."
        self._refresh_ui()

    def clear_selection(self):
        for unit in self.state.selected_units:
            unit.deselect()
        self.state.selected_units = []

        if self.state.selected_building:
            self.state.selected_building.deselect()
            self.state.selected_building = None

    def _owned_building_keys(self, owner):
        return {
            getattr(building, "building_key", None)
            for building in self.buildings
            if getattr(building, "owner", None) == owner and not getattr(building, "is_destroyed", False)
        }

    @staticmethod
    def _building_class_for_key(building_key):
        if building_key == "main_base":
            return MainBase
        return BUILDING_DEFINITIONS[building_key]["class"]

    @staticmethod
    def _building_label_for_key(building_key):
        if building_key == "main_base":
            return MainBase.display_name
        return BUILDING_DEFINITIONS[building_key]["label"]

    def _missing_build_requirements(self, building_key, owner="player"):
        definition = BUILDING_DEFINITIONS[building_key]
        owned_keys = self._owned_building_keys(owner)
        return tuple(requirement for requirement in definition.get("requires", ()) if requirement not in owned_keys)

    def _locked_building_reason(self, building_key, owner="player"):
        missing_requirements = self._missing_build_requirements(building_key, owner=owner)
        if not missing_requirements:
            return ""

        missing_labels = []
        for requirement in missing_requirements:
            missing_labels.append(self._building_label_for_key(requirement))
        definition = BUILDING_DEFINITIONS[building_key]
        return f"{definition['label']} requires {', '.join(missing_labels)}."

    def _update_construction_queue(self):
        if not self.state.construction_building_key:
            return

        self.state.construction_time_left = max(0.0, self.state.construction_time_left - time.dt)
        if self.state.construction_time_left > 0:
            return

        self.state.ready_building_key = self.state.construction_building_key
        self.state.pending_building_key = self.state.construction_building_key
        self.state.construction_building_key = None
        self.state.construction_time_left = 0.0
        self.state.construction_total_time = 0.0
        definition = BUILDING_DEFINITIONS[self.state.ready_building_key]
        self.state.status_message = f"{definition['label']} is ready. Click the ground to place it."
        self._refresh_ui()

    def _construction_label(self):
        if self.state.pending_building_key:
            label = BUILDING_DEFINITIONS[self.state.pending_building_key]["label"]
            return f"{label} ready to place"
        if self.state.ready_building_key:
            label = BUILDING_DEFINITIONS[self.state.ready_building_key]["label"]
            return f"{label} ready"
        if self.state.construction_building_key:
            label = BUILDING_DEFINITIONS[self.state.construction_building_key]["label"]
            return f"{label} {self.state.construction_time_left:.1f}s"
        return "idle"

    def _construction_progress(self):
        if self.state.pending_building_key or self.state.ready_building_key:
            return 1.0
        if not self.state.construction_building_key or self.state.construction_total_time <= 0:
            return 0.0
        return 1.0 - (self.state.construction_time_left / self.state.construction_total_time)

    def _building_button_states(self):
        states = {}
        active_key = self.state.construction_building_key
        ready_key = self.state.ready_building_key
        pending_key = self.state.pending_building_key

        for key, definition in BUILDING_DEFINITIONS.items():
            base_text = f"{definition['label']} (${definition['cost']})"
            if active_key == key:
                progress = int(self._construction_progress() * 100)
                states[key] = {
                    "text": f"{definition['label']} {progress}%",
                    "enabled": False,
                    "selected": True,
                }
                continue

            if ready_key == key:
                states[key] = {
                    "text": f"{definition['label']} READY",
                    "enabled": True,
                    "selected": True,
                }
                continue

            locked_reason = self._locked_building_reason(key)
            enabled = (
                not locked_reason
                and self.state.credits >= definition["cost"]
                and pending_key is None
                and active_key is None
                and ready_key is None
            )
            states[key] = {
                "text": base_text,
                "enabled": enabled,
                "selected": False,
            }
        return states

    def _apply_faction_ui(self):
        if hasattr(self, "sidebar"):
            self.sidebar.set_command_title(self.player_faction.command_label)
        if hasattr(self, "main_menu"):
            self.main_menu.set_selected_faction(self.state.player_faction_key)
            self.main_menu.set_subtitle(self._menu_subtitle())
        self.preview_entity.color = color.rgba32(
            self.player_faction.selection.r * 255,
            self.player_faction.selection.g * 255,
            self.player_faction.selection.b * 255,
            110,
        )

    def _menu_subtitle(self):
        return (
            f"Deploy as {self.player_faction.name}. Start with an MCV, unfold the Main Base, "
            f"then branch into power, refinery, barracks, and armor tech."
        )

    def _create_world(self):
        self.backdrop_ground = Entity(
            model="plane",
            scale=(GROUND_BACKDROP_SIZE, 1, GROUND_BACKDROP_SIZE),
            texture="white_cube",
            texture_scale=(GROUND_BACKDROP_TEXTURE_SCALE, GROUND_BACKDROP_TEXTURE_SCALE),
            color=BACKDROP_GROUND_COLOR,
            y=-0.35,
            collider=None,
        )
        self.ground = Entity(
            model="plane",
            scale=(GROUND_SIZE, 1, GROUND_SIZE),
            texture="white_cube",
            texture_scale=(GROUND_TEXTURE_SCALE, GROUND_TEXTURE_SCALE),
            color=PLAYABLE_GROUND_COLOR,
            collider="box",
        )
        self._create_terrain_patches()
        camera.position = CAMERA_START_POSITION
        camera.rotation_x = CAMERA_START_ROTATION_X
        camera.fov = CAMERA_FOV

    def _create_terrain_patches(self):
        self.terrain_tiles = []

        for position, scale, tint in TERRAIN_PATCHES:
            self.terrain_tiles.append(
                Entity(
                    model="plane",
                    position=position,
                    scale=(scale[0], 1, scale[1]),
                    color=tint,
                    collider=None,
                )
            )

        for position, scale, tint in ROAD_PATCHES:
            self.terrain_tiles.append(
                Entity(
                    model="plane",
                    position=position,
                    scale=(scale[0], 1, scale[1]),
                    color=tint,
                    collider=None,
                )
            )

    def _reset_battlefield(self):
        self.preview_entity.enabled = False
        self._clear_selection_drag()
        self.clear_selection()
        for unit in tuple(self.units):
            destroy(unit)
        for building in tuple(self.buildings):
            destroy(building)
        for field in tuple(self.resource_fields):
            destroy(field)
        self.units = []
        self.buildings = []
        self.resource_fields = []
        self.spawn_counts.clear()
        self._spawn_initial_entities()

    def _spawn_initial_entities(self):
        for resource_kind, position, amount in RESOURCE_FIELDS:
            self._spawn_resource_field(resource_kind, Vec3(*position), amount)

        for building_key, position in PLAYER_STARTING_BUILDINGS:
            self._spawn_building(
                building_key,
                Vec3(*position),
                faction_key=self.state.player_faction_key,
                owner="player",
            )

        for building_key, position in ENEMY_STARTING_BUILDINGS:
            self._spawn_building(
                building_key,
                Vec3(*position),
                faction_key=self.state.enemy_faction_key,
                owner="enemy",
            )

        for unit_key, position in PLAYER_STARTING_UNITS:
            self._spawn_unit(
                unit_key,
                Vec3(*position),
                faction_key=self.state.player_faction_key,
                owner="player",
            )

        for unit_key, position in ENEMY_STARTING_UNITS:
            unit = self._spawn_unit(
                unit_key,
                Vec3(*position),
                faction_key=self.state.enemy_faction_key,
                owner="enemy",
            )
            if getattr(unit, "deploy_building_key", None):
                self._deploy_construction_vehicle(unit, auto=True)

    def _spawn_resource_field(self, resource_kind, position, amount):
        resource_class = RESOURCE_FIELD_CLASSES[resource_kind]
        field = resource_class(position=position, amount=amount)
        self.resource_fields.append(field)
        return field

    def _spawn_building(self, building_key, position, faction_key, owner):
        building_class = self._building_class_for_key(building_key)
        building = building_class(position=position, faction_key=faction_key, owner=owner)
        building.building_key = building_key
        if hasattr(building, "set_combat_context"):
            building.set_combat_context(self._iter_units, self._iter_buildings)
        self.buildings.append(building)
        return building

    def _spawn_unit(self, unit_key, position, faction_key, owner):
        unit_class = UNIT_DEFINITIONS[unit_key]["class"]
        unit = unit_class(position=position, faction_key=faction_key, owner=owner)
        unit.unit_key = unit_key
        unit.set_navigation_context(self._iter_units, self._iter_buildings, self._plan_route)
        if hasattr(unit, "set_economy_context"):
            unit.set_economy_context(self._iter_resource_fields, self._iter_dropoff_buildings, self._deposit_resources)
        self.units.append(unit)
        return unit

    def _deploy_selected_mcv(self):
        if len(self.state.selected_units) != 1:
            return False

        selected_unit = self.state.selected_units[0]
        if not getattr(selected_unit, "deploy_building_key", None):
            return False

        return self._deploy_construction_vehicle(selected_unit)

    def _deploy_construction_vehicle(self, unit, auto=False):
        building_key = getattr(unit, "deploy_building_key", None)
        if not building_key:
            return False

        snapped_position = self._snap_to_grid(unit.position)
        can_build, message = self._can_place_building(building_key, snapped_position)
        if not can_build:
            if not auto:
                self.state.status_message = message
                self._refresh_ui()
            return False

        building_class = self._building_class_for_key(building_key)

        building = self._spawn_building(
            building_key,
            Vec3(snapped_position.x, building_class.placement_y, snapped_position.z),
            faction_key=unit.faction_key,
            owner=unit.owner,
        )

        if unit in self.state.selected_units:
            self.clear_selection()
        if unit in self.units:
            self.units.remove(unit)
        unit.destroy_self()

        if not auto and unit.owner == "player":
            self.state.selected_building = building
            building.select()
            self.state.status_message = f"{building.display_name} deployed from the MCV."
            self._refresh_ui()
        return True

    @staticmethod
    def _selection_status_for_unit(unit):
        if getattr(unit, "deploy_building_key", None):
            return f"{unit.display_name} selected. Press F to deploy Main Base."
        return f"{unit.display_name} selected."

    def _handle_left_click(self, multi_select=False):
        hovered = mouse.hovered_entity

        if hovered in self.units:
            if hovered.owner != "player":
                self.state.status_message = f"{hovered.faction.name} {hovered.display_name} spotted."
                self._refresh_ui()
                return
            if multi_select:
                if hovered in self.state.selected_units:
                    hovered.deselect()
                    self.state.selected_units.remove(hovered)
                else:
                    if self.state.selected_building:
                        self.state.selected_building.deselect()
                        self.state.selected_building = None
                    self.state.selected_units.append(hovered)
                    hovered.select()
            else:
                self.clear_selection()
                self.state.selected_units = [hovered]
                hovered.select()

            if len(self.state.selected_units) == 1:
                self.state.status_message = self._selection_status_for_unit(hovered)
            elif not self.state.selected_units:
                self.state.status_message = DEFAULT_STATUS
            else:
                self.state.status_message = f"{len(self.state.selected_units)} units selected."
        elif hovered in self.buildings:
            if hovered.owner != "player":
                self.state.status_message = f"{hovered.faction.name} {hovered.display_name} identified."
                self._refresh_ui()
                return
            self.clear_selection()
            self.state.selected_building = hovered
            hovered.select()
            self.state.status_message = f"{hovered.display_name} selected."
        else:
            if not multi_select:
                self.clear_selection()
                self.state.status_message = DEFAULT_STATUS

        self._refresh_ui()

    def _begin_selection_drag(self):
        self.selection_drag_origin = Vec2(mouse.position.x, mouse.position.y)
        self.selection_drag_additive = bool(held_keys["shift"])
        self.selection_box.enabled = True
        self._set_selection_box(self.selection_drag_origin, self.selection_drag_origin)

    def _finish_selection_drag(self):
        start = self.selection_drag_origin
        end = Vec2(mouse.position.x, mouse.position.y)
        additive = self.selection_drag_additive
        self._clear_selection_drag()
        if start is None:
            return

        if (end - start).length() < self.selection_drag_threshold:
            self._handle_left_click(multi_select=additive)
            return

        self._select_units_in_drag_rect(start, end, additive=additive)

    def _clear_selection_drag(self):
        self.selection_drag_origin = None
        self.selection_drag_additive = False
        self.selection_box.enabled = False
        self.selection_box.scale = (0, 0)

    def _update_selection_drag_visual(self):
        if self.selection_drag_origin is None:
            return
        current = Vec2(mouse.position.x, mouse.position.y)
        self._set_selection_box(self.selection_drag_origin, current)

    def _set_selection_box(self, start, end):
        min_x = min(start.x, end.x)
        max_x = max(start.x, end.x)
        min_y = min(start.y, end.y)
        max_y = max(start.y, end.y)
        self.selection_box.position = Vec3((min_x + max_x) / 2, (min_y + max_y) / 2, -0.01)
        self.selection_box.scale = (max(0.001, max_x - min_x), max(0.001, max_y - min_y))

    def _select_units_in_drag_rect(self, start, end, additive=False):
        min_x = min(start.x, end.x)
        max_x = max(start.x, end.x)
        min_y = min(start.y, end.y)
        max_y = max(start.y, end.y)

        if not additive:
            self.clear_selection()
        elif self.state.selected_building:
            self.state.selected_building.deselect()
            self.state.selected_building = None

        selected_now = []
        for unit in self.units:
            if unit.owner != "player" or getattr(unit, "is_destroyed", False):
                continue
            screen_position = self._entity_screen_position(unit)
            if screen_position is None:
                continue
            if min_x <= screen_position.x <= max_x and min_y <= screen_position.y <= max_y:
                selected_now.append(unit)
                if unit not in self.state.selected_units:
                    self.state.selected_units.append(unit)
                    unit.select()

        if len(self.state.selected_units) == 1:
            self.state.status_message = self._selection_status_for_unit(self.state.selected_units[0])
        elif self.state.selected_units:
            self.state.status_message = f"{len(self.state.selected_units)} units selected."
        elif additive:
            self.state.status_message = "No additional units in selection box."
        else:
            self.state.status_message = DEFAULT_STATUS

        if not selected_now and not additive:
            self.clear_selection()

        self._refresh_ui()

    def _entity_screen_position(self, entity):
        if not hasattr(camera, "lens"):
            return None
        try:
            return entity.screen_position
        except Exception:
            return None

    def _handle_right_click(self):
        if not self.state.selected_units:
            return

        hovered = mouse.hovered_entity
        if hovered in self.resource_fields:
            selected_harvesters = [unit for unit in self.state.selected_units if hasattr(unit, "command_harvest")]
            if selected_harvesters:
                if hovered.is_depleted:
                    self.state.status_message = f"{hovered.display_name} is depleted."
                else:
                    for harvester in selected_harvesters:
                        harvester.command_harvest(hovered)
                    self.state.status_message = f"Harvest order: {hovered.display_name}."
                self._refresh_ui()
                return

        if hovered in self.units and hovered.owner != "player":
            for unit in self.state.selected_units:
                unit.command_attack(hovered)
            self.state.status_message = f"Attack order: {hovered.faction.name} {hovered.display_name}."
            self._refresh_ui()
            return

        if hovered in self.buildings and hovered.owner != "player":
            for unit in self.state.selected_units:
                unit.command_attack(hovered)
            self.state.status_message = f"Attack order: {hovered.faction.name} {hovered.display_name}."
            self._refresh_ui()
            return

        if not mouse.world_point:
            return

        move_target = self._snap_to_grid(mouse.world_point)
        selected_units = sorted(self.state.selected_units, key=lambda unit: (unit.z, unit.x))
        formation_targets = self._build_formation_targets(move_target, len(selected_units))
        ignored_units = set(selected_units)
        for unit, target in zip(selected_units, formation_targets):
            unit.command_move(self._resolve_move_target(target, unit, ignored_units))

        if len(selected_units) == 1:
            self.state.status_message = f"{selected_units[0].display_name} moving."
        else:
            self.state.status_message = f"Moving {len(selected_units)} units."
        self._refresh_ui()

    def _place_pending_building(self):
        if not mouse.world_point:
            self.state.status_message = "Move the cursor over the ground to place a structure."
            self._refresh_ui()
            return

        building_key = self.state.pending_building_key
        if building_key is None:
            self.state.status_message = DEFAULT_STATUS
            self._refresh_ui()
            return
        snapped_position = self._snap_to_grid(mouse.world_point)
        can_build, message = self._can_place_building(building_key, snapped_position)
        if not can_build:
            self.state.status_message = message
            self._refresh_ui()
            return

        definition = BUILDING_DEFINITIONS[building_key]
        if self.state.ready_building_key != building_key:
            self.state.status_message = f"{definition['label']} is not ready for placement."
            self._refresh_ui()
            return

        building_class = definition["class"]
        position = Vec3(snapped_position.x, building_class.placement_y, snapped_position.z)
        building = self._spawn_building(
            building_key,
            position,
            faction_key=self.state.player_faction_key,
            owner="player",
        )

        self.state.pending_building_key = None
        self.state.ready_building_key = None
        self.clear_selection()
        self.state.selected_building = building
        building.select()
        self.state.status_message = f"{building.display_name} deployed."
        self._refresh_ui()

    def _update_build_preview(self):
        building_key = self.state.pending_building_key
        if building_key is None or not mouse.world_point:
            self.preview_entity.enabled = False
            return

        definition = BUILDING_DEFINITIONS[building_key]
        building_class = definition["class"]
        preview_point = self._snap_to_grid(mouse.world_point)
        can_build, _ = self._can_place_building(building_key, preview_point)

        self.preview_entity.enabled = True
        self.preview_entity.scale = building_class.size
        self.preview_entity.position = Vec3(
            preview_point.x,
            building_class.placement_y,
            preview_point.z,
        )
        self.preview_entity.color = (
            color.rgba32(82, 161, 95, 130)
            if can_build
            else color.rgba32(187, 77, 71, 130)
        )

    def _can_place_building(self, building_key, position):
        building_class = self._building_class_for_key(building_key)
        half_width = building_class.size[0] / 2
        half_depth = building_class.size[2] / 2

        if abs(position.x) > (GROUND_EDGE_LIMIT - half_width) or abs(position.z) > (
            GROUND_EDGE_LIMIT - half_depth
        ):
            return False, "Placement is outside the build area."

        for building in self.buildings:
            min_dx = half_width + (building.scale_x / 2) + BUILD_CLEARANCE
            min_dz = half_depth + (building.scale_z / 2) + BUILD_CLEARANCE
            if abs(position.x - building.x) < min_dx and abs(position.z - building.z) < min_dz:
                return False, "Too close to another structure."

        return True, ""

    def _available_units_for_selection(self):
        selected_building = self.state.selected_building
        if not selected_building:
            return ()

        if selected_building.owner != "player":
            return ()

        for building_type, unit_keys in BUILDING_TRAINING.items():
            if isinstance(selected_building, building_type):
                return unit_keys

        return ()

    def _find_spawn_position(self, source_building, unit_radius=1.2):
        base_x = source_building.scale_x / 2 + 1.5
        base_z = source_building.scale_z / 2 + 1.5
        candidates = [
            Vec3(source_building.x + base_x, 0.5, source_building.z),
            Vec3(source_building.x - base_x, 0.5, source_building.z),
            Vec3(source_building.x, 0.5, source_building.z + base_z),
            Vec3(source_building.x, 0.5, source_building.z - base_z),
            Vec3(source_building.x + base_x, 0.5, source_building.z + base_z),
            Vec3(source_building.x - base_x, 0.5, source_building.z - base_z),
        ]

        for candidate in candidates:
            candidate = self._clamp_point_to_ground(candidate)
            if self._position_is_free(candidate, unit_radius=unit_radius):
                return candidate

        fallback_index = self.spawn_counts[source_building]
        self.spawn_counts[source_building] += 1
        fallback = Vec3(
            source_building.x + base_x + 2 + (fallback_index * 1.4),
            0.5,
            source_building.z,
        )
        fallback.x = max(-GROUND_EDGE_LIMIT, min(GROUND_EDGE_LIMIT, fallback.x))
        fallback.z = max(-GROUND_EDGE_LIMIT, min(GROUND_EDGE_LIMIT, fallback.z))
        return fallback

    def _position_is_free(self, position, unit_radius, ignored_units=None):
        ignored_units = ignored_units or set()
        for unit in self.units:
            if unit in ignored_units or getattr(unit, "is_destroyed", False):
                continue
            other_radius = getattr(unit, "footprint_radius", unit.scale_x / 2)
            if distance(unit.position, position) < unit_radius + other_radius:
                return False

        for building in self.buildings:
            if getattr(building, "is_destroyed", False):
                continue
            if (
                abs(position.x - building.x) < (building.scale_x / 2) + unit_radius
                and abs(position.z - building.z) < (building.scale_z / 2) + unit_radius
            ):
                return False

        return True

    def _build_formation_targets(self, center, unit_count):
        if unit_count == 1:
            return [center]

        columns = max(2, ceil(sqrt(unit_count)))
        rows = ceil(unit_count / columns)
        targets = []
        for index in range(unit_count):
            row = index // columns
            column = index % columns
            x_offset = (column - ((columns - 1) / 2)) * FORMATION_SPACING
            z_offset = (row - ((rows - 1) / 2)) * FORMATION_SPACING
            targets.append(Vec3(center.x + x_offset, 0, center.z + z_offset))
        return targets

    def _resolve_move_target(self, target, unit, ignored_units):
        base_target = self._clamp_point_to_ground(target)
        probe_offsets = [Vec3(0, 0, 0)]
        for ring in range(1, MOVE_TARGET_SEARCH_RINGS + 1):
            radius = ring * MOVE_TARGET_SEARCH_STEP
            probe_offsets.extend(
                [
                    Vec3(radius, 0, 0),
                    Vec3(-radius, 0, 0),
                    Vec3(0, 0, radius),
                    Vec3(0, 0, -radius),
                    Vec3(radius, 0, radius),
                    Vec3(radius, 0, -radius),
                    Vec3(-radius, 0, radius),
                    Vec3(-radius, 0, -radius),
                ]
            )

        for offset in probe_offsets:
            candidate = self._clamp_point_to_ground(base_target + offset)
            if self._position_is_free(candidate, unit.footprint_radius, ignored_units):
                return Vec3(candidate.x, unit.ground_y, candidate.z)

        return Vec3(base_target.x, unit.ground_y, base_target.z)

    def _plan_route(self, start, goal, unit_radius):
        start = self._clamp_point_to_ground(Vec3(start.x, start.y, start.z))
        goal = self._clamp_point_to_ground(Vec3(goal.x, start.y, goal.z))
        direct_goal = Vec3(goal.x, start.y, goal.z)

        if self._line_is_clear(start, direct_goal, unit_radius):
            return [direct_goal]

        start_cell = self._nearest_walkable_cell((round(start.x), round(start.z)), unit_radius, preferred_point=start)
        goal_cell = self._nearest_walkable_cell((round(goal.x), round(goal.z)), unit_radius, preferred_point=goal)
        if start_cell is None or goal_cell is None:
            return [direct_goal]

        cell_path = self._astar_path(start_cell, goal_cell, unit_radius)
        if not cell_path:
            return [direct_goal]

        waypoint_path = [Vec3(cell[0], start.y, cell[1]) for cell in cell_path]
        waypoint_path = self._smooth_path(waypoint_path, unit_radius)
        if not waypoint_path:
            return [direct_goal]

        if self._line_is_clear(waypoint_path[-1], direct_goal, unit_radius):
            waypoint_path[-1] = direct_goal

        return waypoint_path[1:] if len(waypoint_path) > 1 else [waypoint_path[0]]

    def _nearest_walkable_cell(self, cell, unit_radius, preferred_point, max_radius=12):
        if self._cell_is_walkable(cell, unit_radius):
            return cell

        preferred = Vec3(preferred_point.x, 0, preferred_point.z)
        for radius in range(1, max_radius + 1):
            candidates = []
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if max(abs(dx), abs(dz)) != radius:
                        continue
                    candidate = (cell[0] + dx, cell[1] + dz)
                    if not self._cell_is_walkable(candidate, unit_radius):
                        continue
                    candidate_point = Vec3(candidate[0], 0, candidate[1])
                    score = (candidate_point - preferred).length()
                    candidates.append((score, candidate))
            if candidates:
                candidates.sort(key=lambda item: item[0])
                return candidates[0][1]

        return None

    def _astar_path(self, start_cell, goal_cell, unit_radius):
        if start_cell == goal_cell:
            return [start_cell]

        open_heap = []
        came_from = {}
        g_score = {start_cell: 0.0}
        closed = set()
        heappush(open_heap, (self._path_heuristic(start_cell, goal_cell), 0.0, start_cell))

        while open_heap:
            _, current_cost, current = heappop(open_heap)
            if current in closed:
                continue
            if current == goal_cell:
                return self._reconstruct_path(came_from, current)

            closed.add(current)
            for neighbor, move_cost in self._iter_path_neighbors(current, unit_radius):
                if neighbor in closed:
                    continue

                tentative_cost = current_cost + move_cost
                if tentative_cost >= g_score.get(neighbor, float("inf")):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative_cost
                priority = tentative_cost + self._path_heuristic(neighbor, goal_cell)
                heappush(open_heap, (priority, tentative_cost, neighbor))

        return ()

    def _iter_path_neighbors(self, cell, unit_radius):
        directions = (
            ((1, 0), 1.0),
            ((-1, 0), 1.0),
            ((0, 1), 1.0),
            ((0, -1), 1.0),
            ((1, 1), 1.4142),
            ((1, -1), 1.4142),
            ((-1, 1), 1.4142),
            ((-1, -1), 1.4142),
        )

        for (dx, dz), move_cost in directions:
            neighbor = (cell[0] + dx, cell[1] + dz)
            if not self._cell_is_walkable(neighbor, unit_radius):
                continue
            if dx != 0 and dz != 0:
                if not self._cell_is_walkable((cell[0] + dx, cell[1]), unit_radius):
                    continue
                if not self._cell_is_walkable((cell[0], cell[1] + dz), unit_radius):
                    continue
            yield neighbor, move_cost

    @staticmethod
    def _path_heuristic(cell, goal):
        dx = abs(goal[0] - cell[0])
        dz = abs(goal[1] - cell[1])
        return (dx + dz) + (1.4142 - 2.0) * min(dx, dz)

    @staticmethod
    def _reconstruct_path(came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _smooth_path(self, waypoint_path, unit_radius):
        if len(waypoint_path) <= 2:
            return waypoint_path

        smoothed = [waypoint_path[0]]
        index = 0
        while index < len(waypoint_path) - 1:
            next_index = index + 1
            for candidate_index in range(len(waypoint_path) - 1, index, -1):
                if self._line_is_clear(waypoint_path[index], waypoint_path[candidate_index], unit_radius):
                    next_index = candidate_index
                    break
            smoothed.append(waypoint_path[next_index])
            index = next_index
        return smoothed

    def _cell_is_walkable(self, cell, unit_radius):
        return self._point_is_walkable(cell[0], cell[1], unit_radius)

    def _point_is_walkable(self, x, z, unit_radius):
        if abs(x) > (GROUND_EDGE_LIMIT - unit_radius) or abs(z) > (GROUND_EDGE_LIMIT - unit_radius):
            return False

        padding = unit_radius + 0.12
        for building in self.buildings:
            if getattr(building, "is_destroyed", False):
                continue
            if abs(x - building.x) < (building.scale_x / 2) + padding and abs(z - building.z) < (building.scale_z / 2) + padding:
                return False

        return True

    def _line_is_clear(self, start, end, unit_radius):
        delta = Vec3(end.x - start.x, 0, end.z - start.z)
        distance_to_goal = delta.length()
        if distance_to_goal <= 0.01:
            return True

        sample_count = max(1, ceil(distance_to_goal / 0.55))
        for index in range(1, sample_count + 1):
            t = index / sample_count
            sample_x = start.x + ((end.x - start.x) * t)
            sample_z = start.z + ((end.z - start.z) * t)
            if not self._point_is_walkable(sample_x, sample_z, unit_radius):
                return False

        return True

    def _clamp_point_to_ground(self, point):
        return Vec3(
            max(-GROUND_EDGE_LIMIT, min(GROUND_EDGE_LIMIT, point.x)),
            point.y,
            max(-GROUND_EDGE_LIMIT, min(GROUND_EDGE_LIMIT, point.z)),
        )

    def _cleanup_destroyed_entities(self):
        ui_changed = False

        live_units = [unit for unit in self.units if not getattr(unit, "is_destroyed", False)]
        if len(live_units) != len(self.units):
            self.units = live_units
            ui_changed = True

        live_buildings = [building for building in self.buildings if not getattr(building, "is_destroyed", False)]
        if len(live_buildings) != len(self.buildings):
            self.buildings = live_buildings
            ui_changed = True

        live_selected_units = [unit for unit in self.state.selected_units if unit in self.units]
        if len(live_selected_units) != len(self.state.selected_units):
            self.state.selected_units = live_selected_units
            ui_changed = True

        if self.state.selected_building and self.state.selected_building not in self.buildings:
            self.state.selected_building = None
            ui_changed = True

        if ui_changed:
            self._refresh_ui()

    def _update_battle_result(self):
        if self.battle_result:
            return

        player_assets = any(entity.owner == "player" for entity in self.units + self.buildings)
        enemy_assets = any(entity.owner == "enemy" for entity in self.units + self.buildings)

        if not enemy_assets:
            self.battle_result = "victory"
            self.state.status_message = f"{self.player_faction.name} controls the battlefield."
            self._refresh_ui()
        elif not player_assets:
            self.battle_result = "defeat"
            self.state.status_message = f"{self.enemy_faction.name} has crushed your battle group."
            self._refresh_ui()

    def _deposit_resources(self, owner, amount):
        if amount <= 0:
            return
        if owner == "player":
            self.state.credits += int(amount)
        else:
            self.state.enemy_credits += int(amount)
        self._refresh_ui()

    def _iter_units(self):
        return tuple(self.units)

    def _iter_buildings(self):
        return tuple(self.buildings)

    def _iter_resource_fields(self):
        return tuple(self.resource_fields)

    def _iter_dropoff_buildings(self, owner):
        return tuple(
            building
            for building in self.buildings
            if not getattr(building, "is_destroyed", False)
            and getattr(building, "accepts_resources", False)
            and building.owner == owner
        )

    def _move_camera(self):
        movement = Vec3(
            held_keys["d"] - held_keys["a"],
            0,
            held_keys["w"] - held_keys["s"],
        )
        if movement == Vec3(0, 0, 0):
            return

        camera.position += movement.normalized() * CAMERA_MOVE_SPEED * time.dt
        camera.x = max(-GROUND_EDGE_LIMIT, min(GROUND_EDGE_LIMIT, camera.x))
        camera.z = max(-GROUND_EDGE_LIMIT, min(GROUND_EDGE_LIMIT, camera.z))

    def _zoom_camera(self, delta_y):
        new_y = max(CAMERA_MIN_Y, min(CAMERA_MAX_Y, camera.y + delta_y))
        camera.y = new_y

    def _snap_to_grid(self, world_point):
        return Vec3(round(world_point.x), 0, round(world_point.z))

    def _hovering_ui(self):
        hovered = mouse.hovered_entity
        while hovered:
            if hovered == camera.ui:
                return True
            hovered = hovered.parent
        return False

    def _current_selection_label(self):
        if self.state.pending_building_key:
            return f"placing {BUILDING_DEFINITIONS[self.state.pending_building_key]['label']}"

        if len(self.state.selected_units) == 1:
            unit = self.state.selected_units[0]
            if hasattr(unit, "get_selection_summary"):
                return unit.get_selection_summary()
            return f"{unit.display_name} ({max(0, int(unit.health))} hp)"

        if self.state.selected_units:
            return f"{len(self.state.selected_units)} units"

        if self.state.selected_building:
            building = self.state.selected_building
            return f"{building.display_name} ({max(0, int(building.health))} hp)"

        return "none"

    def _refresh_ui(self):
        self.sidebar.refresh(
            credits=self.state.credits,
            selection_label=self._current_selection_label(),
            status_message=self.state.status_message,
            pending_building_key=self.state.pending_building_key,
            available_units=self._available_units_for_selection(),
            cancel_available=self.state.pending_building_key is not None or self.state.construction_building_key is not None,
            building_states=self._building_button_states(),
            construction_label=self._construction_label(),
            construction_ratio=self._construction_progress(),
        )
