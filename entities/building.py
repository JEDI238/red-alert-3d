from math import atan2, degrees

from ursina import Entity, Vec3, color, destroy, lerp, time
from factions import get_faction_theme


class Building(Entity):
    display_name = "Building"
    cost = 0
    base_tint = color.rgb32(96, 103, 112)
    size = (2, 2, 2)
    placement_y = 1
    default_health = 500
    selection_color = color.rgb32(255, 201, 102)
    selection_ring_alpha = 110
    selection_ring_scale = 1.14
    can_be_targeted = True
    accepts_resources = False
    health_bar_display_time = 3.2

    def __init__(self, position=(0, 0, 0), faction_key="alliance", owner="player", health=None, **kwargs):
        self.faction_key = faction_key
        self.owner = owner
        self.faction = get_faction_theme(faction_key)
        self.selection_color = self.faction.selection
        self.style = self._get_style()
        self.is_destroyed = False
        self.is_selected = False
        self.health_bar_timer = 0.0
        super().__init__(
            model="cube",
            color=self.style["body"],
            scale=self.size,
            position=position,
            collider="box",
            **kwargs,
        )
        self.base_color = self.style["body"]
        self.max_health = health if health is not None else self.default_health
        self.health = self.max_health
        self.visual_parts = []
        self.selection_indicator = Entity(
            parent=self,
            model="plane",
            scale=(self.selection_ring_scale, 1, self.selection_ring_scale),
            y=-(self.scale_y / 2) + 0.04,
            color=color.rgba32(
                self.selection_color.r * 255,
                self.selection_color.g * 255,
                self.selection_color.b * 255,
                self.selection_ring_alpha,
            ),
            collider=None,
            enabled=False,
        )
        self.health_bar_root = Entity(parent=self, y=(self.scale_y / 2) + 0.34, enabled=False)
        self.health_bar_bg = Entity(
            parent=self.health_bar_root,
            model="cube",
            scale=(0.94, 0.06, 0.04),
            color=color.rgba32(18, 18, 20, 200),
            collider=None,
        )
        self.health_bar_fill = Entity(
            parent=self.health_bar_root,
            model="cube",
            scale=(0.86, 0.03, 0.05),
            y=0.005,
            color=color.rgb32(92, 208, 124),
            collider=None,
        )
        self._build_visuals()
        self._update_health_bar()
        self._refresh_health_bar_visibility()

    def update(self):
        if self.is_destroyed:
            return
        self.health_bar_timer = max(0.0, self.health_bar_timer - time.dt)
        self._refresh_health_bar_visibility()

    @property
    def footprint(self):
        return self.scale_x, self.scale_z

    def select(self):
        self.is_selected = True
        self.selection_indicator.enabled = True
        self._show_health_bar()

    def deselect(self):
        self.is_selected = False
        self.selection_indicator.enabled = False
        self._refresh_health_bar_visibility()

    def is_enemy_to(self, owner):
        return self.owner != owner

    def damage(self, amount, attacker=None):
        return self.take_damage(amount, attacker=attacker)

    def take_damage(self, amount, attacker=None):
        if self.is_destroyed:
            return True
        self.health -= amount
        self._update_health_bar()
        self._show_health_bar(duration=self.health_bar_display_time)
        if self.health <= 0:
            self.destroy_self()
            return True
        return False

    def destroy_self(self):
        if self.is_destroyed:
            return
        self.is_destroyed = True
        self.collider = None
        self.enabled = False
        destroy(self)

    def _show_health_bar(self, duration=None):
        if duration is None:
            self.health_bar_timer = max(self.health_bar_timer, self.health_bar_display_time)
        else:
            self.health_bar_timer = max(self.health_bar_timer, duration)
        self._refresh_health_bar_visibility()

    def _refresh_health_bar_visibility(self):
        self.health_bar_root.enabled = self.is_selected or self.health_bar_timer > 0

    def _add_detail(self, *, scale, position=(0, 0, 0), color=None, rotation=(0, 0, 0), model="cube"):
        detail = Entity(
            parent=self,
            model=model,
            scale=scale,
            position=position,
            color=color if color is not None else self.base_color,
            rotation=rotation,
            collider=None,
        )
        self.visual_parts.append(detail)
        return detail

    def _build_visuals(self):
        pass

    def _get_style(self):
        return {
            "body": self.base_tint,
            "roof": self.faction.secondary,
            "metal": self.faction.metal,
            "accent": self.faction.accent,
            "panel": self.faction.panel,
            "glow": self.faction.glow,
        }

    def _update_health_bar(self):
        health_ratio = max(0.0, min(1.0, self.health / max(1, self.max_health)))
        max_width = 0.86
        self.health_bar_fill.scale_x = max_width * health_ratio
        self.health_bar_fill.x = -(max_width - self.health_bar_fill.scale_x) / 2
        if health_ratio > 0.6:
            self.health_bar_fill.color = color.rgb32(92, 208, 124)
        elif health_ratio > 0.3:
            self.health_bar_fill.color = color.rgb32(232, 191, 88)
        else:
            self.health_bar_fill.color = color.rgb32(211, 92, 78)


