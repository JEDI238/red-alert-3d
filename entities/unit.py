import sys
from pathlib import Path
from math import atan2, degrees

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ursina import Entity, Vec3, color, destroy, lerp, time
from factions import get_faction_theme


class Unit(Entity):
    display_name = "Unit"
    cost = 0
    can_attack = True
    unit_color = color.rgb32(96, 140, 196)
    unit_scale = (1, 1, 1)
    default_speed = 5
    default_health = 100
    default_attack_damage = 10
    default_attack_range = 2.2
    default_attack_cooldown = 1.0
    default_vision_range = 8.5
    selection_color = color.rgb32(255, 201, 102)
    shadow_color = color.rgba32(0, 0, 0, 90)
    selection_ring_alpha = 120
    acceleration = 7.5
    turn_speed = 8
    slow_down_radius = 2.2
    stopping_distance = 0.18
    footprint_radius = 0.9
    avoidance_radius = 1.4
    selection_ring_scale = 1.8
    attack_flash_duration = 0.08
    health_bar_display_time = 3.2
    path_repath_interval = 0.45
    path_retarget_distance = 1.35
    stuck_repath_time = 0.85
    stuck_progress_threshold = 0.18

    def __init__(
        self,
        position=(0, 0.5, 0),
        faction_key="alliance",
        owner="player",
        speed=None,
        health=None,
        damage=None,
        attack_range=None,
        attack_cooldown=None,
        vision_range=None,
        **kwargs,
    ):
        self.faction_key = faction_key
        self.owner = owner
        self.faction = get_faction_theme(faction_key)
        self.selection_color = self.faction.selection
        self.style = self._get_style()
        self.is_destroyed = False
        self.is_selected = False
        super().__init__(
            model="cube",
            color=self.style["body"],
            scale=self.unit_scale,
            position=position,
            collider="box",
            **kwargs,
        )
        self.base_color = self.style["body"]
        self.destination = None
        self.requested_destination = None
        self.path_points = []
        self.velocity = Vec3(0, 0, 0)
        self.speed = speed if speed is not None else self.default_speed
        self.max_health = health if health is not None else self.default_health
        self.health = self.max_health
        self.attack_damage = damage if damage is not None else self.default_attack_damage
        self.attack_range = attack_range if attack_range is not None else self.default_attack_range
        self.attack_cooldown = attack_cooldown if attack_cooldown is not None else self.default_attack_cooldown
        self.vision_range = vision_range if vision_range is not None else self.default_vision_range
        self.attack_timer = 0.0
        self.attack_flash_timer = 0.0
        self.health_bar_timer = 0.0
        self.combat_target = None
        self.forced_target = False
        self.units_provider = lambda: ()
        self.buildings_provider = lambda: ()
        self.route_planner = lambda start, goal, unit_radius: [Vec3(goal.x, start.y, goal.z)]
        self.route_repath_timer = 0.0
        self.ground_y = self.scale_y / 2
        self.position = Vec3(self.x, self.ground_y, self.z)
        self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
        self.stuck_timer = 0.0
        self.visual_parts = []
        self.shadow = Entity(
            parent=self,
            model="plane",
            scale=(self.selection_ring_scale * 0.9, 1, self.selection_ring_scale * 0.9),
            y=-(self.scale_y / 2) + 0.01,
            color=self.shadow_color,
            collider=None,
        )
        self.selection_indicator = Entity(
            parent=self,
            model="plane",
            scale=(self.selection_ring_scale, 1, self.selection_ring_scale),
            y=-(self.scale_y / 2) + 0.02,
            color=color.rgba32(
                self.selection_color.r * 255,
                self.selection_color.g * 255,
                self.selection_color.b * 255,
                self.selection_ring_alpha,
            ),
            collider=None,
            enabled=False,
        )
        self.health_bar_root = Entity(parent=self, y=(self.scale_y / 2) + 0.35, enabled=False)
        self.health_bar_bg = Entity(
            parent=self.health_bar_root,
            model="cube",
            scale=(0.92, 0.06, 0.04),
            color=color.rgba32(18, 18, 22, 210),
            collider=None,
        )
        self.health_bar_fill = Entity(
            parent=self.health_bar_root,
            model="cube",
            scale=(0.84, 0.03, 0.05),
            y=0.005,
            color=color.rgb32(92, 208, 124),
            collider=None,
        )
        self._build_visuals()
        self.attack_flash = Entity(
            parent=self._attack_flash_parent(),
            model="cube",
            scale=self._attack_flash_scale(),
            position=self._attack_flash_position(),
            color=self._attack_flash_color(),
            collider=None,
            enabled=False,
        )
        self._update_health_bar()
        self._refresh_health_bar_visibility()

    def update(self):
        if self.is_destroyed:
            return

        self.shadow.rotation_y = -self.rotation_y
        self.attack_timer = max(0.0, self.attack_timer - time.dt)
        self.health_bar_timer = max(0.0, self.health_bar_timer - time.dt)
        self.route_repath_timer = max(0.0, self.route_repath_timer - time.dt)
        self._refresh_health_bar_visibility()
        self._update_attack_flash()

        if self.can_attack:
            if self.combat_target and not self._is_target_valid(self.combat_target):
                self._clear_combat_target()

            if not self.combat_target and self.destination is None:
                self._acquire_auto_target()

            if self.combat_target and self._update_combat():
                return
        else:
            self._clear_combat_target()

        if self._update_special_behavior():
            return

        self._update_movement()

    def set_navigation_context(self, units_provider, buildings_provider, route_planner=None):
        self.units_provider = units_provider
        self.buildings_provider = buildings_provider
        if route_planner is not None:
            self.route_planner = route_planner

    def command_move(self, destination):
        self._clear_combat_target()
        self._set_navigation_goal(destination, force_repath=True)
        self._on_manual_move()

    def command_attack(self, target):
        if not self.can_attack or not self._is_target_valid(target):
            return
        self.combat_target = target
        self.forced_target = True
        self._clear_navigation_goal()

    def take_damage(self, amount, attacker=None):
        if self.is_destroyed:
            return True
        self.health -= amount
        self._update_health_bar()
        self._show_health_bar(duration=self.health_bar_display_time)
        if self.can_attack and attacker and getattr(attacker, "owner", self.owner) != self.owner and not self.forced_target:
            self.combat_target = attacker
            self.route_repath_timer = 0.0
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

    def select(self):
        self.is_selected = True
        self.selection_indicator.enabled = True
        self._show_health_bar()

    def deselect(self):
        self.is_selected = False
        self.selection_indicator.enabled = False
        self._refresh_health_bar_visibility()

    def get_selection_summary(self):
        return f"{self.display_name} ({max(0, int(self.health))} hp)"

    def _show_health_bar(self, duration=None):
        if duration is None:
            self.health_bar_timer = max(self.health_bar_timer, self.health_bar_display_time)
        else:
            self.health_bar_timer = max(self.health_bar_timer, duration)
        self._refresh_health_bar_visibility()

    def _refresh_health_bar_visibility(self):
        self.health_bar_root.enabled = self.is_selected or self.health_bar_timer > 0

    def _update_movement(self):
        if self.destination is None and self.path_points:
            self.destination = self.path_points.pop(0)

        if not self.destination:
            self.velocity = lerp(self.velocity, Vec3(0, 0, 0), min(1, time.dt * 6))
            self.stuck_timer = 0.0
            self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
            self._update_visuals(Vec3(0, 0, 0))
            return

        target_vector = Vec3(self.destination.x - self.x, 0, self.destination.z - self.z)
        distance_to_target = target_vector.length()

        if distance_to_target <= self.stopping_distance:
            self.position = Vec3(self.destination.x, self.ground_y, self.destination.z)
            if self.path_points:
                self.destination = self.path_points.pop(0)
                self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
                self.stuck_timer = 0.0
                return
            self._clear_navigation_goal()
            self.velocity = Vec3(0, 0, 0)
            self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
            self.stuck_timer = 0.0
            self._update_visuals(Vec3(0, 0, 0))
            return

        desired_speed = self.speed
        if distance_to_target < self.slow_down_radius:
            desired_speed *= max(0.35, distance_to_target / self.slow_down_radius)

        desired_velocity = target_vector.normalized() * desired_speed
        avoidance = self._compute_unit_avoidance() + self._compute_building_avoidance()
        if avoidance.length() > 0.01:
            desired_velocity += avoidance.normalized() * min(self.speed * 0.9, avoidance.length())

        self.velocity = lerp(self.velocity, desired_velocity, min(1, time.dt * self.acceleration))
        horizontal_velocity = Vec3(self.velocity.x, 0, self.velocity.z)
        if horizontal_velocity.length() > self.speed:
            horizontal_velocity = horizontal_velocity.normalized() * self.speed

        step = horizontal_velocity * time.dt
        if step.length() > distance_to_target:
            step = target_vector

        self.position += Vec3(step.x, 0, step.z)
        self.y = self.ground_y
        self.velocity = horizontal_velocity

        if horizontal_velocity.length() > 0.025:
            self._rotate_towards(horizontal_velocity)

        self._update_visuals(horizontal_velocity)
        self._update_stuck_progress(horizontal_velocity)

    def _update_combat(self):
        target_position = self._target_position(self.combat_target)
        target_vector = Vec3(target_position.x - self.x, 0, target_position.z - self.z)

        if target_vector.length() > 0.05:
            self._rotate_towards(target_vector)

        if self._distance_to_target(self.combat_target) <= self.attack_range:
            self._clear_navigation_goal()
            self.velocity = lerp(self.velocity, Vec3(0, 0, 0), min(1, time.dt * 8))
            self._update_visuals(Vec3(0, 0, 0))
            if self.attack_timer <= 0:
                self._fire_at(self.combat_target)
            return True

        requested_delta = 999.0
        if self.requested_destination is not None:
            requested_delta = Vec3(
                self.requested_destination.x - target_position.x,
                0,
                self.requested_destination.z - target_position.z,
            ).length()

        if self.requested_destination is None or requested_delta > self.path_retarget_distance or self.route_repath_timer <= 0:
            self._set_navigation_goal(target_position, force_repath=True)
        return False

    def _fire_at(self, target):
        self.attack_timer = self.attack_cooldown
        self.attack_flash_timer = self.attack_flash_duration
        self.attack_flash.enabled = True
        if hasattr(target, "take_damage"):
            target.take_damage(self.attack_damage, attacker=self)

    def _acquire_auto_target(self):
        nearest_target = None
        nearest_distance = self.vision_range
        for target in self._iter_enemy_targets():
            target_distance = self._distance_to_target(target)
            if target_distance <= nearest_distance:
                nearest_distance = target_distance
                nearest_target = target

        if nearest_target:
            self.combat_target = nearest_target
            self.forced_target = False

    def _iter_enemy_targets(self):
        for unit in self.units_provider():
            if unit is self or not self._is_target_valid(unit):
                continue
            yield unit

        for building in self.buildings_provider():
            if not self._is_target_valid(building):
                continue
            yield building

    def _clear_combat_target(self):
        self.combat_target = None
        self.forced_target = False

    def _set_navigation_goal(self, destination, force_repath=False):
        goal = Vec3(destination.x, self.ground_y, destination.z)
        self.requested_destination = goal
        if not force_repath and self.destination is not None and self.route_repath_timer > 0:
            return

        route = self.route_planner(Vec3(self.x, self.ground_y, self.z), goal, self.footprint_radius)
        self.path_points = list(route) if route else [goal]
        self.destination = self.path_points.pop(0) if self.path_points else goal
        self.route_repath_timer = self.path_repath_interval
        self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
        self.stuck_timer = 0.0

    def _clear_navigation_goal(self):
        self.destination = None
        self.requested_destination = None
        self.path_points = []
        self.stuck_timer = 0.0

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
        target_radius = self._target_radius(target)
        return max(0.0, center_vector.length() - target_radius - (self.footprint_radius * 0.25))

    def _target_position(self, target):
        return Vec3(target.x, self.ground_y, target.z)

    def _target_radius(self, target):
        if hasattr(target, "footprint_radius"):
            return target.footprint_radius
        return max(getattr(target, "scale_x", 1), getattr(target, "scale_z", 1)) / 2

    def _rotate_towards(self, direction):
        target_heading = degrees(atan2(direction.x, direction.z))
        self.rotation_y = lerp(self.rotation_y, target_heading, min(1, time.dt * self.turn_speed))

    def _update_stuck_progress(self, horizontal_velocity):
        if self.requested_destination is None or horizontal_velocity.length() <= 0.02:
            self.stuck_timer = 0.0
            self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
            return

        moved_distance = Vec3(self.x - self.last_progress_position.x, 0, self.z - self.last_progress_position.z).length()
        if moved_distance >= self.stuck_progress_threshold:
            self.last_progress_position = Vec3(self.x, self.ground_y, self.z)
            self.stuck_timer = 0.0
            return

        self.stuck_timer += time.dt
        if self.stuck_timer >= self.stuck_repath_time and self.requested_destination is not None:
            self._set_navigation_goal(self.requested_destination, force_repath=True)

    def _compute_unit_avoidance(self):
        push = Vec3(0, 0, 0)
        for other in self.units_provider():
            if other is self or getattr(other, "is_destroyed", False):
                continue

            offset = Vec3(self.x - other.x, 0, self.z - other.z)
            distance_to_other = offset.length()
            min_distance = self.avoidance_radius + other.footprint_radius
            if 0 < distance_to_other < min_distance:
                strength = (min_distance - distance_to_other) / min_distance
                push += offset.normalized() * (strength * self.speed)
        return push

    def _compute_building_avoidance(self):
        push = Vec3(0, 0, 0)
        for building in self.buildings_provider():
            if getattr(building, "is_destroyed", False):
                continue
            inflate_x = (building.scale_x / 2) + self.footprint_radius
            inflate_z = (building.scale_z / 2) + self.footprint_radius
            closest_x = max(building.x - inflate_x, min(self.x, building.x + inflate_x))
            closest_z = max(building.z - inflate_z, min(self.z, building.z + inflate_z))
            offset = Vec3(self.x - closest_x, 0, self.z - closest_z)
            distance_to_building = offset.length()

            if distance_to_building == 0:
                x_penetration = inflate_x - abs(self.x - building.x)
                z_penetration = inflate_z - abs(self.z - building.z)
                if x_penetration < z_penetration:
                    push += Vec3(-1 if self.x < building.x else 1, 0, 0) * self.speed
                else:
                    push += Vec3(0, 0, -1 if self.z < building.z else 1) * self.speed
                continue

            if distance_to_building < self.avoidance_radius:
                strength = (self.avoidance_radius - distance_to_building) / self.avoidance_radius
                push += offset.normalized() * (strength * self.speed)

        return push

    def _update_health_bar(self):
        health_ratio = max(0.0, min(1.0, self.health / max(1, self.max_health)))
        max_width = 0.84
        self.health_bar_fill.scale_x = max_width * health_ratio
        self.health_bar_fill.x = -(max_width - self.health_bar_fill.scale_x) / 2
        if health_ratio > 0.6:
            self.health_bar_fill.color = color.rgb32(92, 208, 124)
        elif health_ratio > 0.3:
            self.health_bar_fill.color = color.rgb32(232, 191, 88)
        else:
            self.health_bar_fill.color = color.rgb32(211, 92, 78)

    def _update_attack_flash(self):
        self.attack_flash_timer = max(0.0, self.attack_flash_timer - time.dt)
        self.attack_flash.enabled = self.attack_flash_timer > 0

    def _attack_flash_parent(self):
        return self

    def _attack_flash_position(self):
        return (0, 0.3, 0.6)

    def _attack_flash_scale(self):
        return (0.18, 0.18, 0.18)

    def _attack_flash_color(self):
        return color.rgba32(255, 219, 112, 220)

    def _add_part(self, *, scale, position=(0, 0, 0), color=None, rotation=(0, 0, 0), model="cube"):
        part = Entity(
            parent=self,
            model=model,
            scale=scale,
            position=position,
            rotation=rotation,
            color=color if color is not None else self.base_color,
            collider=None,
        )
        self.visual_parts.append(part)
        return part

    def _update_special_behavior(self):
        return False

    def _on_manual_move(self):
        pass

    def _build_visuals(self):
        pass

    def _update_visuals(self, horizontal_velocity):
        pass

    def _get_style(self):
        return {
            "body": self.unit_color,
            "metal": self.faction.metal,
            "accent": self.faction.accent,
            "panel": self.faction.panel,
            "glow": self.faction.glow,
            "secondary": self.faction.secondary,
        }


