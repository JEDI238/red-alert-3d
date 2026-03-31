import sys
from pathlib import Path
from math import atan2, degrees

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ursina import Cone, Cylinder, Entity, Vec3, color, destroy, lerp, time
from factions import get_faction_theme


class Building(Entity):
    display_name = "Building"
    cost = 0
    base_tint = color.rgb32(96, 103, 112)
    size = (2, 2, 2)
    visual_rotation_y = 38
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
        self.visual_root = Entity(parent=self, rotation_y=self.visual_rotation_y, collider=None)
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
            parent=self.visual_root,
            model=model,
            scale=scale,
            position=position,
            color=color if color is not None else self.base_color,
            rotation=rotation,
            collider=None,
        )
        self.visual_parts.append(detail)
        return detail

    def _add_pipe(self, *, position=(0, 0, 0), length=0.6, radius=0.06, axis="x", color=None, resolution=14):
        if axis == "x":
            rotation = (0, 0, 90)
        elif axis == "z":
            rotation = (90, 0, 0)
        else:
            rotation = (0, 0, 0)
        return self._add_detail(
            scale=(radius * 2, length, radius * 2),
            position=position,
            color=color,
            rotation=rotation,
            model=Cylinder(resolution, start=-0.5),
        )

    def _add_light_beacon(
        self,
        *,
        position=(0, 0, 0),
        radius=0.08,
        base_height=0.07,
        stem_height=0.06,
        base_color=None,
        glow_color=None,
    ):
        x, y, z = position
        base_color = base_color if base_color is not None else self.style["metal"]
        glow_color = glow_color if glow_color is not None else self.style["glow"]
        self._add_detail(
            scale=(radius * 1.6, base_height, radius * 1.6),
            position=(x, y - stem_height - (base_height / 2), z),
            color=base_color,
            model=Cylinder(14, start=-0.5),
        )
        self._add_detail(
            scale=(radius * 0.9, stem_height, radius * 0.9),
            position=(x, y - (stem_height / 2), z),
            color=base_color,
            model=Cylinder(12, start=-0.5),
        )
        self._add_detail(scale=(radius * 1.12, radius * 1.12, radius * 1.12), position=position, color=glow_color, model="sphere")

    def _add_corner_posts(
        self,
        *,
        footprint=(1.0, 1.0),
        y=0.0,
        height=0.4,
        thickness=0.08,
        inset=0.0,
        color=None,
        cap_color=None,
    ):
        half_x = max(0.0, (footprint[0] / 2) - inset)
        half_z = max(0.0, (footprint[1] / 2) - inset)
        cap_height = max(0.04, thickness * 0.55)
        for post_x in (-half_x, half_x):
            for post_z in (-half_z, half_z):
                self._add_detail(scale=(thickness, height, thickness), position=(post_x, y, post_z), color=color)
                if cap_color is not None:
                    self._add_detail(
                        scale=(thickness * 1.3, cap_height, thickness * 1.3),
                        position=(post_x, y + (height / 2) + (cap_height / 2), post_z),
                        color=cap_color,
                    )

    def _add_perimeter_trim(self, *, footprint=(1.0, 1.0), y=0.0, thickness=0.06, edge=0.08, inset=0.0, color=None):
        width = max(0.12, footprint[0] - (inset * 2))
        depth = max(0.12, footprint[1] - (inset * 2))
        strip_z = max(0.0, (depth / 2) - (edge / 2))
        strip_x = max(0.0, (width / 2) - (edge / 2))
        self._add_detail(scale=(width, thickness, edge), position=(0, y, strip_z), color=color)
        self._add_detail(scale=(width, thickness, edge), position=(0, y, -strip_z), color=color)
        self._add_detail(scale=(edge, thickness, depth), position=(strip_x, y, 0), color=color)
        self._add_detail(scale=(edge, thickness, depth), position=(-strip_x, y, 0), color=color)

    def _add_vent_bank(
        self,
        *,
        position=(0, 0, 0),
        count=3,
        spacing=0.16,
        size=(0.1, 0.16, 0.18),
        axis="x",
        color=None,
        cap_color=None,
    ):
        x, y, z = position
        origin = -((count - 1) * spacing) / 2
        for index in range(count):
            offset = origin + (index * spacing)
            vent_x = x + offset if axis == "x" else x
            vent_z = z + offset if axis == "z" else z
            self._add_detail(scale=size, position=(vent_x, y, vent_z), color=color)
            if cap_color is not None:
                self._add_detail(
                    scale=(size[0] * 1.08, max(0.04, size[1] * 0.22), size[2] * 1.08),
                    position=(vent_x, y + (size[1] / 2) + max(0.025, size[1] * 0.12), vent_z),
                    color=cap_color,
                )

    def _add_stack_tower(
        self,
        *,
        position=(0, 0, 0),
        height=0.9,
        radius=0.18,
        segments=4,
        taper=0.86,
        color=None,
        cap_color=None,
        emitter=False,
    ):
        x, y, z = position
        segment_height = height / max(1, segments)
        segment_y = y - (height / 2) + (segment_height / 2)
        current_radius = radius
        for _ in range(segments):
            self._add_detail(
                scale=(current_radius * 2, segment_height, current_radius * 2),
                position=(x, segment_y, z),
                color=color,
                model=Cylinder(16, start=-0.5),
            )
            segment_y += segment_height
            current_radius *= taper
        if cap_color is not None:
            self._add_detail(
                scale=(max(radius * 1.4, current_radius * 2.4), max(0.05, segment_height * 0.25), max(radius * 1.4, current_radius * 2.4)),
                position=(x, y + (height / 2) + max(0.03, segment_height * 0.18), z),
                color=cap_color,
                model=Cylinder(16, start=-0.5),
            )
        if emitter:
            self._add_detail(
                scale=(max(radius * 0.65, 0.1), max(segment_height * 0.6, 0.12), max(radius * 0.65, 0.1)),
                position=(x, y + (height / 2) + max(0.12, segment_height * 0.4), z),
                color=self.style["glow"],
                model=Cone(16, radius=0.5, height=1),
            )

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
        self._add_perimeter_trim(footprint=(1.18, 1.18), y=-0.34, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_perimeter_trim(footprint=(1.0, 1.0), y=0.42, thickness=0.04, edge=0.06, color=self.style["metal"])
        self._add_corner_posts(
            footprint=(1.0, 1.0),
            y=0.02,
            height=0.62,
            thickness=0.09,
            inset=0.06,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
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
        self._add_vent_bank(position=(0, 0.76, 0.18), count=4, spacing=0.18, size=(0.1, 0.14, 0.2), color=self.style["panel"], cap_color=self.style["roof"])
        self._add_pipe(position=(-0.96, -0.16, -0.1), length=0.92, radius=0.05, axis="z", color=self.style["metal"])
        self._add_pipe(position=(0.96, -0.16, -0.1), length=0.92, radius=0.05, axis="z", color=self.style["metal"])
        self._add_pipe(position=(0, 0.92, -0.46), length=0.62, radius=0.04, axis="x", color=self.style["metal"])
        self._add_light_beacon(position=(-0.9, 0.08, 0.86), radius=0.07, glow_color=self.style["accent"])
        self._add_light_beacon(position=(0.9, 0.08, 0.86), radius=0.07, glow_color=self.style["accent"])
        if self.faction_key == "soviet":
            self._add_stack_tower(position=(-0.52, 1.16, -0.52), height=0.78, radius=0.11, segments=4, color=self.style["metal"], cap_color=self.style["glow"], emitter=True)
            self._add_stack_tower(position=(0.52, 1.16, -0.52), height=0.78, radius=0.11, segments=4, color=self.style["metal"], cap_color=self.style["glow"], emitter=True)
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
        self._add_detail(scale=(1.12, 0.04, 1.1), position=(0, -0.5, 0), color=self.style["metal"])
        self._add_perimeter_trim(footprint=(1.18, 1.08), y=-0.32, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_corner_posts(
            footprint=(1.0, 0.98),
            y=-0.02,
            height=0.58,
            thickness=0.08,
            inset=0.06,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
        self._add_detail(scale=(0.76, 0.44, 0.58), position=(-0.46, 0.02, -0.1), color=self.style["body"])
        self._add_detail(scale=(0.76, 0.44, 0.58), position=(0.46, 0.02, -0.1), color=self.style["body"])
        self._add_detail(scale=(0.88, 0.12, 0.82), position=(0, 0.5, -0.06), color=self.style["roof"])
        self._add_detail(scale=(0.92, 0.12, 0.22), position=(0, -0.04, 0.96), color=self.style["accent"])
        self._add_detail(scale=(0.98, 0.06, 0.14), position=(0, 0.1, 1.12), color=self.style["glow"])
        self._add_detail(scale=(0.22, 0.54, 0.22), position=(-0.94, 0.1, -0.26), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.54, 0.22), position=(0.94, 0.1, -0.26), color=self.style["panel"])
        self._add_detail(scale=(0.24, 0.24, 1.04), position=(-1.02, -0.18, 0.0), color=self.style["metal"])
        self._add_detail(scale=(0.24, 0.24, 1.04), position=(1.02, -0.18, 0.0), color=self.style["metal"])
        self._add_detail(scale=(0.2, 0.16, 0.72), position=(0, 0.28, 0.48), color=self.style["panel"])
        self._add_vent_bank(position=(0, 0.7, 0.12), count=4, spacing=0.16, size=(0.1, 0.18, 0.14), color=self.style["metal"], cap_color=self.style["roof"])
        self._add_pipe(position=(-0.46, 0.36, 0.3), length=0.96, radius=0.05, axis="x", color=self.style["metal"])
        self._add_pipe(position=(0.46, 0.36, 0.3), length=0.96, radius=0.05, axis="x", color=self.style["metal"])
        self._add_pipe(position=(0.0, 0.02, -0.84), length=1.28, radius=0.05, axis="x", color=self.style["panel"])
        self._add_light_beacon(position=(-0.86, 0.34, 0.84), radius=0.065, glow_color=self.style["glow"])
        self._add_light_beacon(position=(0.86, 0.34, 0.84), radius=0.065, glow_color=self.style["glow"])
        if self.faction_key == "soviet":
            self._add_stack_tower(position=(-0.26, 1.04, 0.16), height=0.78, radius=0.1, segments=4, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_stack_tower(position=(0.26, 1.04, 0.16), height=0.78, radius=0.1, segments=4, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_detail(scale=(0.34, 0.46, 0.34), position=(0, 0.84, -0.18), color=self.style["accent"])
            self._add_detail(scale=(0.12, 0.92, 0.12), position=(0.0, 1.18, 0.26), color=self.style["metal"])
            self._add_detail(scale=(0.52, 0.08, 0.14), position=(0, 0.22, 1.0), color=self.style["glow"])
            self._add_detail(scale=(0.24, 0.18, 0.56), position=(-0.62, 0.12, -0.84), color=self.style["panel"])
            self._add_detail(scale=(0.24, 0.18, 0.56), position=(0.62, 0.12, -0.84), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.46, 0.12, 0.74), position=(0, 0.94, -0.18), color=self.style["accent"])
            self._add_detail(scale=(0.14, 0.72, 0.14), position=(0.0, 1.04, 0.22), color=self.style["metal"])
            self._add_detail(scale=(0.48, 0.08, 0.14), position=(0, 0.22, 1.0), color=self.style["glow"])
            self._add_detail(scale=(0.26, 0.16, 0.62), position=(0.72, 0.1, -0.84), color=self.style["panel"])
            self._add_detail(scale=(0.18, 0.16, 0.48), position=(-0.72, 0.14, -0.78), color=self.style["panel"])


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
        self._add_detail(scale=(1.08, 0.04, 1.1), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_perimeter_trim(footprint=(1.1, 1.12), y=-0.34, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_corner_posts(
            footprint=(0.98, 1.02),
            y=-0.06,
            height=0.46,
            thickness=0.08,
            inset=0.04,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
        self._add_detail(scale=(0.84, 0.34, 0.82), position=(0, -0.04, 0.02), color=self.style["body"])
        self._add_detail(scale=(0.9, 0.1, 0.86), position=(0, 0.5, 0.02), color=self.style["roof"])
        self._add_detail(scale=(0.42, 0.48, 0.18), position=(0, -0.02, 0.76), color=self.style["metal"])
        self._add_detail(scale=(0.28, 0.24, 0.08), position=(-0.24, 0.06, 0.82), color=self.style["accent"])
        self._add_detail(scale=(0.28, 0.24, 0.08), position=(0.24, 0.06, 0.82), color=self.style["accent"])
        self._add_detail(scale=(0.26, 0.44, 0.42), position=(-0.54, -0.06, -0.06), color=self.style["panel"])
        self._add_detail(scale=(0.26, 0.44, 0.42), position=(0.54, -0.06, -0.06), color=self.style["panel"])
        self._add_detail(scale=(0.64, 0.14, 0.18), position=(0, 0.14, -0.72), color=self.style["panel"])
        self._add_detail(scale=(0.62, 0.05, 0.18), position=(0, 0.38, 0.94), color=self.style["glow"])
        self._add_detail(scale=(0.18, 0.18, 0.08), position=(-0.54, -0.22, 0.84), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.18, 0.08), position=(0.54, -0.22, 0.84), color=self.style["metal"])
        self._add_vent_bank(position=(0, 0.64, -0.02), count=3, spacing=0.2, size=(0.12, 0.14, 0.24), color=self.style["panel"], cap_color=self.style["roof"])
        self._add_pipe(position=(-0.84, -0.12, 0.0), length=0.82, radius=0.045, axis="z", color=self.style["metal"])
        self._add_pipe(position=(0.84, -0.12, 0.0), length=0.82, radius=0.045, axis="z", color=self.style["metal"])
        self._add_light_beacon(position=(-0.7, 0.18, 0.84), radius=0.06, glow_color=self.style["accent"])
        self._add_light_beacon(position=(0.7, 0.18, 0.84), radius=0.06, glow_color=self.style["accent"])
        if self.faction_key == "soviet":
            self._add_stack_tower(position=(-0.42, 0.92, -0.42), height=0.56, radius=0.08, segments=3, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_stack_tower(position=(0.42, 0.92, -0.42), height=0.56, radius=0.08, segments=3, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_detail(scale=(0.14, 0.74, 0.14), position=(-0.42, 0.74, -0.34), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.74, 0.14), position=(0.42, 0.74, -0.34), color=self.style["metal"])
            self._add_detail(scale=(0.44, 0.08, 0.14), position=(0, 0.24, 0.72), color=self.style["glow"])
            self._add_detail(scale=(0.14, 0.54, 0.14), position=(0, 0.9, 0.12), color=self.style["accent"])
            self._add_detail(scale=(0.18, 0.2, 0.62), position=(0, 0.58, -0.84), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.08, 0.62, 0.08), position=(0.42, 0.7, -0.32), color=self.style["metal"])
            self._add_detail(scale=(0.2, 0.08, 0.2), position=(0.42, 1.04, -0.32), color=self.style["glow"])
            self._add_detail(scale=(0.5, 0.08, 0.14), position=(0, 0.28, 0.72), color=self.style["glow"])
            self._add_detail(scale=(0.3, 0.08, 0.3), position=(-0.5, 0.74, 0.02), color=self.style["accent"])
            self._add_detail(scale=(0.18, 0.16, 0.62), position=(-0.76, 0.1, -0.64), color=self.style["panel"])
            self._add_detail(scale=(0.12, 0.16, 0.52), position=(0.76, 0.12, -0.58), color=self.style["panel"])


class Radar(Building):
    display_name = "Radar"
    cost = 450
    base_tint = color.rgb32(112, 119, 129)
    size = (2.7, 2.0, 2.9)
    placement_y = 1.0
    default_health = 980
    selection_ring_scale = 1.1

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(126, 72, 66),
                "roof": color.rgb32(169, 93, 85),
                "metal": color.rgb32(78, 73, 76),
                "accent": self.faction.accent,
                "panel": color.rgb32(96, 48, 43),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(83, 118, 159),
            "roof": color.rgb32(154, 184, 212),
            "metal": color.rgb32(74, 89, 111),
            "accent": self.faction.accent,
            "panel": color.rgb32(49, 73, 103),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.12, 0.04, 1.08), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_perimeter_trim(footprint=(1.14, 1.08), y=-0.34, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_corner_posts(
            footprint=(1.02, 0.98),
            y=0.02,
            height=0.64,
            thickness=0.08,
            inset=0.06,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
        self._add_detail(scale=(0.88, 0.36, 0.68), position=(0, 0.04, -0.18), color=self.style["body"])
        self._add_detail(scale=(0.94, 0.1, 0.74), position=(0, 0.48, -0.12), color=self.style["roof"])
        self._add_detail(scale=(0.88, 0.08, 0.16), position=(0, -0.04, 0.98), color=self.style["glow"])
        self._add_detail(scale=(0.24, 0.58, 0.24), position=(-0.78, 0.04, 0.22), color=self.style["panel"])
        self._add_detail(scale=(0.24, 0.58, 0.24), position=(0.78, 0.04, 0.22), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.92, 0.22), position=(0, 0.8, 0.18), color=self.style["metal"])
        self._add_detail(scale=(0.62, 0.08, 0.18), position=(0, 0.38, 0.66), color=self.style["accent"])
        self._add_detail(scale=(0.54, 0.12, 0.78), position=(0, 0.78, -0.28), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.22, 0.72), position=(-0.96, -0.18, -0.08), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.22, 0.72), position=(0.96, -0.18, -0.08), color=self.style["metal"])
        self._add_vent_bank(position=(0, 0.7, -0.56), count=3, spacing=0.18, size=(0.12, 0.16, 0.16), color=self.style["metal"], cap_color=self.style["roof"])
        self._add_pipe(position=(-0.94, -0.1, -0.12), length=0.96, radius=0.045, axis="z", color=self.style["metal"])
        self._add_pipe(position=(0.94, -0.1, -0.12), length=0.96, radius=0.045, axis="z", color=self.style["metal"])
        self._add_light_beacon(position=(-0.92, 0.28, 0.76), radius=0.06, glow_color=self.style["accent"])
        self._add_light_beacon(position=(0.92, 0.28, 0.76), radius=0.06, glow_color=self.style["accent"])
        dish_mount = self._add_detail(scale=(0.16, 0.28, 0.16), position=(0, 1.16, 0.2), color=self.style["accent"])
        self._add_detail(scale=(0.26, 0.08, 0.26), position=(0, 1.0, 0.2), color=self.style["metal"], model=Cylinder(14, start=-0.5))
        self._add_pipe(position=(-0.12, 1.0, 0.16), length=0.28, radius=0.03, axis="x", color=self.style["metal"])
        self._add_pipe(position=(0.12, 1.0, 0.16), length=0.28, radius=0.03, axis="x", color=self.style["metal"])
        self._add_pipe(position=(0, 1.0, 0.04), length=0.26, radius=0.03, axis="z", color=self.style["metal"])
        dish = Entity(
            parent=dish_mount,
            model="quad",
            scale=(0.72, 0.72),
            position=(0, 0.14, -0.08),
            rotation=(58, 0, 0),
            color=self.style["glow"],
            collider=None,
        )
        self.visual_parts.append(dish)
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.14, 0.82, 0.14), position=(-0.46, 0.98, -0.58), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.82, 0.14), position=(0.46, 0.98, -0.58), color=self.style["metal"])
            self._add_detail(scale=(0.38, 0.08, 0.38), position=(0, 1.44, 0.12), color=self.style["accent"])
        else:
            self._add_detail(scale=(0.48, 0.08, 0.16), position=(0, 0.9, -0.82), color=self.style["glow"])
            self._add_detail(scale=(0.22, 0.18, 0.62), position=(0.82, 0.18, -0.66), color=self.style["panel"])
            self._add_detail(scale=(0.22, 0.18, 0.62), position=(-0.82, 0.18, -0.66), color=self.style["panel"])


class Airfield(Building):
    display_name = "Air Base"
    cost = 450
    base_tint = color.rgb32(101, 114, 128)
    size = (3.55, 1.7, 3.8)
    placement_y = 0.85
    default_health = 1080
    selection_ring_scale = 1.13

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(127, 75, 68),
                "roof": color.rgb32(168, 95, 86),
                "metal": color.rgb32(78, 73, 76),
                "accent": self.faction.accent,
                "panel": color.rgb32(97, 51, 45),
                "glow": self.faction.glow,
            }

        return {
            "body": color.rgb32(82, 118, 160),
            "roof": color.rgb32(154, 185, 214),
            "metal": color.rgb32(74, 90, 113),
            "accent": self.faction.accent,
            "panel": color.rgb32(48, 73, 103),
            "glow": self.faction.glow,
        }

    def _build_visuals(self):
        self._add_detail(scale=(1.12, 0.04, 1.12), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_perimeter_trim(footprint=(1.16, 1.16), y=-0.34, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_perimeter_trim(footprint=(0.96, 0.96), y=0.28, thickness=0.04, edge=0.06, color=self.style["metal"])
        self._add_corner_posts(
            footprint=(1.02, 1.04),
            y=-0.08,
            height=0.34,
            thickness=0.08,
            inset=0.06,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
        self._add_detail(scale=(0.96, 0.18, 0.94), position=(0, -0.08, 0), color=self.style["body"])
        self._add_detail(scale=(0.92, 0.08, 0.9), position=(0, 0.22, 0), color=self.style["roof"])
        self._add_detail(scale=(0.98, 0.04, 0.16), position=(0, 0.1, 0.0), color=self.style["glow"])
        self._add_detail(scale=(0.16, 0.04, 0.98), position=(0, 0.1, 0.0), color=self.style["glow"])
        self._add_detail(scale=(0.94, 0.04, 0.16), position=(0, 0.12, 1.1), color=self.style["accent"])
        self._add_detail(scale=(0.94, 0.04, 0.16), position=(0, 0.12, -1.1), color=self.style["accent"])
        self._add_detail(scale=(0.22, 0.42, 0.22), position=(-1.08, -0.08, -0.5), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.42, 0.22), position=(1.08, -0.08, -0.5), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.42, 0.22), position=(-1.08, -0.08, 0.5), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.42, 0.22), position=(1.08, -0.08, 0.5), color=self.style["panel"])
        self._add_detail(scale=(0.58, 0.28, 0.34), position=(-0.96, 0.22, -0.94), color=self.style["panel"])
        self._add_detail(scale=(0.18, 0.62, 0.18), position=(-0.98, 0.72, -0.96), color=self.style["metal"])
        self._add_detail(scale=(0.34, 0.08, 0.34), position=(-0.98, 1.06, -0.96), color=self.style["glow"])
        self._add_vent_bank(position=(0.0, 0.36, -0.92), count=5, spacing=0.16, size=(0.08, 0.14, 0.18), color=self.style["metal"], cap_color=self.style["roof"])
        self._add_pipe(position=(1.08, -0.08, 0.0), length=1.18, radius=0.045, axis="z", color=self.style["metal"])
        self._add_pipe(position=(-1.08, -0.08, 0.0), length=1.18, radius=0.045, axis="z", color=self.style["metal"])
        self._add_light_beacon(position=(-1.14, 0.08, -1.1), radius=0.055, glow_color=self.style["glow"])
        self._add_light_beacon(position=(1.14, 0.08, -1.1), radius=0.055, glow_color=self.style["glow"])
        self._add_light_beacon(position=(-1.14, 0.08, 1.1), radius=0.055, glow_color=self.style["glow"])
        self._add_light_beacon(position=(1.14, 0.08, 1.1), radius=0.055, glow_color=self.style["glow"])
        if self.faction_key == "soviet":
            self._add_detail(scale=(0.54, 0.08, 0.16), position=(0, 0.26, 0.86), color=self.style["glow"])
            self._add_detail(scale=(0.24, 0.18, 0.82), position=(1.0, 0.04, -0.18), color=self.style["panel"])
        else:
            self._add_stack_tower(position=(-1.02, 0.86, -0.98), height=0.52, radius=0.09, segments=3, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_detail(scale=(0.58, 0.08, 0.18), position=(0, 0.26, 0.86), color=self.style["glow"])
            self._add_detail(scale=(0.24, 0.18, 0.88), position=(1.0, 0.04, -0.12), color=self.style["panel"])
            self._add_detail(scale=(0.22, 0.06, 0.64), position=(-0.22, 0.38, 0.0), color=self.style["accent"])


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
        self._add_detail(scale=(1.12, 0.04, 1.12), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_perimeter_trim(footprint=(1.16, 1.16), y=-0.34, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_corner_posts(
            footprint=(1.06, 1.06),
            y=-0.02,
            height=0.48,
            thickness=0.08,
            inset=0.08,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
        if self.faction_key == "soviet":
            warning_red = color.rgb32(214, 78, 60)
            dark_panel = color.rgb32(62, 44, 37)
            coil_model = Cylinder(18, start=-0.5)
            stack_model = Cylinder(16, start=-0.5)
            emitter_model = Cone(18, radius=0.5, height=1)

            self._add_detail(scale=(1.54, 0.42, 1.36), position=(0.0, -0.12, 0.02), color=self.style["body"])
            self._add_detail(scale=(1.36, 0.12, 1.08), position=(0.0, 0.18, 0.0), color=self.style["roof"])
            self._add_detail(scale=(0.74, 0.38, 0.54), position=(0.0, 0.08, -0.22), color=self.style["panel"])

            self._add_detail(scale=(0.46, 0.56, 0.28), position=(0.0, -0.04, 0.72), color=dark_panel)
            self._add_detail(scale=(0.3, 0.54, 0.08), position=(0.0, -0.02, 0.88), color=self.style["accent"])
            self._add_detail(scale=(0.1, 0.5, 0.1), position=(-0.12, -0.04, 0.86), color=self.style["roof"])
            self._add_detail(scale=(0.1, 0.5, 0.1), position=(0.12, -0.04, 0.86), color=self.style["roof"])
            self._add_detail(scale=(0.34, 0.2, 0.12), position=(0.0, 0.14, 0.56), color=self.style["roof"])

            self._add_detail(scale=(0.34, 0.52, 0.46), position=(-0.78, -0.06, 0.34), color=self.style["panel"])
            self._add_detail(scale=(0.34, 0.52, 0.46), position=(0.78, -0.06, 0.34), color=self.style["panel"])
            self._add_detail(scale=(0.18, 0.12, 0.18), position=(-0.78, 0.18, 0.72), color=self.style["metal"], model=coil_model)
            self._add_detail(scale=(0.18, 0.12, 0.18), position=(0.78, 0.18, 0.72), color=self.style["metal"], model=coil_model)
            self._add_detail(scale=(0.14, 0.14, 0.14), position=(-0.78, 0.3, 0.72), color=warning_red, model="sphere")
            self._add_detail(scale=(0.14, 0.14, 0.14), position=(0.78, 0.3, 0.72), color=warning_red, model="sphere")

            self._add_detail(scale=(0.3, 0.34, 0.52), position=(-0.86, -0.08, -0.02), color=self.style["panel"])
            self._add_detail(scale=(0.3, 0.34, 0.52), position=(0.86, -0.08, -0.02), color=self.style["panel"])
            self._add_detail(scale=(0.14, 0.1, 0.14), position=(-0.58, 0.14, -0.16), color=self.style["metal"], model=coil_model)
            self._add_detail(scale=(0.14, 0.1, 0.14), position=(0.58, 0.14, -0.16), color=self.style["metal"], model=coil_model)
            self._add_detail(scale=(0.12, 0.12, 0.12), position=(-0.58, 0.24, -0.16), color=warning_red, model="sphere")
            self._add_detail(scale=(0.12, 0.12, 0.12), position=(0.58, 0.24, -0.16), color=warning_red, model="sphere")

            self._add_detail(scale=(0.56, 0.12, 0.34), position=(0.0, 0.38, 0.02), color=self.style["roof"])
            self._add_detail(scale=(0.42, 0.12, 0.26), position=(0.0, 0.5, -0.02), color=self.style["body"])
            self._add_detail(scale=(0.3, 0.12, 0.18), position=(0.0, 0.62, -0.06), color=self.style["roof"])
            self._add_detail(scale=(0.14, 0.14, 0.34), position=(0.0, 0.7, -0.06), color=self.style["metal"])

            outer_tower_segments = (
                ((0.34, 0.18, 0.34), 0.34),
                ((0.3, 0.16, 0.3), 0.52),
                ((0.26, 0.16, 0.26), 0.68),
                ((0.22, 0.18, 0.22), 0.86),
                ((0.18, 0.24, 0.18), 1.08),
            )
            for tower_x in (-0.62, 0.62):
                self._add_detail(scale=(0.1, 1.28, 0.1), position=(tower_x, 0.92, -0.26), color=self.style["panel"], model=stack_model)
                for scale, y in outer_tower_segments:
                    self._add_detail(scale=scale, position=(tower_x, y, -0.26), color=self.style["metal"], model=coil_model)
                self._add_detail(scale=(0.22, 0.18, 0.22), position=(tower_x, 1.32, -0.26), color=self.style["accent"], model=coil_model)
                self._add_detail(scale=(0.16, 0.2, 0.16), position=(tower_x, 1.52, -0.26), color=self.style["glow"], model=emitter_model)
                self._add_detail(scale=(0.34, 0.04, 0.34), position=(tower_x, 1.4, -0.26), color=self.style["glow"], model=coil_model)

            center_tower_segments = (
                ((0.4, 0.18, 0.4), 0.48),
                ((0.34, 0.16, 0.34), 0.66),
                ((0.28, 0.16, 0.28), 0.84),
                ((0.22, 0.22, 0.22), 1.04),
            )
            self._add_detail(scale=(0.12, 1.16, 0.12), position=(0.0, 0.9, -0.14), color=self.style["panel"], model=stack_model)
            for scale, y in center_tower_segments:
                self._add_detail(scale=scale, position=(0.0, y, -0.14), color=self.style["metal"], model=coil_model)
            self._add_detail(scale=(0.3, 0.12, 0.3), position=(0.0, 1.2, -0.14), color=self.style["roof"], model=coil_model)
            self._add_detail(scale=(0.2, 0.18, 0.2), position=(0.0, 1.38, -0.14), color=self.style["accent"], model=emitter_model)

            self._add_detail(scale=(0.44, 0.05, 0.05), position=(-0.3, 1.52, -0.26), color=self.style["glow"])
            self._add_detail(scale=(0.44, 0.05, 0.05), position=(0.3, 1.52, -0.26), color=self.style["glow"])
            self._add_detail(scale=(0.18, 0.05, 0.05), position=(0.0, 1.56, -0.18), color=self.style["glow"])

            self._add_detail(scale=(0.92, 0.08, 0.14), position=(0.0, -0.02, 0.98), color=self.style["panel"])
            self._add_detail(scale=(1.0, 0.06, 0.08), position=(0.0, 0.08, 1.08), color=self.style["glow"])
            self._add_vent_bank(position=(0.0, 0.28, -0.54), count=4, spacing=0.16, size=(0.1, 0.16, 0.16), color=self.style["panel"], cap_color=self.style["roof"])
            self._add_pipe(position=(-0.98, -0.1, -0.08), length=1.1, radius=0.05, axis="z", color=self.style["metal"])
            self._add_pipe(position=(0.98, -0.1, -0.08), length=1.1, radius=0.05, axis="z", color=self.style["metal"])
            self._add_pipe(position=(0.0, 0.42, 0.32), length=0.74, radius=0.045, axis="x", color=self.style["metal"])
            self._add_light_beacon(position=(-0.98, 0.28, 0.86), radius=0.06, glow_color=warning_red)
            self._add_light_beacon(position=(0.98, 0.28, 0.86), radius=0.06, glow_color=warning_red)
            return
        else:
            self._add_detail(scale=(0.52, 0.54, 0.52), position=(0, 0.04, 0), color=self.style["accent"])
            self._add_detail(scale=(0.26, 0.48, 0.26), position=(-0.44, -0.02, 0.36), color=self.style["panel"])
            self._add_detail(scale=(0.26, 0.48, 0.26), position=(0.44, -0.02, 0.36), color=self.style["panel"])
            self._add_detail(scale=(0.94, 0.08, 0.16), position=(0, 0.08, 0.56), color=self.style["panel"])
            self._add_detail(scale=(0.62, 0.08, 0.08), position=(0, 0.32, 0.12), color=self.style["glow"])
            self._add_detail(scale=(0.18, 0.2, 0.84), position=(0, 0.58, 0.02), color=self.style["accent"])
            self._add_detail(scale=(0.62, 0.06, 0.06), position=(0, -0.06, 0.84), color=self.style["panel"])
            self._add_detail(scale=(0.14, 0.82, 0.14), position=(-0.28, 0.76, -0.3), color=self.style["metal"])
            self._add_detail(scale=(0.14, 0.82, 0.14), position=(0.28, 0.76, -0.3), color=self.style["metal"])
            self._add_detail(scale=(0.22, 0.08, 0.22), position=(-0.28, 1.18, -0.3), color=self.style["glow"])
            self._add_detail(scale=(0.22, 0.08, 0.22), position=(0.28, 1.18, -0.3), color=self.style["glow"])
            self._add_detail(scale=(0.86, 0.08, 0.08), position=(0, 0.48, -0.52), color=self.style["accent"])
            self._add_detail(scale=(0.46, 0.06, 0.12), position=(0, 0.88, 0.44), color=self.style["glow"])
            self._add_vent_bank(position=(0.0, 0.18, -0.48), count=3, spacing=0.18, size=(0.12, 0.16, 0.18), color=self.style["metal"], cap_color=self.style["roof"])
            self._add_pipe(position=(-0.78, -0.08, 0.1), length=0.92, radius=0.045, axis="z", color=self.style["metal"])
            self._add_pipe(position=(0.78, -0.08, 0.1), length=0.92, radius=0.045, axis="z", color=self.style["metal"])
            self._add_light_beacon(position=(-0.88, 0.24, 0.74), radius=0.055, glow_color=self.style["glow"])
            self._add_light_beacon(position=(0.88, 0.24, 0.74), radius=0.055, glow_color=self.style["glow"])


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
        self._add_detail(scale=(1.14, 0.04, 1.08), position=(0, -0.52, 0), color=self.style["metal"])
        self._add_perimeter_trim(footprint=(1.18, 1.12), y=-0.34, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_corner_posts(
            footprint=(1.06, 0.98),
            y=-0.02,
            height=0.62,
            thickness=0.08,
            inset=0.08,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
        self._add_detail(scale=(0.98, 0.42, 0.56), position=(0, 0.02, -0.48), color=self.style["body"])
        self._add_detail(scale=(1.0, 0.12, 0.6), position=(0, 0.5, -0.42), color=self.style["roof"])
        self._add_detail(scale=(0.86, 0.24, 0.22), position=(0, -0.04, 1.02), color=self.style["accent"])
        self._add_detail(scale=(1.02, 0.08, 0.12), position=(0, -0.16, 1.26), color=self.style["glow"])
        self._add_detail(scale=(0.24, 0.66, 0.24), position=(-0.82, 0.08, 0.18), color=self.style["panel"])
        self._add_detail(scale=(0.24, 0.66, 0.24), position=(0.82, 0.08, 0.18), color=self.style["panel"])
        self._add_detail(scale=(0.18, 1.06, 0.18), position=(-0.98, 0.76, -0.92), color=self.style["metal"])
        self._add_detail(scale=(0.18, 1.06, 0.18), position=(0.98, 0.76, -0.92), color=self.style["metal"])
        self._add_detail(scale=(0.3, 0.14, 0.3), position=(-0.98, 1.34, -0.92), color=self.style["glow"])
        self._add_detail(scale=(0.3, 0.14, 0.3), position=(0.98, 1.34, -0.92), color=self.style["glow"])
        self._add_detail(scale=(0.64, 0.14, 0.22), position=(0, 0.24, 0.56), color=self.style["panel"])
        self._add_detail(scale=(0.22, 0.34, 1.18), position=(-1.14, -0.24, -0.08), color=self.style["metal"])
        self._add_detail(scale=(0.22, 0.34, 1.18), position=(1.14, -0.24, -0.08), color=self.style["metal"])
        self._add_detail(scale=(0.22, 0.18, 0.92), position=(0, 0.42, 0.88), color=self.style["accent"])
        self._add_detail(scale=(0.18, 0.58, 0.18), position=(-0.46, 0.88, 0.14), color=self.style["metal"])
        self._add_detail(scale=(0.18, 0.58, 0.18), position=(0.46, 0.88, 0.14), color=self.style["metal"])
        self._add_vent_bank(position=(0, 0.78, -0.64), count=5, spacing=0.16, size=(0.08, 0.18, 0.18), color=self.style["metal"], cap_color=self.style["roof"])
        self._add_pipe(position=(-1.12, -0.08, 0.0), length=1.4, radius=0.05, axis="z", color=self.style["metal"])
        self._add_pipe(position=(1.12, -0.08, 0.0), length=1.4, radius=0.05, axis="z", color=self.style["metal"])
        self._add_pipe(position=(0, 0.56, 0.28), length=1.02, radius=0.05, axis="x", color=self.style["metal"])
        self._add_light_beacon(position=(-1.02, 0.18, 1.0), radius=0.06, glow_color=self.style["accent"])
        self._add_light_beacon(position=(1.02, 0.18, 1.0), radius=0.06, glow_color=self.style["accent"])
        if self.faction_key == "soviet":
            self._add_stack_tower(position=(-0.96, 0.96, -0.96), height=0.82, radius=0.1, segments=4, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_stack_tower(position=(0.96, 0.96, -0.96), height=0.82, radius=0.1, segments=4, color=self.style["metal"], cap_color=self.style["glow"])
            self._add_detail(scale=(0.46, 0.16, 0.84), position=(0, 0.92, -0.18), color=self.style["accent"])
            self._add_detail(scale=(0.14, 0.68, 0.14), position=(0, 1.12, 0.34), color=self.style["metal"])
            self._add_detail(scale=(0.18, 0.2, 0.82), position=(0.88, 0.08, -1.02), color=self.style["panel"])
            self._add_detail(scale=(0.18, 0.2, 0.82), position=(-0.88, 0.08, -1.02), color=self.style["panel"])
        else:
            self._add_detail(scale=(0.48, 0.12, 0.68), position=(0, 0.94, -0.16), color=self.style["accent"])
            self._add_detail(scale=(0.12, 0.62, 0.12), position=(0, 1.04, 0.3), color=self.style["metal"])
            self._add_detail(scale=(0.78, 0.06, 0.12), position=(0, 1.2, -0.94), color=self.style["glow"])


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
        self._add_perimeter_trim(footprint=(1.12, 1.12), y=-0.32, thickness=0.05, edge=0.08, color=self.style["panel"])
        self._add_corner_posts(
            footprint=(1.0, 1.0),
            y=-0.04,
            height=0.36,
            thickness=0.08,
            inset=0.08,
            color=self.style["panel"],
            cap_color=self.style["roof"],
        )
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
        self._add_detail(scale=(0.52, 0.05, 0.52), position=(0, 0.34, -0.04), color=self.style["metal"], model=Cylinder(14, start=-0.5))
        self._add_pipe(position=(-0.78, -0.04, 0.0), length=0.68, radius=0.04, axis="z", color=self.style["metal"])
        self._add_pipe(position=(0.78, -0.04, 0.0), length=0.68, radius=0.04, axis="z", color=self.style["metal"])
        self._add_light_beacon(position=(-0.72, 0.04, 0.76), radius=0.055, glow_color=self.style["accent"])
        self._add_light_beacon(position=(0.72, 0.04, 0.76), radius=0.055, glow_color=self.style["accent"])

    def _aim_visuals(self, target):
        direction = Vec3(target.x - self.x, 0, target.z - self.z)
        if direction.length() <= 0.01:
            return
        target_heading = degrees(atan2(direction.x, direction.z)) - self.visual_root.rotation_y
        self.turret.rotation_y = lerp(self.turret.rotation_y, target_heading, min(1, time.dt * 10))

    def _attack_flash_parent(self):
        return self.barrel

    def _attack_flash_position(self):
        return (0, 0, 0.38)

    def _attack_flash_scale(self):
        return (0.14, 0.1, 0.18)