class DefenseBuilding(Building):
    default_attack_damage = 10
    default_attack_range = 7.5
    default_attack_cooldown = 0.35
    default_vision_range = 8.5
    attack_targets_buildings = False
    attack_flash_duration = 0.07

    def __init__(self, *args, damage=None, attack_range=None, attack_cooldown=None, vision_range=None, **kwargs):
        self.units_provider = lambda: ()
        self.buildings_provider = lambda: ()
        self.attack_damage = damage if damage is not None else self.default_attack_damage
        self.attack_range = attack_range if attack_range is not None else self.default_attack_range
        self.attack_cooldown = attack_cooldown if attack_cooldown is not None else self.default_attack_cooldown
        self.vision_range = vision_range if vision_range is not None else self.default_vision_range
        self.attack_timer = 0.0
        self.attack_flash_timer = 0.0
        self.attack_target = None
        super().__init__(*args, **kwargs)
        self.attack_flash = Entity(
            parent=self._attack_flash_parent(),
            model="cube",
            scale=self._attack_flash_scale(),
            position=self._attack_flash_position(),
            color=self._attack_flash_color(),
            collider=None,
            enabled=False,
        )

    def update(self):
        super().update()
        if self.is_destroyed:
            return

        self.attack_timer = max(0.0, self.attack_timer - time.dt)
        self.attack_flash_timer = max(0.0, self.attack_flash_timer - time.dt)
        self.attack_flash.enabled = self.attack_flash_timer > 0

        if self.attack_target and not self._is_target_valid(self.attack_target):
            self.attack_target = None

        if not self.attack_target:
            self._acquire_auto_target()

        if self.attack_target:
            self._aim_visuals(self.attack_target)
            if self._distance_to_target(self.attack_target) <= self.attack_range and self.attack_timer <= 0:
                self._fire_at(self.attack_target)

    def set_combat_context(self, units_provider, buildings_provider):
        self.units_provider = units_provider
        self.buildings_provider = buildings_provider

    def take_damage(self, amount, attacker=None):
        destroyed = super().take_damage(amount, attacker=attacker)
        if not destroyed and attacker and self._is_target_valid(attacker):
            self.attack_target = attacker
        return destroyed

    def _acquire_auto_target(self):
        nearest_target = None
        nearest_distance = self.vision_range
        for target in self._iter_enemy_targets():
            target_distance = self._distance_to_target(target)
            if target_distance <= nearest_distance:
                nearest_distance = target_distance
                nearest_target = target
        self.attack_target = nearest_target

    def _iter_enemy_targets(self):
        for unit in self.units_provider():
            if self._is_target_valid(unit):
                yield unit

        if not self.attack_targets_buildings:
            return

        for building in self.buildings_provider():
            if self._is_target_valid(building):
                yield building

    def _is_target_valid(self, target):
        return (
            target is not None
            and not getattr(target, "is_destroyed", False)
            and getattr(target, "enabled", True)
            and getattr(target, "owner", self.owner) != self.owner
            and getattr(target, "can_be_targeted", True)
        )

    def _distance_to_target(self, target):
        center_vector = Vec3(target.x - self.x, 0, target.z - self.z)
        target_radius = max(getattr(target, "scale_x", 1), getattr(target, "scale_z", 1)) / 2
        return max(0.0, center_vector.length() - target_radius)

    def _fire_at(self, target):
        self.attack_timer = self.attack_cooldown
        self.attack_flash_timer = self.attack_flash_duration
        self.attack_flash.enabled = True
        if hasattr(target, "take_damage"):
            target.take_damage(self.attack_damage, attacker=self)

    def _aim_visuals(self, target):
        pass

    def _attack_flash_parent(self):
        return self

    def _attack_flash_position(self):
        return (0, 0.2, 0.7)

    def _attack_flash_scale(self):
        return (0.16, 0.16, 0.22)

    def _attack_flash_color(self):
        return color.rgba32(255, 218, 130, 220)