class Worker(Unit):
    display_name = "Worker"
    cost = 100
    unit_color = color.rgb32(160, 118, 79)
    unit_scale = (0.4, 0.62, 0.34)
    default_speed = 7
    default_health = 80
    default_attack_damage = 8
    default_attack_range = 1.5
    default_attack_cooldown = 0.75
    default_vision_range = 7.0
    footprint_radius = 0.75
    avoidance_radius = 1.1
    selection_ring_scale = 3.0

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(150, 84, 72),
                "helmet": color.rgb32(117, 53, 48),
                "skin": color.rgb32(201, 168, 128),
                "gear": color.rgb32(98, 67, 54),
                "fabric": color.rgb32(70, 54, 49),
                "accent": self.faction.accent,
                "panel": color.rgb32(94, 39, 35),
            }

        return {
            "body": color.rgb32(112, 134, 167),
            "helmet": color.rgb32(92, 112, 138),
            "skin": color.rgb32(207, 176, 135),
            "gear": color.rgb32(76, 94, 122),
            "fabric": color.rgb32(72, 82, 96),
            "accent": self.faction.glow,
            "panel": color.rgb32(54, 72, 96),
        }

    def _build_visuals(self):
        self.head = self._add_part(scale=(0.52, 0.34, 0.52), position=(0, 0.82, 0), color=self.style["skin"])
        self.helmet = self._add_part(scale=(0.58, 0.16, 0.58), position=(0, 1.02, 0), color=self.style["helmet"])
        self.chest_plate = self._add_part(scale=(0.64, 0.36, 0.12), position=(0, 0.18, 0.24), color=self.style["accent"])
        self.backpack = self._add_part(scale=(0.54, 0.54, 0.24), position=(0, 0.12, -0.48), color=self.style["gear"])
        self.left_arm = self._add_part(scale=(0.16, 0.62, 0.16), position=(-0.66, 0.04, 0), color=self.style["skin"])
        self.right_arm = self._add_part(scale=(0.16, 0.62, 0.16), position=(0.66, 0.04, 0), color=self.style["skin"])
        self.left_leg = self._add_part(scale=(0.18, 0.72, 0.18), position=(-0.24, -0.88, 0), color=self.style["fabric"])
        self.right_leg = self._add_part(scale=(0.18, 0.72, 0.18), position=(0.24, -0.88, 0), color=self.style["fabric"])
        self.tool_case = self._add_part(scale=(0.22, 0.22, 0.44), position=(-0.48, -0.14, -0.18), color=self.style["panel"])
        self.visor = self._add_part(scale=(0.34, 0.08, 0.08), position=(0, 0.86, 0.28), color=self.style["accent"])

    def _update_visuals(self, horizontal_velocity):
        stride = min(1.0, horizontal_velocity.length() / max(0.001, self.speed))
        sway = stride * 28
        self.left_arm.rotation_x = lerp(self.left_arm.rotation_x, sway, min(1, time.dt * 8))
        self.right_arm.rotation_x = lerp(self.right_arm.rotation_x, -sway, min(1, time.dt * 8))
        self.left_leg.rotation_x = lerp(self.left_leg.rotation_x, -sway, min(1, time.dt * 8))
        self.right_leg.rotation_x = lerp(self.right_leg.rotation_x, sway, min(1, time.dt * 8))
        self.tool_case.rotation_z = lerp(self.tool_case.rotation_z, -10 * stride, min(1, time.dt * 8))

    def _attack_flash_position(self):
        return (0.42, 0.12, 0.34)

    def _attack_flash_scale(self):
        return (0.12, 0.12, 0.12)

    def _attack_flash_color(self):
        return color.rgba32(255, 202, 124, 210)


