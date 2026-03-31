from pathlib import Path

from pathlib import Path

from ursina import Button, Entity, Func, Text, application, camera, color, load_texture, window
from ursina.texture import Texture

from factions import FACTIONS
from .config import BUILDING_DEFINITIONS, CAMERA_MAX_Y, CAMERA_MIN_Y, SIDEBAR_TABS, UNIT_DEFINITIONS
from .texture_handler import get_icon_texture_spec, get_tab_icon_texture_spec

PANEL_COLOR = color.rgba32(14, 20, 28, 244)
CARD_COLOR = color.rgba32(24, 32, 41, 245)
SECTION_COLOR = color.rgba32(35, 48, 59, 236)
ACTION_COLOR = color.rgb32(54, 95, 140)
ACTION_HIGHLIGHT = color.rgb32(76, 123, 176)
ACTION_PRESSED = color.rgb32(42, 76, 113)
TRAIN_COLOR = color.rgb32(62, 121, 80)
TRAIN_HIGHLIGHT = color.rgb32(83, 153, 103)
TRAIN_PRESSED = color.rgb32(48, 94, 62)
TAB_COLOR = color.rgb32(44, 56, 70)
TAB_HIGHLIGHT = color.rgb32(64, 78, 96)
SELECTED_COLOR = color.rgb32(162, 108, 56)
SELECTED_HIGHLIGHT = color.rgb32(194, 135, 75)
CANCEL_COLOR = color.rgb32(121, 72, 61)
CANCEL_HIGHLIGHT = color.rgb32(152, 98, 87)
CANCEL_PRESSED = color.rgb32(95, 58, 49)
DISABLED_COLOR = color.rgb32(58, 63, 70)
ACCENT_COLOR = color.rgb32(224, 199, 139)
TEXT_PRIMARY = color.rgb32(241, 237, 229)
TEXT_SECONDARY = color.rgb32(188, 197, 206)
ALLIANCE_COLOR = color.rgb32(70, 111, 166)
ALLIANCE_HIGHLIGHT = color.rgb32(92, 138, 199)
SOVIET_COLOR = color.rgb32(145, 72, 64)
SOVIET_HIGHLIGHT = color.rgb32(178, 92, 83)
PROGRESS_TRACK_COLOR = color.rgba32(10, 14, 18, 220)
ICON_BG_COLOR = color.rgb32(18, 24, 31)
ICON_SURFACE_COLOR = color.rgb32(44, 57, 70)
ICON_SURFACE_DISABLED = color.rgb32(31, 37, 43)
READY_PROGRESS_COLOR = color.rgb32(108, 192, 121)


def _rgb32_from_color(source_color):
    return color.rgb32(
        int(source_color.r * 255),
        int(source_color.g * 255),
        int(source_color.b * 255),
    )


def _rgba32_from_color(source_color, alpha):
    return color.rgba32(
        int(source_color.r * 255),
        int(source_color.g * 255),
        int(source_color.b * 255),
        alpha,
    )


def _shade_color(source_color, factor):
    return color.rgb32(
        max(0, min(255, int(source_color.r * 255 * factor))),
        max(0, min(255, int(source_color.g * 255 * factor))),
        max(0, min(255, int(source_color.b * 255 * factor))),
    )


def _blend_colors(color_a, color_b, mix_ratio):
    mix_ratio = max(0.0, min(1.0, mix_ratio))
    inverse_ratio = 1.0 - mix_ratio
    return color.rgb32(
        int((color_a.r * 255 * inverse_ratio) + (color_b.r * 255 * mix_ratio)),
        int((color_a.g * 255 * inverse_ratio) + (color_b.g * 255 * mix_ratio)),
        int((color_a.b * 255 * inverse_ratio) + (color_b.b * 255 * mix_ratio)),
    )


def _sidebar_theme(faction_key):
    faction = FACTIONS[faction_key]
    primary = _rgb32_from_color(faction.primary)
    accent = _rgb32_from_color(faction.accent)
    panel_base = _blend_colors(_rgb32_from_color(faction.panel), color.rgb32(9, 12, 16), 0.52)
    section_base = _blend_colors(panel_base, primary, 0.2)
    tab_base = _blend_colors(_rgb32_from_color(faction.metal), primary, 0.52)
    tab_selected = _shade_color(primary, 1.08)
    minimap_base = _blend_colors(panel_base, color.rgb32(18, 24, 31), 0.3)
    return {
        "panel": _rgba32_from_color(panel_base, 246),
        "section": _rgba32_from_color(section_base, 236),
        "section_line": _rgba32_from_color(accent, 42),
        "credits": accent,
        "status": _blend_colors(TEXT_SECONDARY, accent, 0.16),
        "progress_fill": primary,
        "progress_track": _rgba32_from_color(color.rgb32(8, 10, 14), 232),
        "tab": tab_base,
        "tab_highlight": _shade_color(tab_base, 1.16),
        "tab_selected": tab_selected,
        "tab_selected_highlight": _shade_color(tab_selected, 1.16),
        "tab_accent": accent,
        "button": primary,
        "button_highlight": _shade_color(primary, 1.18),
        "button_pressed": _shade_color(primary, 0.78),
        "minimap_frame": _rgba32_from_color(primary, 210),
        "minimap_surface": minimap_base,
        "minimap_accent": accent,
    }