class MainBase(Building):
    display_name = "Main Base"
    cost = 650
    base_tint = color.rgb32(89, 105, 125)
    size = (3.45, 2.45, 3.45)
    placement_y = 1.23
    default_health = 1800
    accepts_resources = False
    selection_ring_scale = 1.12

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(129, 64, 58),
                "roof": color.rgb32(165, 84, 76),
                "metal": color.rgb32(77, 72, 76),
                "accent": self.faction.accent,
                "panel": color.rgb32(102, 43, 39),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(84, 114, 160),
            "roof": color.rgb32(166, 191, 219),
            "metal": color.rgb32(72, 88, 112),
            "accent": self.faction.accent,
            "panel": color.rgb32(52, 72, 104),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.12, 0.04, 1.12), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_detail(scale=(0.96, 0.18, 0.96), position=(0, 0.58, 0), color=self.style["roof"])
        self._add_detail(scale=(0.44, 0.54, 0.28), position=(0, 0.94, -0.12), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.62, 0.18), position=(-0.62, 0.72, 0.36), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.62, 0.18), position=(0.62, 0.72, 0.36), color=self.style["panel"])
        self._add_detail(scale=(0.26, 0.18, 0.64), position=(-0.64, -0.18, -0.24), color=self.style["panel"])
        self._add_detail(scale=(0.26, 0.18, 0.64), position=(0.64, -0.18, -0.24), color=self.style["panel"])
        self._add_detail(scale=(0.52, 0.12, 0.16), position=(0, 0.12, 0.72), color=self.style["accent"])
        self._add_detail(scale=(0.68, 0.1, 0.12), position=(0, -0.18, 0.9), color=self.style["glow"])
        self._add_detail(scale=(0.14, 0.3, 0.14), position=(-0.9, -0.18, 0.7), color=self.style["metal"])
        self._add_detail(scale=(0.14, 0.3, 0.14), position=(0.9, -0.18, 0.7), color=self.style["metal"])
        self._add_detail(scale=(0.56, 0.06, 0.1), position=(0, 0.82, 0.44), color=self.style["accent"])
        self._add_detail(scale=(0.72, 0.05, 0.08), position=(0, 1.04, -0.72), color=self.style["panel"])
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.14, 0.9, 0.14), position=(-0.26, 1.3, -0.52), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.9, 0.14), position=(0.26, 1.3, -0.52), color=self.style["metal"])
            self._add_detail(scale=(0.24, 0.1, 0.24), position=(-0.26, 1.78, -0.52), color=self.style["glow"])
            self._add_detail(scale=(0.24, 0.1, 0.24), position=(0.26, 1.78, -0.52), color=self.style["glow"])
            self._add_detail(scale=(0.16, 0.54, 0.16), position=(0, 1.36, 0.24), color=self.style["accent"])
            self._add_detail(scale=(0.12, 0.34, 0.36), position=(-0.72, 0.42, -0.7), color=self.style["panel"])
            self._add_detail(scale=(0.12, 0.34, 0.36), position=(0.72, 0.42, -0.7), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.06, 0.92, 0.06), position=(0.46, 1.28, -0.42), color=self.style["metal"])
            self._add_detail(scale=(0.22, 0.1, 0.22), position=(0.46, 1.78, -0.42), color=self.style["glow"])
            self._add_detail(scale=(0.5, 0.1, 0.14), position=(0, 0.32, 0.82), color=self.style["glow"])
            self._add_detail(scale=(0.28, 0.08, 0.28), position=(-0.46, 1.04, 0.08), color=self.style["accent"])
            self._add_detail(scale=(0.1, 0.24, 0.48), position=(-0.76, 0.34, -0.64), color=self.style["panel"])
            self._add_detail(scale=(0.1, 0.24, 0.48), position=(0.76, 0.34, -0.64), color=self.style["panel"])