class Soldier(Unit):
    display_name = "Soldier"
    cost = 90
    unit_color = color.rgb32(132, 124, 112)
    unit_scale = (0.34, 0.72, 0.3)
    default_speed = 5.4
    default_health = 95
    default_attack_damage = 13
    default_attack_range = 5.6
    default_attack_cooldown = 0.48
    default_vision_range = 10.5
    footprint_radius = 0.62
    avoidance_radius = 0.95
    selection_ring_scale = 1.3

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(138, 80, 71),
                "helmet": color.rgb32(116, 54, 48),
                "skin": color.rgb32(193, 156, 124),
                "gear": color.rgb32(86, 62, 52),
                "fabric": color.rgb32(70, 54, 50),
                "accent": self.faction.accent,
                "rifle": color.rgb32(64, 60, 59),
            }

        return {
            "body": color.rgb32(98, 126, 164),
            "helmet": color.rgb32(80, 102, 132),
            "skin": color.rgb32(205, 172, 136),
            "gear": color.rgb32(76, 90, 112),
            "fabric": color.rgb32(72, 83, 100),
            "accent": self.faction.glow,
            "rifle": color.rgb32(64, 73, 84),
        }

    def _build_visuals(self):
        self.head = self._add_part(scale=(0.48, 0.3, 0.48), position=(0, 0.8, 0), color=self.style["skin"])
        self.helmet = self._add_part(scale=(0.54, 0.16, 0.54), position=(0, 0.98, 0), color=self.style["helmet"])
        self.vest = self._add_part(scale=(0.62, 0.4, 0.16), position=(0, 0.14, 0.2), color=self.style["accent"])
        self.pack = self._add_part(scale=(0.48, 0.42, 0.2), position=(0, 0.08, -0.38), color=self.style["gear"])
        self.left_arm = self._add_part(scale=(0.14, 0.58, 0.14), position=(-0.58, 0.02, 0.02), color=self.style["body"])
        self.right_arm = self._add_part(scale=(0.14, 0.58, 0.14), position=(0.58, 0.02, 0.02), color=self.style["body"])
        self.left_leg = self._add_part(scale=(0.16, 0.72, 0.16), position=(-0.22, -0.84, 0), color=self.style["fabric"])
        self.right_leg = self._add_part(scale=(0.16, 0.72, 0.16), position=(0.22, -0.84, 0), color=self.style["fabric"])
        self.rifle = self._add_part(scale=(0.12, 0.12, 0.92), position=(0.28, 0.06, 0.22), color=self.style["rifle"])
        self.visor = self._add_part(scale=(0.28, 0.06, 0.08), position=(0, 0.8, 0.26), color=self.style["accent"])

    def _update_visuals(self, horizontal_velocity):
        stride = min(1.0, horizontal_velocity.length() / max(0.001, self.speed))
        swing = stride * 24
        self.left_arm.rotation_x = lerp(self.left_arm.rotation_x, swing, min(1, time.dt * 8))
        self.right_arm.rotation_x = lerp(self.right_arm.rotation_x, -swing, min(1, time.dt * 8))
        self.left_leg.rotation_x = lerp(self.left_leg.rotation_x, -swing, min(1, time.dt * 8))
        self.right_leg.rotation_x = lerp(self.right_leg.rotation_x, swing, min(1, time.dt * 8))
        self.rifle.rotation_x = lerp(self.rifle.rotation_x, -8 + (stride * 4), min(1, time.dt * 8))

    def _attack_flash_parent(self):
        return self.rifle

    def _attack_flash_position(self):
        return (0, 0, 0.48)

    def _attack_flash_scale(self):
        return (0.1, 0.1, 0.18)

    def _attack_flash_color(self):
        return color.rgba32(255, 208, 126, 220)