def _building_icon_placeholder(definition):
    explicit_placeholder = definition.get("icon_text")
    if explicit_placeholder:
        return explicit_placeholder

    words = [word for word in definition["label"].replace("-", " ").split() if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return "".join(word[0] for word in words[:2]).upper()


def _compact_card_title(title):
    cleaned_title = " ".join(str(title).replace("\n", " ").split())
    words = [word for word in cleaned_title.split() if word]
    if len(words) <= 1:
        return cleaned_title
    if len(words) == 2 and len(cleaned_title) <= 13:
        return cleaned_title
    if len(cleaned_title) <= 14:
        return cleaned_title
    return f"{words[0]}\n{' '.join(words[1:])}"


class ClockwiseProgressFrame:
    _SEGMENTS = (
        ("top_right", 0.125),
        ("right", 0.25),
        ("bottom", 0.25),
        ("left", 0.25),
        ("top_left", 0.125),
    )
    _EPSILON = 0.001

    def __init__(self, parent, thickness=0.08):
        self.thickness = thickness
        self.track_root = Entity(parent=parent, collider=None, z=-0.018)
        self.fill_root = Entity(parent=parent, collider=None, enabled=False, z=-0.019)
        self.track_segments = {
            name: Entity(parent=self.track_root, model="quad", color=PROGRESS_TRACK_COLOR, collider=None)
            for name, _ in self._SEGMENTS
        }
        self.fill_segments = {
            name: Entity(parent=self.fill_root, model="quad", color=ACCENT_COLOR, collider=None, enabled=False)
            for name, _ in self._SEGMENTS
        }
        for name, _ in self._SEGMENTS:
            self._set_segment_fill(self.track_segments[name], name, 1.0)

    def set_progress(self, progress, fill_color=ACCENT_COLOR):
        progress = max(0.0, min(1.0, progress))
        self.fill_root.enabled = progress > 0
        remaining = progress
        for name, fraction in self._SEGMENTS:
            segment = self.fill_segments[name]
            segment.color = fill_color
            segment_fill = max(0.0, min(1.0, remaining / fraction))
            self._set_segment_fill(segment, name, segment_fill)
            remaining = max(0.0, remaining - fraction)

    def _set_segment_fill(self, segment, name, fill):
        fill = max(0.0, min(1.0, fill))
        if fill <= 0:
            segment.enabled = False
            return

        segment.enabled = True
        thickness = self.thickness
        if name == "top_right":
            width = max(self._EPSILON, 0.5 * fill)
            segment.scale = (width, thickness)
            segment.x = width / 2
            segment.y = 0.5 - (thickness / 2)
            return

        if name == "right":
            height = max(self._EPSILON, fill)
            segment.scale = (thickness, height)
            segment.x = 0.5 - (thickness / 2)
            segment.y = 0.5 - (height / 2)
            return

        if name == "bottom":
            width = max(self._EPSILON, fill)
            segment.scale = (width, thickness)
            segment.x = 0.5 - (width / 2)
            segment.y = -0.5 + (thickness / 2)
            return

        if name == "left":
            height = max(self._EPSILON, fill)
            segment.scale = (thickness, height)
            segment.x = -0.5 + (thickness / 2)
            segment.y = -0.5 + (height / 2)
            return

        width = max(self._EPSILON, 0.5 * fill)
        segment.scale = (width, thickness)
        segment.x = -0.5 + (width / 2)
        segment.y = 0.5 - (thickness / 2)


class BuildButtonCard(Button):
    def __init__(
        self,
        parent,
        definition,
        on_click,
        x=0,
        y=0,
        scale=(0.106, 0.106),
        icon_key=None,
        icon_category=None,
        faction_key="alliance",
        show_progress=True,
        ready_color=ACTION_COLOR,
        ready_highlight=ACTION_HIGHLIGHT,
        ready_pressed=ACTION_PRESSED,
        accent_color=ACCENT_COLOR,
    ):
        super().__init__(
            parent=parent,
            text="",
            x=x,
            y=y,
            z=-0.01,
            scale=scale,
            color=ACTION_COLOR,
            highlight_color=ACTION_HIGHLIGHT,
            pressed_color=ACTION_PRESSED,
            on_click=on_click,
        )
        self.definition = definition
        self.show_progress = show_progress
        self.ready_color = ready_color
        self.ready_highlight = ready_highlight
        self.ready_pressed = ready_pressed
        self.accent_color = accent_color
        self.icon_key = icon_key
        self.icon_category = icon_category
        self.faction_key = faction_key
        self.explicit_icon_texture = definition.get("icon_texture")
        self.base_title = _compact_card_title(definition["label"])
        if "meta" in definition:
            self.base_meta = definition["meta"]
        elif "cost" in definition:
            self.base_meta = f"${definition['cost']}"
        else:
            self.base_meta = ""
        if self.text_entity is not None:
            self.text_entity.enabled = False
        self.card_surface = Entity(
            parent=self,
            model="quad",
            scale=(0.96, 0.96),
            z=-0.001,
            color=color.rgba32(255, 255, 255, 18),
            collider=None,
        )
        self.top_accent = Entity(
            parent=self,
            model="quad",
            scale=(0.84, 0.04),
            y=0.375,
            z=-0.002,
            color=color.rgba32(255, 255, 255, 20),
            collider=None,
        )
        self.footer_plate = Entity(
            parent=self,
            model="quad",
            scale=(0.92, 0.22),
            y=-0.35,
            z=-0.003,
            color=color.rgba32(10, 14, 18, 110),
            collider=None,
        )

        self.icon_shell = Entity(
            parent=self,
            model="quad",
            y=0.13,
            z=-0.004,
            scale=(0.72, 0.72),
            color=ICON_BG_COLOR,
            collider=None,
        )
        self.icon_surface = Entity(
            parent=self.icon_shell,
            model="quad",
            scale=(0.96, 0.96),
            z=-0.001,
            color=ICON_SURFACE_COLOR,
            collider=None,
        )
        self.icon_image = Entity(
            parent=self.icon_surface,
            model="quad",
            scale=(1.06, 1.06),
            z=-0.001,
            color=color.white,
            collider=None,
            enabled=False,
        )
        self.icon_placeholder = Text(
            _building_icon_placeholder(definition),
            parent=self.icon_surface,
            y=-0.02,
            scale=2.1,
            origin=(0, 0),
            z=-0.002,
            color=ACCENT_COLOR,
        )
        self.progress_frame = ClockwiseProgressFrame(self, thickness=0.055) if show_progress else None

        self.title_text = Text(
            self.base_title,
            parent=self,
            y=-0.308,
            scale=3.55,
            origin=(0, 0),
            wordwrap=9,
            z=-0.006,
            color=TEXT_PRIMARY,
        )
        self.title_text.line_height = 0.84
        self.meta_text = Text(
            self.base_meta,
            parent=self,
            y=-0.404,
            scale=1.12,
            origin=(0, 0),
            z=-0.007,
            color=TEXT_SECONDARY,
        )
        self._update_icon_texture()

    def refresh(self, state):
        title = state.get("title", self.base_title)
        meta = state.get("meta", self.base_meta)
        enabled = state.get("enabled", False)
        selected = state.get("selected", False)
        ready = state.get("ready", False)
        progress = max(0.0, min(1.0, state.get("progress", 0.0)))

        show_meta = bool(meta)
        self.title_text.text = _compact_card_title(title)
        self.title_text.y = -0.302 if show_meta else -0.356
        self.meta_text.text = meta if show_meta else ""
        if self.progress_frame is not None:
            self.progress_frame.set_progress(progress, fill_color=READY_PROGRESS_COLOR if ready else self.accent_color)
        self._apply_visual_state(enabled=enabled, selected=selected, ready=ready, progress=progress)

    def _apply_visual_state(self, enabled, selected, ready, progress):
        if selected:
            self.color = SELECTED_COLOR
            self.highlight_color = SELECTED_HIGHLIGHT
            self.pressed_color = SELECTED_COLOR
            self.card_surface.color = color.rgba32(255, 224, 168, 30)
            self.top_accent.color = color.rgba32(255, 220, 148, 90)
        elif enabled:
            self.color = self.ready_color
            self.highlight_color = self.ready_highlight
            self.pressed_color = self.ready_pressed
            self.card_surface.color = color.rgba32(255, 255, 255, 20)
            self.top_accent.color = _rgba32_from_color(self.ready_highlight, 88)
        else:
            self.color = color.rgb32(63, 70, 80)
            self.highlight_color = color.rgb32(63, 70, 80)
            self.pressed_color = color.rgb32(63, 70, 80)
            self.card_surface.color = color.rgba32(255, 255, 255, 12)
            self.top_accent.color = color.rgba32(255, 255, 255, 12)

        self.footer_plate.color = color.rgba32(10, 14, 18, 150 if (selected or enabled) else 90)
        if selected:
            self.icon_surface.color = color.rgb32(78, 56, 34)
        elif enabled:
            self.icon_surface.color = ICON_SURFACE_COLOR
        else:
            self.icon_surface.color = ICON_SURFACE_DISABLED

        active_progress = progress > 0 and not ready
        if selected or enabled:
            self.title_text.color = TEXT_PRIMARY
        else:
            self.title_text.color = TEXT_SECONDARY

        if ready:
            accent = READY_PROGRESS_COLOR
        elif active_progress:
            accent = self.accent_color
        elif enabled:
            accent = self.accent_color
        else:
            accent = TEXT_SECONDARY

        meta_value = str(self.meta_text.text).strip()
        if ready or active_progress:
            self.meta_text.color = accent
        elif meta_value.startswith("$") and (selected or enabled):
            self.meta_text.color = self.accent_color
        else:
            self.meta_text.color = TEXT_SECONDARY
        self.icon_placeholder.color = accent
        self.icon_image.color = color.white if (selected or enabled) else color.rgba32(170, 170, 170, 160)

    def set_faction_key(self, faction_key):
        if self.faction_key == faction_key:
            return
        self.faction_key = faction_key
        self._update_icon_texture()

    def set_ready_palette(self, ready_color, ready_highlight, ready_pressed, accent_color=None):
        self.ready_color = ready_color
        self.ready_highlight = ready_highlight
        self.ready_pressed = ready_pressed
        if accent_color is not None:
            self.accent_color = accent_color

    def _update_icon_texture(self):
        texture_spec = self.explicit_icon_texture
        if self.icon_key and self.icon_category:
            texture_spec = get_icon_texture_spec(
                self.icon_key,
                category=self.icon_category,
                faction_key=self.faction_key,
            ) or texture_spec
        self._apply_icon_texture(texture_spec)

    def _apply_icon_texture(self, texture_spec):
        if not texture_spec:
            self.icon_image.enabled = False
            self.icon_placeholder.enabled = True
            return

        crop = None
        texture_name = texture_spec
        if isinstance(texture_spec, dict):
            texture_name = texture_spec.get("texture")
            crop = texture_spec.get("crop")

        texture = None
        if texture_name:
            texture_path = Path(texture_name)
            if texture_path.exists():
                try:
                    from PIL import Image

                    texture = Texture(Image.open(texture_path).convert("RGBA"))
                except Exception:
                    texture = None
            else:
                try:
                    texture = load_texture(texture_name)
                except Exception:
                    texture = None

        if texture is None:
            self.icon_image.enabled = False
            self.icon_placeholder.enabled = True
            return

        self.icon_image.texture = texture
        self.icon_image.texture_scale = (1, 1)
        self.icon_image.texture_offset = (0, 0)
        self.icon_image.scale = (1.06, 1.06)

        if crop and len(crop) == 4:
            left, top, right, bottom = crop
            tex_width = max(1, texture.width)
            tex_height = max(1, texture.height)
            crop_width = max(1, right - left)
            crop_height = max(1, bottom - top)
            self.icon_image.texture_scale = (crop_width / tex_width, crop_height / tex_height)
            self.icon_image.texture_offset = (left / tex_width, 1 - (bottom / tex_height))
            aspect = crop_width / crop_height
        else:
            aspect = texture.width / max(1, texture.height)

        if aspect >= 1:
            self.icon_image.scale = (1.06, 1.06 / aspect)
        else:
            self.icon_image.scale = (1.06 * aspect, 1.06)

        self.icon_image.enabled = True
        self.icon_placeholder.enabled = False


class TabIconButton(Button):
    def __init__(self, parent, tab_key, on_click, x=0, y=0):
        super().__init__(
            parent=parent,
            text="",
            x=x,
            y=y,
            z=-0.01,
            scale=(0.04, 0.04),
            color=TAB_COLOR,
            highlight_color=TAB_HIGHLIGHT,
            pressed_color=TAB_COLOR,
            on_click=on_click,
        )
        if self.text_entity is not None:
            self.text_entity.enabled = False
        self.tab_key = tab_key
        self.base_color = TAB_COLOR
        self.base_highlight = TAB_HIGHLIGHT
        self.selected_color = SELECTED_COLOR
        self.selected_highlight = SELECTED_HIGHLIGHT
        self.accent_color = ACCENT_COLOR
        self.icon_parts = []
        self.icon_root = Entity(parent=self, collider=None, z=-0.002)
        self.icon_image = Entity(
            parent=self.icon_root,
            model="quad",
            scale=(0.68, 0.68),
            z=-0.001,
            color=color.white,
            collider=None,
            enabled=False,
        )
        self.inner_surface = Entity(
            parent=self,
            model="quad",
            scale=(0.96, 0.9),
            z=-0.001,
            color=color.rgba32(255, 255, 255, 14),
            collider=None,
        )
        self._build_icon()
        self._update_icon_texture()

    def set_palette(self, base_color, highlight_color, accent_color, selected_color=None, selected_highlight=None):
        self.base_color = base_color
        self.base_highlight = highlight_color
        self.accent_color = accent_color
        self.selected_color = selected_color if selected_color is not None else _shade_color(base_color, 1.12)
        self.selected_highlight = (
            selected_highlight if selected_highlight is not None else _shade_color(self.selected_color, 1.12)
        )

    def set_selected(self, selected):
        if selected:
            self.color = self.selected_color
            self.highlight_color = self.selected_highlight
            self.pressed_color = _shade_color(self.selected_color, 0.82)
            self.inner_surface.color = _rgba32_from_color(self.accent_color, 36)
            icon_color = TEXT_PRIMARY
            accent_color = self.accent_color
        else:
            self.color = self.base_color
            self.highlight_color = self.base_highlight
            self.pressed_color = _shade_color(self.base_color, 0.84)
            self.inner_surface.color = _rgba32_from_color(self.base_highlight, 42)
            icon_color = TEXT_SECONDARY
            accent_color = self.accent_color

        if self.icon_image.enabled:
            self.icon_image.color = color.white if selected else color.rgba32(228, 234, 240, 212)

        for part in self.icon_parts:
            if getattr(part, "icon_role", "base") == "accent":
                part.color = accent_color
            else:
                part.color = icon_color

    def _build_icon(self):
        if self.tab_key == "structures":
            self._add_icon_part(scale=(0.42, 0.52), position=(0, -0.02))
            self._add_icon_part(scale=(0.48, 0.08), position=(0, 0.3), role="accent")
            for x in (-0.12, 0.0, 0.12):
                self._add_icon_part(scale=(0.06, 0.09), position=(x, 0.08))
                self._add_icon_part(scale=(0.06, 0.09), position=(x, -0.12))
            self._add_icon_part(scale=(0.09, 0.15), position=(0, -0.24), role="accent")
            return

        if self.tab_key == "defenses":
            self._add_icon_part(scale=(0.34, 0.12), position=(0, 0.2))
            self._add_icon_part(scale=(0.26, 0.18), position=(0, 0.0))
            self._add_icon_part(scale=(0.18, 0.2), position=(0, -0.16))
            self._add_icon_part(scale=(0.11, 0.11), position=(0, -0.28), rotation_z=45, role="accent")
            return

        if self.tab_key == "barracks":
            self._add_icon_part(scale=(0.12, 0.12), position=(0, 0.25), role="accent")
            self._add_icon_part(scale=(0.08, 0.26), position=(0, 0.02))
            self._add_icon_part(scale=(0.28, 0.06), position=(0, 0.06))
            self._add_icon_part(scale=(0.06, 0.22), position=(-0.08, -0.2), rotation_z=-24)
            self._add_icon_part(scale=(0.06, 0.22), position=(0.08, -0.2), rotation_z=24)
            return

        self._add_icon_part(scale=(0.48, 0.16), position=(0, -0.04))
        self._add_icon_part(scale=(0.32, 0.1), position=(0.02, 0.1))
        self._add_icon_part(scale=(0.2, 0.08), position=(-0.1, -0.18))
        self._add_icon_part(scale=(0.2, 0.08), position=(0.12, -0.18))
        self._add_icon_part(scale=(0.24, 0.05), position=(0.2, 0.14), role="accent")

    def _add_icon_part(self, scale, position=(0, 0), rotation_z=0, role="base"):
        part = Entity(
            parent=self.icon_root,
            model="quad",
            scale=scale,
            position=position,
            z=-0.001,
            rotation_z=rotation_z,
            color=TEXT_SECONDARY,
            collider=None,
        )
        part.icon_role = role
        self.icon_parts.append(part)
        return part

    def _update_icon_texture(self):
        texture_spec = get_tab_icon_texture_spec(self.tab_key)
        self._apply_icon_texture(texture_spec)

    def _apply_icon_texture(self, texture_spec):
        for part in self.icon_parts:
            part.enabled = texture_spec is None

        if not texture_spec:
            self.icon_image.enabled = False
            return

        crop = None
        texture_name = texture_spec
        if isinstance(texture_spec, dict):
            texture_name = texture_spec.get("texture")
            crop = texture_spec.get("crop")

        texture = None
        if texture_name:
            texture_path = Path(texture_name)
            if texture_path.exists():
                try:
                    from PIL import Image

                    texture = Texture(Image.open(texture_path).convert("RGBA"))
                except Exception:
                    texture = None
            else:
                try:
                    texture = load_texture(texture_name)
                except Exception:
                    texture = None

        if texture is None:
            self.icon_image.enabled = False
            for part in self.icon_parts:
                part.enabled = True
            return

        self.icon_image.texture = texture
        self.icon_image.texture_scale = (1, 1)
        self.icon_image.texture_offset = (0, 0)
        self.icon_image.scale = (0.66, 0.66)

        if crop and len(crop) == 4:
            left, top, right, bottom = crop
            tex_width = max(1, texture.width)
            tex_height = max(1, texture.height)
            crop_width = max(1, right - left)
            crop_height = max(1, bottom - top)
            self.icon_image.texture_scale = (crop_width / tex_width, crop_height / tex_height)
            self.icon_image.texture_offset = (left / tex_width, 1 - (bottom / tex_height))
            aspect = crop_width / crop_height
        else:
            aspect = texture.width / max(1, texture.height)

        if aspect >= 1:
            self.icon_image.scale = (0.68, 0.68 / aspect)
        else:
            self.icon_image.scale = (0.68 * aspect, 0.68)

        self.icon_image.enabled = True


class MinimapWidget:
    def __init__(self, parent, x=0, y=0, size=0.17):
        self.root = Entity(parent=parent, x=x, y=y, z=-0.008)
        self.frame = Entity(
            parent=self.root,
            model="quad",
            scale=(size + 0.024, size + 0.024),
            color=color.rgba32(8, 12, 17, 230),
            collider=None,
        )
        self.surface = Entity(
            parent=self.root,
            model="quad",
            scale=(size, size),
            z=-0.001,
            color=color.rgb32(27, 39, 49),
            collider=None,
        )
        self.terrain_tint = Entity(
            parent=self.surface,
            model="quad",
            scale=(0.96, 0.96),
            z=-0.001,
            color=color.rgba32(80, 120, 92, 34),
            collider=None,
        )
        self.grid_lines = []
        for offset in (-0.166, 0.0, 0.166):
            self.grid_lines.append(
                Entity(
                    parent=self.surface,
                    model="quad",
                    scale=(0.006, 0.94),
                    x=offset,
                    z=-0.002,
                    color=color.rgba32(255, 255, 255, 18),
                    collider=None,
                )
            )
            self.grid_lines.append(
                Entity(
                    parent=self.surface,
                    model="quad",
                    scale=(0.94, 0.006),
                    y=offset,
                    z=-0.002,
                    color=color.rgba32(255, 255, 255, 18),
                    collider=None,
                )
            )

        self.resource_markers = []
        self.player_unit_markers = []
        self.enemy_unit_markers = []
        self.player_building_markers = []
        self.enemy_building_markers = []
        self.camera_view = Entity(
            parent=self.surface,
            model="quad",
            scale=(0.2, 0.16),
            z=-0.004,
            color=color.rgba32(255, 255, 255, 18),
            collider=None,
        )
        self.camera_view_outline_h = [
            Entity(parent=self.camera_view, model="quad", scale=(1, 0.08), y=0.5, z=-0.001, color=ACCENT_COLOR, collider=None),
            Entity(parent=self.camera_view, model="quad", scale=(1, 0.08), y=-0.5, z=-0.001, color=ACCENT_COLOR, collider=None),
        ]
        self.camera_view_outline_v = [
            Entity(parent=self.camera_view, model="quad", scale=(0.08, 1), x=-0.5, z=-0.001, color=ACCENT_COLOR, collider=None),
            Entity(parent=self.camera_view, model="quad", scale=(0.08, 1), x=0.5, z=-0.001, color=ACCENT_COLOR, collider=None),
        ]

    def set_palette(self, frame_color, surface_color, accent_color):
        self.frame.color = frame_color
        self.surface.color = surface_color
        self.terrain_tint.color = _rgba32_from_color(accent_color, 26)
        for grid_line in self.grid_lines:
            grid_line.color = color.rgba32(255, 255, 255, 14)
        for outline in self.camera_view_outline_h + self.camera_view_outline_v:
            outline.color = accent_color

    def update(self, *, ground_limit, camera_position, units, buildings, resource_fields, player_color, enemy_color):
        player_units = [
            unit for unit in units if not getattr(unit, "is_destroyed", False) and getattr(unit, "owner", "") == "player"
        ]
        enemy_units = [
            unit for unit in units if not getattr(unit, "is_destroyed", False) and getattr(unit, "owner", "") == "enemy"
        ]
        player_buildings = [
            building
            for building in buildings
            if not getattr(building, "is_destroyed", False) and getattr(building, "owner", "") == "player"
        ]
        enemy_buildings = [
            building
            for building in buildings
            if not getattr(building, "is_destroyed", False) and getattr(building, "owner", "") == "enemy"
        ]

        self._update_marker_pool(
            self.resource_markers,
            resource_fields,
            ground_limit=ground_limit,
            tint=color.rgb32(232, 191, 88),
            marker_scale=(0.034, 0.034),
        )
        self._update_marker_pool(
            self.player_unit_markers,
            player_units,
            ground_limit=ground_limit,
            tint=self._tint_from_color(player_color),
            marker_scale=(0.022, 0.022),
        )
        self._update_marker_pool(
            self.enemy_unit_markers,
            enemy_units,
            ground_limit=ground_limit,
            tint=self._tint_from_color(enemy_color),
            marker_scale=(0.022, 0.022),
        )
        self._update_marker_pool(
            self.player_building_markers,
            player_buildings,
            ground_limit=ground_limit,
            tint=self._tint_from_color(player_color),
            marker_scale=(0.04, 0.04),
        )
        self._update_marker_pool(
            self.enemy_building_markers,
            enemy_buildings,
            ground_limit=ground_limit,
            tint=self._tint_from_color(enemy_color),
            marker_scale=(0.04, 0.04),
        )

        zoom_ratio = max(0.0, min(1.0, (camera_position.y - CAMERA_MIN_Y) / max(1.0, CAMERA_MAX_Y - CAMERA_MIN_Y)))
        view_height = 0.18 + (zoom_ratio * 0.18)
        self.camera_view.scale = (view_height * 0.78, view_height)
        self.camera_view.x, self.camera_view.y = self._world_to_map(camera_position.x, camera_position.z, ground_limit)

    def _update_marker_pool(self, pool, items, *, ground_limit, tint, marker_scale):
        while len(pool) < len(items):
            pool.append(Entity(parent=self.surface, model="quad", collider=None, z=-0.003))

        for index, marker in enumerate(pool):
            if index >= len(items):
                marker.enabled = False
                continue

            item = items[index]
            marker.enabled = True
            marker.scale = marker_scale
            marker.color = tint
            marker.x, marker.y = self._world_to_map(item.x, item.z, ground_limit)

    @staticmethod
    def _tint_from_color(source_color):
        return color.rgb32(
            int(source_color.r * 255),
            int(source_color.g * 255),
            int(source_color.b * 255),
        )

    @staticmethod
    def _world_to_map(world_x, world_z, ground_limit):
        span = max(1.0, ground_limit)
        x = max(-0.46, min(0.46, (world_x / span) * 0.46))
        y = max(-0.46, min(0.46, (world_z / span) * 0.46))
        return x, y


class MainMenuUI:
    def __init__(
        self,
        start_callback,
        select_faction_callback,
        selected_faction_key="alliance",
        subtitle="Alliance and Soviet battlegroups are deployed.",
    ):
        self.root = Entity(parent=camera.ui, enabled=True, z=-1)
        self.select_faction_callback = select_faction_callback
        self.selected_faction_key = selected_faction_key
        Entity(
            parent=self.root,
            model="quad",
            scale=(2, 1),
            z=0.001,
            color=color.rgba32(0, 0, 0, 170),
        )
        Entity(
            parent=self.root,
            model="quad",
            scale=(0.82, 0.74),
            z=-0.001,
            color=CARD_COLOR,
        )
        Text(
            "RA3 Clone Prototype",
            parent=self.root,
            y=0.28,
            scale=2,
            origin=(0, 0),
            z=-0.01,
            color=ACCENT_COLOR,
        )
        self.subtitle_text = Text(
            subtitle,
            parent=self.root,
            y=0.18,
            scale=0.88,
            origin=(0, 0),
            z=-0.011,
            color=TEXT_SECONDARY,
        )
        Text(
            "Mission notes: Deploy the MCV first. Main Base unlocks your construction branches, refineries fuel the war machine, and factories roll armor.",
            parent=self.root,
            y=0.1,
            scale=0.72,
            origin=(0, 0),
            z=-0.012,
            color=TEXT_SECONDARY,
        )
        Text(
            "Choose faction",
            parent=self.root,
            y=0.0,
            scale=0.95,
            origin=(0, 0),
            z=-0.013,
            color=TEXT_PRIMARY,
        )
        self.faction_buttons = {}
        for x, faction_key in [(-0.14, "alliance"), (0.14, "soviet")]:
            button = Button(
                parent=self.root,
                text=FACTIONS[faction_key].name,
                scale=(0.24, 0.08),
                x=x,
                y=-0.08,
                z=-0.02,
                text_color=TEXT_PRIMARY,
                on_click=Func(self._handle_faction_select, faction_key),
            )
            self.faction_buttons[faction_key] = button
        self.set_selected_faction(selected_faction_key)
        Button(
            parent=self.root,
            text="Start battle",
            scale=(0.28, 0.08),
            y=-0.25,
            z=-0.02,
            color=ACTION_COLOR,
            highlight_color=ACTION_HIGHLIGHT,
            pressed_color=ACTION_PRESSED,
            text_color=TEXT_PRIMARY,
            on_click=start_callback,
        )
        Button(
            parent=self.root,
            text="Quit",
            scale=(0.28, 0.08),
            y=-0.37,
            z=-0.02,
            color=CANCEL_COLOR,
            highlight_color=CANCEL_HIGHLIGHT,
            pressed_color=CANCEL_PRESSED,
            text_color=TEXT_PRIMARY,
            on_click=application.quit,
        )

    def show(self):
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False

    def set_subtitle(self, subtitle):
        self.subtitle_text.text = subtitle

    def set_selected_faction(self, faction_key):
        self.selected_faction_key = faction_key
        for key, button in self.faction_buttons.items():
            if key == "alliance":
                ready_color = ALLIANCE_COLOR
                ready_highlight = ALLIANCE_HIGHLIGHT
            else:
                ready_color = SOVIET_COLOR
                ready_highlight = SOVIET_HIGHLIGHT

            if key == faction_key:
                button.color = SELECTED_COLOR
                button.highlight_color = SELECTED_HIGHLIGHT
                button.pressed_color = SELECTED_COLOR
            else:
                button.color = ready_color
                button.highlight_color = ready_highlight
                button.pressed_color = ready_color
            button.text_entity.color = TEXT_PRIMARY

    def _handle_faction_select(self, faction_key):
        self.select_faction_callback(faction_key)
        self.set_selected_faction(faction_key)


class SidebarUI:
    def __init__(self, on_build, on_train, on_cancel, command_title="Command", faction_key="alliance"):
        self.root = Entity(parent=camera.ui, enabled=False, y=-0.01, z=-1)
        self.active_tab = SIDEBAR_TABS[0][0]
        self.tab_labels = dict(SIDEBAR_TABS)
        self.faction_key = faction_key
        self.command_title = command_title
        panel_width = 0.216
        self.panel_width = panel_width
        self.panel_right_margin = 0.008
        inset_width = 0.184
        action_columns_x = (-0.044, 0.044)
        action_button_scale = (0.084, 0.084)
        action_start_y = 0.086
        action_row_step = 0.086
        self.action_columns_x = action_columns_x
        self.action_start_y = action_start_y
        self.action_row_step = action_row_step
        self.panel_background = Entity(
            parent=self.root,
            model="quad",
            scale=(panel_width, 1.0),
            z=0.001,
            color=PANEL_COLOR,
        )
        self.top_section = Entity(
            parent=self.root,
            model="quad",
            scale=(inset_width, 0.236),
            y=0.336,
            z=-0.001,
            color=SECTION_COLOR,
        )
        self.bottom_section = Entity(
            parent=self.root,
            model="quad",
            scale=(inset_width, 0.756),
            y=-0.102,
            z=-0.001,
            color=SECTION_COLOR,
        )
        self.section_line = Entity(
            parent=self.root,
            model="quad",
            scale=(inset_width, 0.004),
            y=0.176,
            z=-0.002,
            color=color.rgba32(255, 255, 255, 20),
        )
        self.minimap = MinimapWidget(parent=self.root, y=0.344, size=0.096)
        self.credits_text = Text(
            "$0",
            parent=self.root,
            x=0,
            y=0.442,
            z=-0.02,
            scale=0.94,
            origin=(0, 0),
            color=ACCENT_COLOR,
        )
        self.status_text = Text(
            "idle",
            parent=self.root,
            x=0,
            y=0.164,
            z=-0.023,
            scale=0.24,
            origin=(0, 0),
            wordwrap=15,
            color=TEXT_SECONDARY,
        )
        self.construction_bar_width = 0.156
        self.construction_bar_bg = Entity(
            parent=self.root,
            model="quad",
            scale=(self.construction_bar_width, 0.012),
            y=0.138,
            z=-0.004,
            color=color.rgba32(11, 14, 18, 220),
        )
        self.construction_bar_fill = Entity(
            parent=self.root,
            model="quad",
            scale=(0.001, 0.012),
            y=0.138,
            z=-0.005,
            color=SELECTED_COLOR,
            enabled=False,
        )

        self.tab_strip = Entity(
            parent=self.root,
            model="quad",
            scale=(0.178, 0.04),
            y=0.218,
            z=-0.003,
            color=color.rgba32(20, 28, 37, 205),
        )

        self.tab_buttons = {}
        tab_positions = {
            "structures": -0.063,
            "defenses": -0.021,
            "barracks": 0.021,
            "factory": 0.063,
        }
        for tab_key, _label in SIDEBAR_TABS:
            button = TabIconButton(
                parent=self.root,
                tab_key=tab_key,
                x=tab_positions[tab_key],
                y=0.218,
                on_click=Func(self.set_active_tab, tab_key),
            )
            self.tab_buttons[tab_key] = button

        self.tab_roots = {tab_key: Entity(parent=self.root, enabled=False) for tab_key, _ in SIDEBAR_TABS}

        self.building_buttons = {}
        self.building_buttons_by_tab = {tab_key: [] for tab_key, _ in SIDEBAR_TABS}
        for key, definition in BUILDING_DEFINITIONS.items():
            if not definition.get("menu_tab"):
                continue
            tab_key = definition["menu_tab"]
            button = BuildButtonCard(
                parent=self.tab_roots[tab_key],
                definition=definition,
                x=0.0,
                y=action_start_y,
                scale=action_button_scale,
                icon_key=key,
                icon_category="building",
                faction_key=self.faction_key,
                accent_color=ACCENT_COLOR,
                on_click=Func(on_build, key),
            )
            self.building_buttons[key] = button
            self.building_buttons_by_tab[tab_key].append(button)

        self.unit_buttons = {}
        self.unit_buttons_by_tab = {tab_key: [] for tab_key, _ in SIDEBAR_TABS}
        for key, definition in UNIT_DEFINITIONS.items():
            if not definition.get("show_in_menu", True) or not definition.get("menu_tab"):
                continue
            tab_key = definition["menu_tab"]
            button = BuildButtonCard(
                parent=self.tab_roots[definition["menu_tab"]],
                definition=definition,
                x=0.0,
                y=action_start_y,
                scale=action_button_scale,
                icon_key=key,
                icon_category="unit",
                faction_key=self.faction_key,
                show_progress=False,
                ready_color=TRAIN_COLOR,
                ready_highlight=TRAIN_HIGHLIGHT,
                ready_pressed=TRAIN_PRESSED,
                accent_color=ACCENT_COLOR,
                on_click=Func(on_train, key),
            )
            self.unit_buttons[key] = button
            self.unit_buttons_by_tab[tab_key].append(button)

        self.cancel_button = BuildButtonCard(
            parent=self.root,
            definition={
                "label": "Cancel",
                "meta": "QUEUE",
                "icon_text": "X",
                "icon_texture": None,
            },
            x=0.0,
            y=-0.432,
            scale=(0.054, 0.054),
            show_progress=False,
            ready_color=CANCEL_COLOR,
            ready_highlight=CANCEL_HIGHLIGHT,
            ready_pressed=CANCEL_PRESSED,
            accent_color=ACCENT_COLOR,
            on_click=on_cancel,
        )
        self.cancel_button.enabled = False
        self._apply_theme()
        self._relayout_all_action_buttons()
        self._align_to_right_edge()
        self.set_active_tab(self.active_tab)

    def show(self):
        self._align_to_right_edge()
        self.root.enabled = True

    def set_command_title(self, command_title):
        self.command_title = command_title

    def set_faction_key(self, faction_key):
        if self.faction_key == faction_key:
            return
        self.faction_key = faction_key
        for button in self.building_buttons.values():
            button.set_faction_key(faction_key)
        for button in self.unit_buttons.values():
            button.set_faction_key(faction_key)
        self._apply_theme()

    def set_active_tab(self, tab_key):
        if tab_key not in self.tab_roots:
            return
        self.active_tab = tab_key
        for key, root in self.tab_roots.items():
            root.enabled = key == tab_key
        for key, button in self.tab_buttons.items():
            button.set_selected(key == tab_key)

    def refresh(
        self,
        credits,
        selection_label,
        status_message,
        pending_building_key,
        unit_states,
        cancel_available,
        building_states,
        construction_label,
        construction_ratio,
    ):
        self._align_to_right_edge()
        self.credits_text.text = f"${credits}"
        if construction_label != "idle":
            info_line = construction_label
        elif selection_label != "none":
            info_line = selection_label
        else:
            info_line = status_message
        self.status_text.text = info_line
        progress = max(0.0, min(1.0, construction_ratio))
        if progress > 0:
            width = self.construction_bar_width * progress
            self.construction_bar_fill.enabled = True
            self.construction_bar_fill.scale = (width, 0.012)
            self.construction_bar_fill.x = -(self.construction_bar_width / 2) + (width / 2)
        else:
            self.construction_bar_fill.enabled = False

        for key, button in self.building_buttons.items():
            state = dict(building_states.get(key, {}))
            state["selected"] = state.get("selected", key == pending_building_key)
            is_visible = state.get("visible", True)
            button.enabled = is_visible
            if is_visible:
                button.refresh(state)
        self._relayout_button_groups(self.building_buttons_by_tab)

        self._paint_button(
            self.cancel_button,
            enabled=cancel_available,
            selected=False,
            ready_color=CANCEL_COLOR,
            ready_highlight=CANCEL_HIGHLIGHT,
        )
        self.cancel_button.enabled = cancel_available

        for key, button in self.unit_buttons.items():
            state = dict(unit_states.get(key, {}))
            is_visible = state.get("visible", False)
            button.enabled = is_visible
            if not is_visible:
                continue
            button.refresh(state)
        self._relayout_button_groups(self.unit_buttons_by_tab)

    def update_minimap(self, *, ground_limit, units, buildings, resource_fields, player_color, enemy_color):
        self.minimap.update(
            ground_limit=ground_limit,
            camera_position=camera.position,
            units=units,
            buildings=buildings,
            resource_fields=resource_fields,
            player_color=player_color,
            enemy_color=enemy_color,
        )

    def _align_to_right_edge(self):
        self.root.x = (window.aspect_ratio / 2) - (self.panel_width / 2) - self.panel_right_margin

    def _apply_theme(self):
        theme = _sidebar_theme(self.faction_key)
        self.panel_background.color = theme["panel"]
        self.top_section.color = theme["section"]
        self.bottom_section.color = theme["section"]
        self.section_line.color = theme["section_line"]
        self.credits_text.color = theme["credits"]
        self.status_text.color = theme["status"]
        self.construction_bar_bg.color = theme["progress_track"]
        self.construction_bar_fill.color = theme["progress_fill"]
        self.tab_strip.color = _rgba32_from_color(theme["tab_selected"], 132)
        self.minimap.set_palette(
            theme["minimap_frame"],
            theme["minimap_surface"],
            theme["minimap_accent"],
        )
        for key, button in self.tab_buttons.items():
            button.set_palette(
                theme["tab"],
                theme["tab_highlight"],
                theme["tab_accent"],
                selected_color=theme["tab_selected"],
                selected_highlight=theme["tab_selected_highlight"],
            )
            button.set_selected(key == self.active_tab)

        unit_ready = _blend_colors(theme["button"], TEXT_PRIMARY, 0.08)
        unit_highlight = _shade_color(unit_ready, 1.16)
        unit_pressed = _shade_color(unit_ready, 0.8)
        for button in self.building_buttons.values():
            button.set_ready_palette(
                theme["button"],
                theme["button_highlight"],
                theme["button_pressed"],
                accent_color=theme["credits"],
            )
        for button in self.unit_buttons.values():
            button.set_ready_palette(
                unit_ready,
                unit_highlight,
                unit_pressed,
                accent_color=theme["credits"],
            )
        self.cancel_button.set_ready_palette(
            CANCEL_COLOR,
            CANCEL_HIGHLIGHT,
            CANCEL_PRESSED,
            accent_color=theme["credits"],
        )

    def _relayout_all_action_buttons(self):
        self._relayout_button_groups(self.building_buttons_by_tab)
        self._relayout_button_groups(self.unit_buttons_by_tab)

    def _relayout_button_groups(self, button_groups):
        for buttons in button_groups.values():
            self._relayout_button_grid(buttons)

    def _relayout_button_grid(self, buttons):
        visible_buttons = [button for button in buttons if button.enabled]
        for index, button in enumerate(visible_buttons):
            if len(visible_buttons) == 1:
                button.x = 0.0
            else:
                button.x = self.action_columns_x[index % 2]
            button.y = self.action_start_y - ((index // 2) * self.action_row_step)

    @staticmethod
    def _paint_button(button, enabled, selected, ready_color, ready_highlight):
        if hasattr(button, "refresh"):
            button.refresh(
                {
                    "enabled": enabled,
                    "selected": selected,
                    "progress": 0.0,
                    "ready": False,
                }
            )
            return

        if selected:
            button.color = SELECTED_COLOR
            button.highlight_color = SELECTED_HIGHLIGHT
            button.pressed_color = SELECTED_COLOR
            button.text_entity.color = TEXT_PRIMARY
            return

        if enabled:
            button.color = ready_color
            button.highlight_color = ready_highlight
            if ready_color == ACTION_COLOR:
                button.pressed_color = ACTION_PRESSED
            elif ready_color == TRAIN_COLOR:
                button.pressed_color = TRAIN_PRESSED
            else:
                button.pressed_color = CANCEL_PRESSED
            button.text_entity.color = TEXT_PRIMARY
            return

        button.color = DISABLED_COLOR
        button.highlight_color = DISABLED_COLOR
        button.pressed_color = DISABLED_COLOR
        button.text_entity.color = TEXT_SECONDARY