class Refinery(Building):
    display_name = "Refinery"
    cost = 420
    base_tint = color.rgb32(126, 114, 92)
    size = (3.0, 2.1, 3.15)
    placement_y = 1.05
    default_health = 1300
    accepts_resources = True
    selection_ring_scale = 1.1

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(132, 78, 66),
                "roof": color.rgb32(174, 98, 86),
                "metal": color.rgb32(82, 76, 77),
                "accent": self.faction.accent,
                "panel": color.rgb32(104, 53, 46),
                "glow": color.rgb32(232, 183, 92),
            }

        return {
            "body": color.rgb32(88, 123, 164),
            "roof": color.rgb32(162, 187, 214),
            "metal": color.rgb32(77, 94, 116),
            "accent": self.faction.accent,
            "panel": color.rgb32(57, 79, 109),
            "glow": color.rgb32(117, 227, 236),
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.1, 0.04, 1.08), position=(0, -0.5, 0), color=self.style["metal"])
        self._add_detail(scale=(1.06, 0.08, 1.02), position=(0, 0.58, 0), color=self.style["roof"])
        self._add_detail(scale=(0.76, 0.56, 0.52), position=(0, 0.12, -0.36), color=self.style["body"])
        self._add_detail(scale=(0.62, 0.16, 0.22), position=(0, 0.08, 0.78), color=self.style["accent"])
        self._add_detail(scale=(0.86, 0.08, 0.12), position=(0, -0.1, 1.02), color=self.style["glow"])
        self._add_detail(scale=(0.22, 0.48, 0.22), position=(-0.58, 0.02, 0.42), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.48, 0.22), position=(0.58, 0.02, 0.42), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.82, 0.18), position=(-0.82, 0.64, -0.54), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.82, 0.18), position=(0.82, 0.64, -0.54), color=self.style["metal"])
        self._add_detail(scale=(0.28, 0.14, 0.28), position=(-0.82, 1.08, -0.54), color=self.style["glow"])
        self._add_detail(scale=(0.28, 0.14, 0.28), position=(0.82, 1.08, -0.54), color=self.style["glow"])
        self._add_detail(scale=(0.96, 0.12, 0.22), position=(0, 0.32, 0.16), color=self.style["panel"])
        self._add_detail(scale=(0.26, 0.24, 0.9), position=(-0.98, -0.28, -0.22), color=self.style["metal"])
        self._add_detail(scale=(0.26, 0.24, 0.9), position=(0.98, -0.28, -0.22), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.18, 0.76), position=(0, 0.36, 0.58), color=self.style["accent"])
        self._add_detail(scale=(0.12, 0.46, 0.12), position=(-0.26, 0.7, 0.18), color=self.style["metal"])
        self._add_detail(scale=(0.12, 0.46, 0.12), position=(0.26, 0.7, 0.18), color=self.style["metal"])
        self._add_detail(scale=(0.4, 0.08, 0.08), position=(0, 0.8, 0.26), color=self.style["panel"])
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.34, 0.42, 0.34), position=(0, 0.86, -0.18), color=self.style["accent"])
            self._add_detail(scale=(0.1, 0.82, 0.1), position=(0.0, 1.12, 0.22), color=self.style["metal"])
            self._add_detail(scale=(0.5, 0.08, 0.14), position=(0, 0.26, 0.98), color=self.style["glow"])
            self._add_detail(scale=(0.14, 0.24, 0.54), position=(-0.68, 0.04, -0.84), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.42, 0.1, 0.68), position=(0, 0.94, -0.18), color=self.style["accent"])
            self._add_detail(scale=(0.12, 0.62, 0.12), position=(0.0, 1.0, 0.18), color=self.style["metal"])
            self._add_detail(scale=(0.46, 0.08, 0.14), position=(0, 0.26, 0.98), color=self.style["glow"])
            self._add_detail(scale=(0.14, 0.24, 0.54), position=(0.68, 0.04, -0.84), color=self.style["panel"])