class Dog(Unit):
    display_name = "Attack Dog"
    cost = 70
    unit_color = color.rgb32(121, 92, 69)
    unit_scale = (0.54, 0.32, 0.9)
    default_speed = 8.6
    default_health = 70
    default_attack_damage = 20
    default_attack_range = 1.35
    default_attack_cooldown = 0.8
    default_vision_range = 9.2
    footprint_radius = 0.7
    avoidance_radius = 1.05
    selection_ring_scale = 1.38

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(110, 72, 54),
                "fur": color.rgb32(110, 72, 54),
                "mane": color.rgb32(87, 55, 42),
                "snout": color.rgb32(150, 113, 86),
                "accent": self.faction.accent,
            }

        return {
            "body": color.rgb32(114, 104, 90),
            "fur": color.rgb32(114, 104, 90),
            "mane": color.rgb32(89, 82, 72),
            "snout": color.rgb32(174, 156, 132),
            "accent": self.faction.glow,
        }

    def _build_visuals(self):
        self.body_core = self._add_part(scale=(0.78, 0.46, 0.96), position=(0, 0.02, -0.02), color=self.style["fur"])
        self.shoulders = self._add_part(scale=(0.62, 0.36, 0.4), position=(0, 0.18, 0.28), color=self.style["mane"])
        self.head = self._add_part(scale=(0.44, 0.28, 0.42), position=(0, 0.18, 0.7), color=self.style["fur"])
        self.snout = self._add_part(scale=(0.24, 0.14, 0.2), position=(0, 0.08, 0.98), color=self.style["snout"])
        self.left_ear = self._add_part(scale=(0.08, 0.12, 0.06), position=(-0.12, 0.38, 0.74), color=self.style["accent"])
        self.right_ear = self._add_part(scale=(0.08, 0.12, 0.06), position=(0.12, 0.38, 0.74), color=self.style["accent"])
        self.front_left_leg = self._add_part(scale=(0.1, 0.42, 0.1), position=(-0.18, -0.28, 0.34), color=self.style["mane"])
        self.front_right_leg = self._add_part(scale=(0.1, 0.42, 0.1), position=(0.18, -0.28, 0.34), color=self.style["mane"])
        self.back_left_leg = self._add_part(scale=(0.1, 0.42, 0.1), position=(-0.18, -0.28, -0.34), color=self.style["mane"])
        self.back_right_leg = self._add_part(scale=(0.1, 0.42, 0.1), position=(0.18, -0.28, -0.34), color=self.style["mane"])
        self.tail = self._add_part(scale=(0.08, 0.08, 0.42), position=(0, 0.12, -0.74), color=self.style["accent"])

    def _update_visuals(self, horizontal_velocity):
        stride = min(1.0, horizontal_velocity.length() / max(0.001, self.speed))
        kick = stride * 30
        self.front_left_leg.rotation_x = lerp(self.front_left_leg.rotation_x, kick, min(1, time.dt * 10))
        self.front_right_leg.rotation_x = lerp(self.front_right_leg.rotation_x, -kick, min(1, time.dt * 10))
        self.back_left_leg.rotation_x = lerp(self.back_left_leg.rotation_x, -kick, min(1, time.dt * 10))
        self.back_right_leg.rotation_x = lerp(self.back_right_leg.rotation_x, kick, min(1, time.dt * 10))
        self.tail.rotation_x = lerp(self.tail.rotation_x, 18 + (stride * 14), min(1, time.dt * 8))

    def _attack_flash_parent(self):
        return self.snout

    def _attack_flash_position(self):
        return (0, 0, 0.12)

    def _attack_flash_scale(self):
        return (0.12, 0.08, 0.12)

    def _attack_flash_color(self):
        return color.rgba32(255, 170, 120, 190)


