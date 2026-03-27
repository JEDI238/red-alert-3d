from ursina import Entity, color


class ResourceField(Entity):
    display_name = "Resource Field"
    resource_kind = "ore"
    size = (4.2, 0.18, 4.2)
    default_amount = 1200
    credit_value = 4
    base_color = color.rgb32(92, 87, 63)
    vein_color = color.rgb32(212, 176, 74)
    crystal_color = color.rgb32(243, 209, 106)

    def __init__(self, position=(0, 0.08, 0), amount=None, **kwargs):
        self.max_amount = amount if amount is not None else self.default_amount
        self.amount = self.max_amount
        self.is_depleted = False
        self.visual_parts = []
        super().__init__(
            model="cube",
            position=position,
            scale=self.size,
            color=self.base_color,
            collider="box",
            **kwargs,
        )
        self._build_visuals()
        self._update_visuals()

    def harvest(self, requested_amount):
        if self.is_depleted or requested_amount <= 0:
            return 0

        harvested_amount = min(requested_amount, self.amount)
        self.amount -= harvested_amount
        if self.amount <= 0:
            self.amount = 0
            self.is_depleted = True
        self._update_visuals()
        return harvested_amount

    def _add_part(self, *, scale, position=(0, 0, 0), tint=None):
        part = Entity(
            parent=self,
            model="cube",
            scale=scale,
            position=position,
            color=tint if tint is not None else self.vein_color,
            collider=None,
        )
        part.base_scale = scale
        part.base_position = position
        self.visual_parts.append(part)
        return part

    def _build_visuals(self):
        self.ore_ridge_a = self._add_part(scale=(0.36, 1.5, 0.28), position=(-0.78, 0.48, -0.2))
        self.ore_ridge_b = self._add_part(scale=(0.42, 1.8, 0.32), position=(0.16, 0.6, 0.26))
        self.ore_ridge_c = self._add_part(scale=(0.28, 1.2, 0.24), position=(0.84, 0.4, -0.44))
        self.ore_ridge_d = self._add_part(scale=(0.22, 0.9, 0.18), position=(-0.12, 0.28, -0.76))
        self.ore_ridge_e = self._add_part(scale=(0.24, 1.0, 0.18), position=(0.62, 0.32, 0.82))
        self.vein_strip = self._add_part(scale=(0.76, 0.24, 0.16), position=(0.1, 0.12, -0.1), tint=self.crystal_color)

    def _update_visuals(self):
        ratio = self.amount / max(1, self.max_amount)
        visible_ratio = max(0.08, ratio) if self.amount > 0 else 0.04
        self.color = self.base_color if not self.is_depleted else color.rgb32(68, 66, 58)
        for index, part in enumerate(self.visual_parts):
            scale_multiplier = visible_ratio * (1 - (index * 0.05))
            scale_multiplier = max(0.12, scale_multiplier)
            part.scale_x = part.base_scale[0]
            part.scale_z = part.base_scale[2]
            part.scale_y = max(0.06, part.base_scale[1] * scale_multiplier)
            part.y = (part.scale_y / 2) + (0.02 * index)
            part.color = self.crystal_color if index == len(self.visual_parts) - 1 else self.vein_color
            if self.is_depleted:
                part.color = color.rgb32(94, 88, 76)


class GoldField(ResourceField):
    display_name = "Gold Ore"
    resource_kind = "gold"
    default_amount = 1400
    credit_value = 4
    base_color = color.rgb32(92, 85, 58)
    vein_color = color.rgb32(188, 156, 64)
    crystal_color = color.rgb32(232, 196, 82)


class GemField(ResourceField):
    display_name = "Gem Field"
    resource_kind = "gems"
    default_amount = 900
    credit_value = 7
    base_color = color.rgb32(72, 74, 88)
    vein_color = color.rgb32(88, 124, 172)
    crystal_color = color.rgb32(86, 220, 234)