class Barracks(Building):
    display_name = "Barracks"
    cost = 300
    base_tint = color.rgb32(78, 111, 158)
    size = (2.45, 1.65, 2.55)
    placement_y = 0.83
    default_health = 1000

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(129, 70, 64),
                "roof": color.rgb32(171, 86, 79),
                "metal": color.rgb32(76, 70, 74),
                "accent": self.faction.accent,
                "panel": color.rgb32(96, 43, 38),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(84, 120, 170),
            "roof": color.rgb32(151, 177, 209),
            "metal": color.rgb32(75, 92, 118),
            "accent": self.faction.accent,
            "panel": color.rgb32(48, 70, 102),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.08, 0.04, 1.08), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_detail(scale=(1.08, 0.08, 1.08), position=(0, 0.56, 0), color=self.style["roof"])
        self._add_detail(scale=(0.3, 0.54, 0.14), position=(0, -0.08, 0.52), color=self.style["metal"])
        self._add_detail(scale=(0.2, 0.22, 0.06), position=(-0.22, 0.04, 0.56), color=self.style["accent"])
        self._add_detail(scale=(0.2, 0.22, 0.06), position=(0.22, 0.04, 0.56), color=self.style["accent"])
        self._add_detail(scale=(0.24, 0.48, 0.34), position=(-0.36, -0.08, -0.12), color=self.style["panel"])
        self._add_detail(scale=(0.24, 0.48, 0.34), position=(0.36, -0.08, -0.12), color=self.style["panel"])
        self._add_detail(scale=(0.5, 0.12, 0.14), position=(0, 0.16, -0.56), color=self.style["panel"])
        self._add_detail(scale=(0.48, 0.04, 0.18), position=(0, 0.46, 0.72), color=self.style["glow"])
        self._add_detail(scale=(0.16, 0.18, 0.08), position=(-0.46, -0.24, 0.62), color=self.style["metal"])
        self._add_detail(scale=(0.16, 0.18, 0.08), position=(0.46, -0.24, 0.62), color=self.style["metal"])
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.12, 0.62, 0.12), position=(-0.4, 0.62, -0.28), color=self.style["metal"])
            self._add_detail(scale=(0.12, 0.62, 0.12), position=(0.4, 0.62, -0.28), color=self.style["metal"])
            self._add_detail(scale=(0.36, 0.08, 0.12), position=(0, 0.28, 0.58), color=self.style["glow"])
            self._add_detail(scale=(0.12, 0.44, 0.12), position=(0, 0.84, 0.12), color=self.style["accent"])
            self._add_detail(scale=(0.14, 0.22, 0.46), position=(0, 0.58, -0.72), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.06, 0.56, 0.06), position=(0.38, 0.62, -0.26), color=self.style["metal"])
            self._add_detail(scale=(0.18, 0.08, 0.18), position=(0.38, 0.96, -0.26), color=self.style["glow"])
            self._add_detail(scale=(0.46, 0.08, 0.12), position=(0, 0.32, 0.58), color=self.style["glow"])
            self._add_detail(scale=(0.26, 0.08, 0.26), position=(-0.46, 0.7, 0), color=self.style["accent"])
            self._add_detail(scale=(0.14, 0.16, 0.56), position=(-0.62, 0.14, -0.56), color=self.style["panel"])