class ConstructionVehicle(Unit):
    display_name = "MCV"
    cost = 900
    can_attack = False
    unit_color = color.rgb32(132, 126, 114)
    unit_scale = (1.58, 0.58, 2.18)
    default_speed = 3.3
    default_health = 520
    default_attack_damage = 0
    default_attack_range = 0
    default_attack_cooldown = 999
    default_vision_range = 0
    footprint_radius = 1.42
    avoidance_radius = 2.0
    selection_ring_scale = 2.02
    deploy_building_key = "main_base"

    def get_selection_summary(self):
        return f"MCV ({max(0, int(self.health))} hp, press F to deploy)"

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(140, 78, 68),
                "cab": color.rgb32(176, 96, 84),
                "track": color.rgb32(68, 64, 67),
                "panel": color.rgb32(104, 54, 48),
                "accent": self.faction.accent,
                "glass": color.rgb32(232, 170, 132),
            }

        return {
            "body": color.rgb32(96, 128, 164),
            "cab": color.rgb32(136, 164, 198),
            "track": color.rgb32(62, 72, 84),
            "panel": color.rgb32(62, 89, 124),
            "accent": self.faction.accent,
            "glass": color.rgb32(132, 226, 240),
        }

    def _build_visuals(self):
        self.left_track = self._add_part(scale=(0.24, 1.0, 1.16), position=(-0.52, -0.06, -0.04), color=self.style["track"])
        self.right_track = self._add_part(scale=(0.24, 1.0, 1.16), position=(0.52, -0.06, -0.04), color=self.style["track"])
        self.rear_chassis = self._add_part(scale=(0.88, 0.42, 0.88), position=(0, 0.16, -0.46), color=self.style["body"])
        self.front_chassis = self._add_part(scale=(0.72, 0.38, 0.6), position=(0, 0.14, 0.42), color=self.style["body"])
        self.cab = self._add_part(scale=(0.58, 0.46, 0.42), position=(0, 0.54, 0.72), color=self.style["cab"])
        self.windshield = self._add_part(scale=(0.42, 0.18, 0.06), position=(0, 0.58, 0.94), color=self.style["glass"])
        self.center_module = self._add_part(scale=(0.56, 0.32, 0.62), position=(0, 0.48, -0.02), color=self.style["panel"])
        self.roof_core = self._add_part(scale=(0.34, 0.14, 0.48), position=(0, 0.82, -0.02), color=self.style["accent"])
        self.left_support = self._add_part(scale=(0.08, 0.42, 0.54), position=(-0.3, 0.48, -0.02), color=self.style["panel"])
        self.right_support = self._add_part(scale=(0.08, 0.42, 0.54), position=(0.3, 0.48, -0.02), color=self.style["panel"])
        self.front_blade = self._add_part(scale=(0.88, 0.12, 0.18), position=(0, -0.04, 1.02), color=self.style["accent"])
        self.rear_block = self._add_part(scale=(0.62, 0.24, 0.38), position=(0, 0.34, -0.98), color=self.style["panel"])
        self.left_side_box = self._add_part(scale=(0.14, 0.18, 0.66), position=(-0.78, 0.24, 0), color=self.style["panel"])
        self.right_side_box = self._add_part(scale=(0.14, 0.18, 0.66), position=(0.78, 0.24, 0), color=self.style["panel"])
        if self.faction_key == "soviet":
            self.left_stack = self._add_part(scale=(0.1, 0.46, 0.1), position=(-0.24, 0.94, -0.86), color=self.style["track"])
            self.right_stack = self._add_part(scale=(0.1, 0.46, 0.1), position=(0.24, 0.94, -0.86), color=self.style["track"])
            self.signal_beacon = self._add_part(scale=(0.14, 0.1, 0.14), position=(0, 1.02, 0.18), color=self.style["accent"])
        else:
            self.sensor_mast = self._add_part(scale=(0.06, 0.44, 0.06), position=(0.26, 1.0, -0.68), color=self.style["track"])
            self.sensor_head = self._add_part(scale=(0.18, 0.08, 0.18), position=(0.26, 1.26, -0.68), color=self.style["accent"])
            self.side_array = self._add_part(scale=(0.46, 0.08, 0.14), position=(0, 0.86, 0.18), color=self.style["accent"])

    def _update_visuals(self, horizontal_velocity):
        motion = min(1.0, horizontal_velocity.length() / max(0.001, self.speed))
        self.left_track.rotation_x = lerp(self.left_track.rotation_x, 7 * motion, min(1, time.dt * 8))
        self.right_track.rotation_x = lerp(self.right_track.rotation_x, 7 * motion, min(1, time.dt * 8))
        self.cab.rotation_z = lerp(self.cab.rotation_z, -2.4 * motion, min(1, time.dt * 5))
        self.roof_core.rotation_x = lerp(self.roof_core.rotation_x, 3.5 * motion, min(1, time.dt * 5))

    def _attack_flash_color(self):
        return color.rgba32(0, 0, 0, 0)


