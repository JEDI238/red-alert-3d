from ursina import Button, Entity, Func, Text, application, camera, color

from factions import FACTIONS
from .config import BUILDING_DEFINITIONS, SIDEBAR_TABS, UNIT_DEFINITIONS

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


class MainMenuUI:
    def __init__(
        self,
        start_callback,
        select_faction_callback,
        selected_faction_key="alliance",
        subtitle="Alliance and Soviet battlegroups are deployed.",
    ):
        self.root = Entity(parent=camera.ui, enabled=True)
        self.select_faction_callback = select_faction_callback
        self.selected_faction_key = selected_faction_key
        Entity(
            parent=self.root,
            model="quad",
            scale=(2, 1),
            color=color.rgba32(0, 0, 0, 170),
        )
        Entity(
            parent=self.root,
            model="quad",
            scale=(0.82, 0.74),
            color=CARD_COLOR,
        )
        Text(
            "RA3 Clone Prototype",
            parent=self.root,
            y=0.28,
            scale=2,
            origin=(0, 0),
            color=ACCENT_COLOR,
        )
        self.subtitle_text = Text(
            subtitle,
            parent=self.root,
            y=0.18,
            scale=0.88,
            origin=(0, 0),
            color=TEXT_SECONDARY,
        )
        Text(
            "Mission notes: Deploy the MCV first. Main Base unlocks your construction branches, refineries fuel the war machine, and factories roll armor.",
            parent=self.root,
            y=0.1,
            scale=0.72,
            origin=(0, 0),
            color=TEXT_SECONDARY,
        )
        Text(
            "Choose faction",
            parent=self.root,
            y=0.0,
            scale=0.95,
            origin=(0, 0),
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
    def __init__(self, on_build, on_train, on_cancel, command_title="Command"):
        self.root = Entity(parent=camera.ui, enabled=False, x=0.67, y=-0.01)
        self.active_tab = SIDEBAR_TABS[0][0]
        self.tab_labels = dict(SIDEBAR_TABS)
        Entity(
            parent=self.root,
            model="quad",
            scale=(0.52, 1.0),
            color=PANEL_COLOR,
        )
        Entity(parent=self.root, model="quad", scale=(0.46, 0.31), y=0.2, color=SECTION_COLOR)
        Entity(parent=self.root, model="quad", scale=(0.46, 0.56), y=-0.2, color=SECTION_COLOR)

        self.command_text = Text(command_title, parent=self.root, x=-0.22, y=0.41, scale=1.15, color=ACCENT_COLOR)
        self.credits_text = Text(
            "Credits: $0",
            parent=self.root,
            x=-0.22,
            y=0.34,
            scale=1.05,
            color=TEXT_PRIMARY,
        )
        self.selection_text = Text(
            "Selection: none",
            parent=self.root,
            x=-0.22,
            y=0.27,
            scale=0.84,
            wordwrap=28,
            color=TEXT_PRIMARY,
        )
        self.status_text = Text(
            "Status: ready",
            parent=self.root,
            x=-0.22,
            y=0.18,
            scale=0.74,
            wordwrap=32,
            color=TEXT_SECONDARY,
        )
        self.construction_text = Text(
            "Construction: idle",
            parent=self.root,
            x=-0.22,
            y=0.1,
            scale=0.66,
            wordwrap=32,
            color=ACCENT_COLOR,
        )
        self.construction_bar_bg = Entity(
            parent=self.root,
            model="quad",
            scale=(0.42, 0.012),
            y=0.058,
            color=color.rgba32(11, 14, 18, 220),
        )
        self.construction_bar_fill = Entity(
            parent=self.root,
            model="quad",
            scale=(0.001, 0.012),
            y=0.058,
            color=SELECTED_COLOR,
            enabled=False,
        )

        self.tab_buttons = {}
        tab_positions = {
            "structures": (-0.12, 0.01),
            "defenses": (0.12, 0.01),
            "barracks": (-0.12, -0.055),
            "factory": (0.12, -0.055),
        }
        for tab_key, label in SIDEBAR_TABS:
            button = Button(
                parent=self.root,
                text=label,
                x=tab_positions[tab_key][0],
                y=tab_positions[tab_key][1],
                scale=(0.2, 0.05),
                color=TAB_COLOR,
                highlight_color=TAB_HIGHLIGHT,
                pressed_color=TAB_COLOR,
                text_color=TEXT_PRIMARY,
                on_click=Func(self.set_active_tab, tab_key),
            )
            self.tab_buttons[tab_key] = button

        self.content_title = Text(
            self.tab_labels[self.active_tab],
            parent=self.root,
            x=-0.22,
            y=-0.11,
            scale=1.0,
            color=ACCENT_COLOR,
        )
        self.tab_roots = {tab_key: Entity(parent=self.root, enabled=False) for tab_key, _ in SIDEBAR_TABS}

        self.building_buttons = {}
        self.base_building_text = {}
        button_y = {tab_key: -0.18 for tab_key, _ in SIDEBAR_TABS}
        for key, definition in BUILDING_DEFINITIONS.items():
            if not definition.get("menu_tab"):
                continue
            label = f"{definition['label']} (${definition['cost']})"
            button = Button(
                parent=self.tab_roots[definition["menu_tab"]],
                text=label,
                scale=(0.42, 0.055),
                y=button_y[definition["menu_tab"]],
                color=ACTION_COLOR,
                highlight_color=ACTION_HIGHLIGHT,
                pressed_color=ACTION_PRESSED,
                text_color=TEXT_PRIMARY,
                on_click=Func(on_build, key),
            )
            self.building_buttons[key] = button
            self.base_building_text[key] = label
            button_y[definition["menu_tab"]] -= 0.068

        self.unit_buttons = {}
        self.base_unit_text = {}
        unit_button_y = {tab_key: -0.18 for tab_key, _ in SIDEBAR_TABS}
        for key, definition in UNIT_DEFINITIONS.items():
            if not definition.get("show_in_menu", True) or not definition.get("menu_tab"):
                continue
            label = f"{definition['label']} (${definition['cost']})"
            button = Button(
                parent=self.tab_roots[definition["menu_tab"]],
                text=label,
                scale=(0.42, 0.055),
                y=unit_button_y[definition["menu_tab"]],
                color=DISABLED_COLOR,
                highlight_color=DISABLED_COLOR,
                pressed_color=TRAIN_PRESSED,
                text_color=TEXT_PRIMARY,
                on_click=Func(on_train, key),
            )
            self.unit_buttons[key] = button
            self.base_unit_text[key] = label
            unit_button_y[definition["menu_tab"]] -= 0.068

        self.cancel_button = Button(
            parent=self.root,
            text="Cancel build",
            scale=(0.42, 0.055),
            y=-0.54,
            color=CANCEL_COLOR,
            highlight_color=CANCEL_HIGHLIGHT,
            pressed_color=CANCEL_PRESSED,
            text_color=TEXT_PRIMARY,
            on_click=on_cancel,
        )

        Text(
            "Controls: select the MCV and press F to deploy Main Base. Drag LMB to box-select, Shift adds units, RMB moves or attacks. Harvesters unload at refineries.",
            parent=self.root,
            x=-0.22,
            y=-0.66,
            scale=0.56,
            wordwrap=33,
            color=TEXT_SECONDARY,
        )
        self.set_active_tab(self.active_tab)

    def show(self):
        self.root.enabled = True

    def set_command_title(self, command_title):
        self.command_text.text = command_title

    def set_active_tab(self, tab_key):
        if tab_key not in self.tab_roots:
            return
        self.active_tab = tab_key
        self.content_title.text = self.tab_labels[tab_key]
        for key, root in self.tab_roots.items():
            root.enabled = key == tab_key
        for key, button in self.tab_buttons.items():
            if key == tab_key:
                button.color = SELECTED_COLOR
                button.highlight_color = SELECTED_HIGHLIGHT
                button.pressed_color = SELECTED_COLOR
            else:
                button.color = TAB_COLOR
                button.highlight_color = TAB_HIGHLIGHT
                button.pressed_color = TAB_COLOR
            button.text_entity.color = TEXT_PRIMARY

    def refresh(
        self,
        credits,
        selection_label,
        status_message,
        pending_building_key,
        available_units,
        cancel_available,
        building_states,
        construction_label,
        construction_ratio,
    ):
        self.credits_text.text = f"Credits: ${credits}"
        self.selection_text.text = f"Selection: {selection_label}"
        self.status_text.text = f"Status: {status_message}"
        self.construction_text.text = f"Construction: {construction_label}"
        progress = max(0.0, min(1.0, construction_ratio))
        if progress > 0:
            width = 0.42 * progress
            self.construction_bar_fill.enabled = True
            self.construction_bar_fill.scale = (width, 0.012)
            self.construction_bar_fill.x = -0.21 + (width / 2)
        else:
            self.construction_bar_fill.enabled = False

        for key, button in self.building_buttons.items():
            state = building_states.get(key, {})
            button.text = state.get("text", self.base_building_text[key])
            self._paint_button(
                button,
                enabled=state.get("enabled", False),
                selected=state.get("selected", key == pending_building_key),
                ready_color=ACTION_COLOR,
                ready_highlight=ACTION_HIGHLIGHT,
            )

        self._paint_button(
            self.cancel_button,
            enabled=cancel_available,
            selected=False,
            ready_color=CANCEL_COLOR,
            ready_highlight=CANCEL_HIGHLIGHT,
        )

        for key, button in self.unit_buttons.items():
            button.text = self.base_unit_text[key]
            ready = key in available_units and credits >= UNIT_DEFINITIONS[key]["cost"]
            self._paint_button(
                button,
                enabled=ready,
                selected=False,
                ready_color=TRAIN_COLOR,
                ready_highlight=TRAIN_HIGHLIGHT,
            )

    @staticmethod
    def _paint_button(button, enabled, selected, ready_color, ready_highlight):
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