class PowerPlant(Building):
    display_name = "Power Plant"
    cost = 250
    base_tint = color.rgb32(188, 156, 69)
    size = (2.05, 2.0, 2.05)
    placement_y = 1.0
    default_health = 700

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(173, 118, 62),
                "roof": color.rgb32(197, 143, 76),
                "metal": color.rgb32(84, 76, 66),
                "accent": self.faction.accent,
                "panel": color.rgb32(102, 68, 33),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(131, 160, 170),
            "roof": color.rgb32(171, 200, 214),
            "metal": color.rgb32(67, 93, 112),
            "accent": self.faction.accent,
            "panel": color.rgb32(56, 82, 104),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.1, 0.04, 1.1), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_detail(scale=(1.08, 0.08, 1.08), position=(0, 0.56, 0), color=self.style["roof"])
        self._add_detail(scale=(0.44, 0.62, 0.44), position=(0, 0.16, 0), color=self.style["accent"])
        self._add_detail(scale=(0.18, 0.42, 0.18), position=(-0.34, -0.1, 0.34), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.42, 0.18), position=(0.34, -0.1, 0.34), color=self.style["panel"])
        self._add_detail(scale=(0.82, 0.08, 0.12), position=(0, 0.12, 0.5), color=self.style["panel"])
        self._add_detail(scale=(0.56, 0.08, 0.08), position=(0, 0.34, 0.1), color=self.style["glow"])
        self._add_detail(scale=(0.16, 0.18, 0.64), position=(0, 0.6, 0.02), color=self.style["accent"])
        self._add_detail(scale=(0.56, 0.06, 0.06), position=(0, -0.02, 0.76), color=self.style["panel"])
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.14, 0.92, 0.14), position=(-0.26, 0.82, -0.24), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.92, 0.14), position=(0.26, 0.82, -0.24), color=self.style["metal"])
            self._add_detail(scale=(0.22, 0.12, 0.22), position=(-0.26, 1.28, -0.24), color=self.style["glow"])
            self._add_detail(scale=(0.22, 0.12, 0.22), position=(0.26, 1.28, -0.24), color=self.style["glow"])
            self._add_detail(scale=(0.72, 0.08, 0.08), position=(0, 0.52, -0.46), color=self.style["accent"])
            self._add_detail(scale=(0.12, 0.24, 0.42), position=(0, 0.22, -0.8), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.14, 0.74, 0.14), position=(-0.26, 0.68, -0.24), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.74, 0.14), position=(0.26, 0.68, -0.24), color=self.style["metal"])
            self._add_detail(scale=(0.2, 0.08, 0.2), position=(-0.26, 1.06, -0.24), color=self.style["glow"])
            self._add_detail(scale=(0.2, 0.08, 0.2), position=(0.26, 1.06, -0.24), color=self.style["glow"])
            self._add_detail(scale=(0.78, 0.08, 0.08), position=(0, 0.52, -0.46), color=self.style["accent"])
            self._add_detail(scale=(0.42, 0.06, 0.12), position=(0, 0.86, 0.42), color=self.style["glow"])


class TankFactory(Building):
    display_name = "Tank Factory"
    cost = 520
    base_tint = color.rgb32(94, 108, 122)
    size = (3.2, 2.25, 3.55)
    placement_y = 1.13
    default_health = 1250
    selection_ring_scale = 1.13

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(126, 74, 66),
                "roof": color.rgb32(171, 95, 84),
                "metal": color.rgb32(77, 72, 74),
                "accent": self.faction.accent,
                "panel": color.rgb32(96, 48, 42),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(84, 116, 156),
            "roof": color.rgb32(149, 180, 211),
            "metal": color.rgb32(72, 88, 110),
            "accent": self.faction.accent,
            "panel": color.rgb32(50, 72, 101),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.12, 0.04, 1.08), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_detail(scale=(1.08, 0.08, 1.04), position=(0, 0.58, 0), color=self.style["roof"])
        self._add_detail(scale=(0.86, 0.52, 0.46), position=(0, 0.12, -0.42), color=self.style["body"])
        self._add_detail(scale=(0.74, 0.18, 0.18), position=(0, 0.02, 0.98), color=self.style["accent"])
        self._add_detail(scale=(0.86, 0.08, 0.12), position=(0, -0.12, 1.18), color=self.style["glow"])
        self._add_detail(scale=(0.22, 0.64, 0.22), position=(-0.74, 0.12, 0.28), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.64, 0.22), position=(0.74, 0.12, 0.28), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.98, 0.18), position=(-0.9, 0.74, -0.7), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.98, 0.18), position=(0.9, 0.74, -0.7), color=self.style["metal"])
        self._add_detail(scale=(0.28, 0.14, 0.28), position=(-0.9, 1.28, -0.7), color=self.style["glow"])
        self._add_detail(scale=(0.28, 0.14, 0.28), position=(0.9, 1.28, -0.7), color=self.style["glow"])
        self._add_detail(scale=(0.56, 0.12, 0.18), position=(0, 0.3, 0.58), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.34, 1.08), position=(-1.08, -0.26, -0.12), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.34, 1.08), position=(1.08, -0.26, -0.12), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.18, 0.78), position=(0, 0.44, 0.84), color=self.style["accent"])
        self._add_detail(scale=(0.16, 0.54, 0.16), position=(-0.42, 0.84, 0.12), color=self.style["metal"])
        self._add_detail(scale=(0.16, 0.54, 0.16), position=(0.42, 0.84, 0.12), color=self.style["metal"])
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.4, 0.14, 0.72), position=(0, 0.9, -0.28), color=self.style["accent"])
            self._add_detail(scale=(0.12, 0.62, 0.12), position=(0, 1.08, 0.32), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.18, 0.72), position=(0.82, 0.06, -0.92), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.42, 0.1, 0.62), position=(0, 0.92, -0.22), color=self.style["accent"])
            self._add_detail(scale=(0.1, 0.56, 0.1), position=(0, 1.02, 0.28), color=self.style["metal"])
            self._add_detail(scale=(0.72, 0.06, 0.1), position=(0, 1.18, -0.78), color=self.style["glow"])