class Harvester(Unit):
    display_name = "Harvester"
    cost = 280
    can_attack = False
    unit_color = color.rgb32(121, 112, 98)
    unit_scale = (1.46, 0.52, 2.04)
    default_speed = 3.8
    default_health = 280
    default_attack_damage = 0
    default_attack_range = 0
    default_attack_cooldown = 999
    default_vision_range = 0
    footprint_radius = 1.35
    avoidance_radius = 1.9
    selection_ring_scale = 1.92
    cargo_capacity = 120
    harvest_amount_per_cycle = 12
    harvest_interval = 0.45
    unload_interval = 0.35
    harvest_range = 1.95
    unload_range = 2.4

    def __init__(self, *args, **kwargs):
        self.resource_fields_provider = lambda: ()
        self.dropoff_provider = lambda owner: ()
        self.deposit_callback = lambda owner, amount: None
        self.cargo_amount = 0
        self.cargo_value = 0
        self.cargo_kind = None
        self.harvest_timer = 0.0
        self.unload_timer = 0.0
        self.harvest_target = None
        self.manual_harvest = False
        super().__init__(*args, **kwargs)

    def set_economy_context(self, resource_fields_provider, dropoff_provider, deposit_callback):
        self.resource_fields_provider = resource_fields_provider
        self.dropoff_provider = dropoff_provider
        self.deposit_callback = deposit_callback

    def command_harvest(self, resource_field):
        if resource_field is None or getattr(resource_field, "is_depleted", False):
            return
        self.harvest_target = resource_field
        self.manual_harvest = True
        self._clear_navigation_goal()

    def command_move(self, destination):
        self.harvest_target = None
        self.manual_harvest = False
        super().command_move(destination)

    def get_selection_summary(self):
        return f"Harvester ({max(0, int(self.health))} hp, load {int(self.cargo_amount)}/{self.cargo_capacity})"

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(146, 82, 70),
                "cab": color.rgb32(176, 98, 84),
                "track": color.rgb32(66, 63, 68),
                "cargo": color.rgb32(95, 50, 44),
                "accent": self.faction.accent,
                "panel": color.rgb32(110, 62, 51),
                "glass": color.rgb32(222, 153, 119),
            }

        return {
            "body": color.rgb32(105, 133, 169),
            "cab": color.rgb32(138, 165, 201),
            "track": color.rgb32(66, 75, 87),
            "cargo": color.rgb32(55, 79, 112),
            "accent": self.faction.accent,
            "panel": color.rgb32(74, 97, 130),
            "glass": color.rgb32(121, 224, 238),
        }

    def _build_visuals(self):
        self.left_track = self._add_part(scale=(0.22, 0.92, 1.1), position=(-0.48, -0.04, 0.02), color=self.style["track"])
        self.right_track = self._add_part(scale=(0.22, 0.92, 1.1), position=(0.48, -0.04, 0.02), color=self.style["track"])
        self.body_shell = self._add_part(scale=(0.76, 0.48, 0.92), position=(0, 0.18, -0.22), color=self.style["body"])
        self.cab = self._add_part(scale=(0.56, 0.5, 0.42), position=(0, 0.52, 0.56), color=self.style["cab"])
        self.windshield = self._add_part(scale=(0.42, 0.2, 0.06), position=(0, 0.58, 0.82), color=self.style["glass"])
        self.cargo_bay = self._add_part(scale=(0.62, 0.28, 0.82), position=(0, 0.3, -0.58), color=self.style["cargo"])
        self.cargo_pod = self._add_part(scale=(0.54, 0.14, 0.68), position=(0, 0.5, -0.58), color=self.style["accent"])
        self.left_armature = self._add_part(scale=(0.06, 0.26, 0.42), position=(-0.26, 0.48, -0.1), color=self.style["panel"])
        self.right_armature = self._add_part(scale=(0.06, 0.26, 0.42), position=(0.26, 0.48, -0.1), color=self.style["panel"])
        self.front_guard = self._add_part(scale=(0.72, 0.12, 0.16), position=(0, -0.02, 0.96), color=self.style["accent"])
        self.exhaust = self._add_part(scale=(0.08, 0.34, 0.08), position=(0.32, 0.62, -0.84), color=self.style["panel"])

    def _update_special_behavior(self):
        self.harvest_timer = max(0.0, self.harvest_timer - time.dt)
        self.unload_timer = max(0.0, self.unload_timer - time.dt)

        if self.harvest_target and getattr(self.harvest_target, "is_depleted", False):
            self.harvest_target = None

        if self.cargo_amount >= self.cargo_capacity:
            return self._return_to_dropoff()

        if self.harvest_target:
            return self._approach_or_harvest()

        if self.cargo_amount > 0:
            return self._return_to_dropoff()

        if self.destination is None:
            self.harvest_target = self._find_best_resource_field()

        if self.harvest_target:
            return self._approach_or_harvest()

        return False

    def _approach_or_harvest(self):
        if self.harvest_target is None or getattr(self.harvest_target, "is_depleted", False):
            self.harvest_target = None
            return False

        target_point = Vec3(self.harvest_target.x, self.ground_y, self.harvest_target.z)
        distance_to_field = Vec3(target_point.x - self.x, 0, target_point.z - self.z).length()
        if distance_to_field <= self.harvest_range:
            self._clear_navigation_goal()
            self.velocity = lerp(self.velocity, Vec3(0, 0, 0), min(1, time.dt * 7))
            self._update_visuals(Vec3(0, 0, 0))
            if self.harvest_timer <= 0 and self.cargo_amount < self.cargo_capacity:
                harvest_request = min(self.harvest_amount_per_cycle, self.cargo_capacity - self.cargo_amount)
                harvested_amount = self.harvest_target.harvest(harvest_request)
                if harvested_amount > 0:
                    self.cargo_amount += harvested_amount
                    self.cargo_value += harvested_amount * self.harvest_target.credit_value
                    self.cargo_kind = self.harvest_target.resource_kind
                self.harvest_timer = self.harvest_interval
                if harvested_amount == 0 or self.cargo_amount >= self.cargo_capacity or self.harvest_target.is_depleted:
                    self.harvest_target = None
            return True

        self._set_navigation_goal(target_point)
        return False

    def _return_to_dropoff(self):
        if self.cargo_amount <= 0:
            self.cargo_value = 0
            self.cargo_kind = None
            return False

        dropoff = self._find_nearest_dropoff()
        if dropoff is None:
            return False

        dropoff_point = Vec3(dropoff.x, self.ground_y, dropoff.z)
        distance_to_dropoff = Vec3(dropoff_point.x - self.x, 0, dropoff_point.z - self.z).length()
        if distance_to_dropoff <= self.unload_range:
            self._clear_navigation_goal()
            self.velocity = lerp(self.velocity, Vec3(0, 0, 0), min(1, time.dt * 7))
            self._update_visuals(Vec3(0, 0, 0))
            if self.unload_timer <= 0 and self.cargo_value > 0:
                self.deposit_callback(self.owner, self.cargo_value)
                self.cargo_amount = 0
                self.cargo_value = 0
                self.cargo_kind = None
                self.unload_timer = self.unload_interval
                if not self.manual_harvest:
                    self.harvest_target = self._find_best_resource_field()
            return True

        self._set_navigation_goal(dropoff_point)
        return False

    def _find_best_resource_field(self):
        best_field = None
        best_score = None
        for field in self.resource_fields_provider():
            if getattr(field, "is_depleted", False):
                continue
            distance_to_field = Vec3(field.x - self.x, 0, field.z - self.z).length()
            score = distance_to_field - (field.credit_value * 0.25)
            if best_score is None or score < best_score:
                best_score = score
                best_field = field
        return best_field

    def _find_nearest_dropoff(self):
        best_building = None
        best_distance = None
        for building in self.dropoff_provider(self.owner):
            distance_to_building = Vec3(building.x - self.x, 0, building.z - self.z).length()
            if best_distance is None or distance_to_building < best_distance:
                best_distance = distance_to_building
                best_building = building
        return best_building

    def _update_visuals(self, horizontal_velocity):
        motion = min(1.0, horizontal_velocity.length() / max(0.001, self.speed))
        self.left_track.rotation_x = lerp(self.left_track.rotation_x, 12 * motion, min(1, time.dt * 9))
        self.right_track.rotation_x = lerp(self.right_track.rotation_x, 12 * motion, min(1, time.dt * 9))
        load_ratio = self.cargo_amount / max(1, self.cargo_capacity)
        self.cargo_pod.scale_y = lerp(self.cargo_pod.scale_y, 0.1 + (0.24 * load_ratio), min(1, time.dt * 6))
        self.cargo_pod.y = lerp(self.cargo_pod.y, 0.44 + (0.09 * load_ratio), min(1, time.dt * 6))
        if self.cargo_kind == "gems":
            cargo_color = color.rgb32(86, 220, 234)
        elif self.cargo_kind == "gold":
            cargo_color = color.rgb32(232, 196, 82)
        else:
            cargo_color = self.style["accent"]
        self.cargo_pod.color = cargo_color

    def _attack_flash_color(self):
        return color.rgba32(0, 0, 0, 0)


class Tank(Unit):
    display_name = "Tank"
    cost = 250
    unit_color = color.rgb32(145, 63, 59)
    unit_scale = (1.28, 0.36, 1.72)
    default_speed = 3
    default_health = 200
    default_attack_damage = 28
    default_attack_range = 6.4
    default_attack_cooldown = 1.35
    default_vision_range = 12.0
    footprint_radius = 1.25
    avoidance_radius = 1.9
    selection_ring_scale = 1.7

    def _get_style(self):
        if self.faction_key == "soviet":
            return {
                "body": color.rgb32(143, 60, 54),
                "track": color.rgb32(60, 58, 62),
                "turret": color.rgb32(176, 84, 77),
                "metal": color.rgb32(92, 88, 93),
                "accent": self.faction.accent,
                "panel": color.rgb32(106, 44, 40),
            }

        return {
            "body": color.rgb32(79, 118, 173),
            "track": color.rgb32(63, 72, 81),
            "turret": color.rgb32(129, 164, 207),
            "metal": color.rgb32(180, 196, 216),
            "accent": self.faction.glow,
            "panel": color.rgb32(50, 74, 108),
        }

    def _build_visuals(self):
        self.left_track = self._add_part(scale=(0.24, 1.1, 1.06), position=(-0.46, 0, 0), color=self.style["track"])
        self.right_track = self._add_part(scale=(0.24, 1.1, 1.06), position=(0.46, 0, 0), color=self.style["track"])
        self.hull_top = self._add_part(scale=(0.72, 0.52, 0.72), position=(0, 0.56, -0.08), color=self.style["turret"])
        self.turret = self._add_part(scale=(0.48, 0.62, 0.48), position=(0, 0.82, -0.02), color=self.style["body"])
        self.cannon = Entity(
            parent=self.turret,
            model="cube",
            scale=(0.18, 0.18, 1.45),
            position=(0, 0.04, 1.02),
            color=self.style["metal"],
            collider=None,
        )
        self.visual_parts.append(self.cannon)
        self.engine_box = self._add_part(scale=(0.4, 0.22, 0.28), position=(0, 0.5, -0.62), color=self.style["panel"])
        self.front_glacis = self._add_part(scale=(0.62, 0.16, 0.28), position=(0, 0.22, 0.76), color=self.style["accent"])
        self.left_skirt = self._add_part(scale=(0.08, 0.22, 0.92), position=(-0.62, 0.12, 0), color=self.style["metal"])
        self.right_skirt = self._add_part(scale=(0.08, 0.22, 0.92), position=(0.62, 0.12, 0), color=self.style["metal"])
        if self.faction_key == "soviet":
            self.rear_stack_left = self._add_part(scale=(0.08, 0.46, 0.08), position=(-0.22, 0.82, -0.84), color=self.style["metal"])
            self.rear_stack_right = self._add_part(scale=(0.08, 0.46, 0.08), position=(0.22, 0.82, -0.84), color=self.style["metal"])
            self.turret_badge = self._add_part(scale=(0.18, 0.08, 0.08), position=(0, 0.16, 0.28), color=self.style["accent"])
        else:
            self.sensor_mast = self._add_part(scale=(0.06, 0.34, 0.06), position=(0.24, 1.08, -0.34), color=self.style["metal"])
            self.sensor_head = self._add_part(scale=(0.14, 0.08, 0.14), position=(0.24, 1.28, -0.34), color=self.style["accent"])
            self.turret_band = self._add_part(scale=(0.56, 0.08, 0.08), position=(0, 0.22, 0.12), color=self.style["accent"])

    def _update_visuals(self, horizontal_velocity):
        track_motion = min(1.0, horizontal_velocity.length() / max(0.001, self.speed))
        self.left_track.rotation_x = lerp(self.left_track.rotation_x, 8 * track_motion, min(1, time.dt * 10))
        self.right_track.rotation_x = lerp(self.right_track.rotation_x, 8 * track_motion, min(1, time.dt * 10))
        self.turret.rotation_y = lerp(self.turret.rotation_y, 0, min(1, time.dt * 6))
        self.cannon.rotation_x = lerp(self.cannon.rotation_x, -4 * track_motion, min(1, time.dt * 6))

    def _attack_flash_parent(self):
        return self.cannon

    def _attack_flash_position(self):
        return (0, 0, 0.72)

    def _attack_flash_scale(self):
        return (0.22, 0.22, 0.28)

    def _attack_flash_color(self):
        return color.rgba32(255, 214, 118, 225)