class MachineGunBunker(DefenseBuilding):
    display_name = "MG Pillbox"
    cost = 240
    base_tint = color.rgb32(112, 102, 90)
    size = (1.75, 1.38, 1.75)
    placement_y = 0.69
    default_health = 850
    default_attack_damage = 9
    default_attack_range = 8.2
    default_attack_cooldown = 0.22
    default_vision_range = 9.2
    selection_ring_scale = 1.08

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(122, 84, 72),
                "roof": color.rgb32(160, 106, 92),
                "metal": color.rgb32(75, 71, 72),
                "accent": self.faction.accent,
                "panel": color.rgb32(95, 58, 48),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(95, 118, 149),
            "roof": color.rgb32(155, 176, 199),
            "metal": color.rgb32(69, 84, 101),
            "accent": self.faction.accent,
            "panel": color.rgb32(57, 76, 99),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.12, 0.04, 1.12), position=(0, -0.5, 0), color=self.style["metal"])
        self._add_detail(scale=(1.06, 0.08, 1.06), position=(0, 0.54, 0), color=self.style["roof"])
        self._add_detail(scale=(0.62, 0.22, 0.22), position=(0, 0.1, 0.76), color=self.style["accent"])
        self._add_detail(scale=(0.74, 0.08, 0.12), position=(0, -0.08, 0.98), color=self.style["glow"])
        self.turret_base = self._add_detail(scale=(0.42, 0.28, 0.42), position=(0, 0.46, -0.06), color=self.style["panel"])
        self.turret = self._add_detail(scale=(0.3, 0.18, 0.3), position=(0, 0.66, -0.02), color=self.style["metal"])
        self.barrel = Entity(
            parent=self.turret,
            model="cube",
            scale=(0.12, 0.08, 0.72),
            position=(0, -0.02, 0.42),
            color=self.style["metal"],
            collider=None,
        )
        self.visual_parts.append(self.barrel)
        self._add_detail(scale=(0.18, 0.34, 0.18), position=(-0.52, -0.12, 0.28), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.34, 0.18), position=(0.52, -0.12, 0.28), color=self.style["panel"])
        self._add_detail(scale=(0.14, 0.18, 0.56), position=(-0.76, -0.14, -0.12), color=self.style["panel"])
        self._add_detail(scale=(0.14, 0.18, 0.56), position=(0.76, -0.14, -0.12), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.08, 0.18), position=(0, 0.92, -0.46), color=self.style["accent"])

    def _aim_visuals(self, target):
        direction = Vec3(target.x - self.x, 0, target.z - self.z)
        if direction.length() <= 0.01:
            return
        target_heading = degrees(atan2(direction.x, direction.z))
        self.turret.rotation_y = lerp(self.turret.rotation_y, target_heading, min(1, time.dt * 10))

    def _attack_flash_parent(self):
        return self.barrel

    def _attack_flash_position(self):
        return (0, 0, 0.38)

    def _attack_flash_scale(self):
        return (0.14, 0.1, 0.18)
