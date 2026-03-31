from collections import deque
from pathlib import Path

ICON_ATLAS_FILES = {
    "alliance": Path("game/icons/alliance_icons.png"),
    "soviet": Path("game/icons/soviet_icons.png"),
}

TAB_ICON_SOURCE = Path("game/icons/category_icons.png")
TAB_ICON_BOUNDS = {
    "structures": (150, 390, 420, 590),
    "defenses": (500, 385, 700, 600),
    "barracks": (750, 390, 1020, 600),
    "factory": (1070, 440, 1360, 590),
}

ICON_CELL_BOUNDS = {
    "building": {
        "power_plant": (12, 37, 312, 371),
        "refinery": (346, 47, 663, 371),
        "barracks": (682, 47, 1011, 372),
        "radar": None,
        "airfield": None,
        "tank_factory": (13, 383, 375, 714),
        "pillbox": (659, 487, 757, 653),
    },
    "unit": {
        "mcv": (124, 722, 530, 956),
        "soldier": (432, 420, 619, 569),
        "dog": (807, 429, 941, 604),
        "harvester": (537, 727, 807, 976),
        "tank": (722, 687, 879, 857),
    },
}

FACTION_ICON_CELL_BOUNDS = {
    "alliance": {
        "unit": {
            "tank": (693, 668, 902, 971),
        },
    },
    "soviet": {
        "unit": {
            "tank": (739, 691, 881, 892),
        },
    },
}

SLICED_ICON_ROOT = Path("game/icons/sliced")

CUSTOM_ICON_SOURCES = {
    "building": {
        "radar": {
            "source": Path("game/icons/radar.png"),
            "factions": {
                "soviet": "left",
            },
        },
        "airfield": {
            "source": Path("game/icons/radar.png"),
            "factions": {
                "alliance": "right",
            },
        },
    },
    "unit": {
        "tank": {
            "source": Path("game/icons/tanks.png"),
            "factions": {
                "alliance": "right",
                "soviet": "left",
            },
        },
        "mcv": {
            "source": Path("game/icons/MCV.png"),
            "factions": {
                "alliance": "right",
                "soviet": "left",
            },
        },
        "dog": {
            "source": Path("game/icons/dots.png"),
            "factions": {
                "alliance": "left",
                "soviet": "right",
            },
        },
    },
}


def get_icon_texture_spec(icon_key, *, category, faction_key):
    sliced_path = get_sliced_icon_path(icon_key, category=category, faction_key=faction_key)
    if sliced_path.exists():
        return str(sliced_path)

    atlas_path = ICON_ATLAS_FILES.get(faction_key)
    cell_bounds = _get_cell_bounds(icon_key, category=category, faction_key=faction_key)
    if atlas_path is None or cell_bounds is None:
        return None

    return {
        "texture": str(atlas_path),
        "crop": cell_bounds,
    }


def get_tab_icon_texture_spec(tab_key):
    sliced_path = get_sliced_tab_icon_path(tab_key)
    if sliced_path.exists():
        return str(sliced_path)

    crop = TAB_ICON_BOUNDS.get(tab_key)
    if crop is None or not TAB_ICON_SOURCE.exists():
        return None

    return {
        "texture": str(TAB_ICON_SOURCE),
        "crop": crop,
    }


def get_sliced_icon_path(icon_key, *, category, faction_key):
    return SLICED_ICON_ROOT / faction_key / category / f"{icon_key}.png"


def get_sliced_tab_icon_path(tab_key):
    return SLICED_ICON_ROOT / "tabs" / f"{tab_key}.png"


def slice_all_icon_packs(output_root=SLICED_ICON_ROOT, overwrite=False):
    written_paths = []
    for faction_key in ICON_ATLAS_FILES:
        written_paths.extend(slice_icon_pack(faction_key, output_root=output_root, overwrite=overwrite))
    written_paths.extend(slice_tab_icon_pack(output_root=output_root, overwrite=overwrite))
    return written_paths


def slice_icon_pack(faction_key, output_root=SLICED_ICON_ROOT, overwrite=False):
    from PIL import Image

    atlas_path = ICON_ATLAS_FILES.get(faction_key)
    atlas_image = Image.open(atlas_path).convert("RGBA") if atlas_path and atlas_path.exists() else None
    written_paths = []
    for category, items in ICON_CELL_BOUNDS.items():
        for icon_key in items:
            output_path = output_root / faction_key / category / f"{icon_key}.png"
            if output_path.exists() and not overwrite:
                written_paths.append(output_path)
                continue

            custom_image = _slice_custom_icon_source(icon_key, category=category, faction_key=faction_key)
            if custom_image is not None:
                icon_image = custom_image
            else:
                if atlas_image is None:
                    continue
                cell_bounds = _get_cell_bounds(icon_key, category=category, faction_key=faction_key)
                if cell_bounds is None:
                    continue
                icon_image = atlas_image.crop(cell_bounds)
            icon_image = _trim_icon_image(icon_image)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            icon_image.save(output_path)
            written_paths.append(output_path)

    return written_paths


def slice_tab_icon_pack(output_root=SLICED_ICON_ROOT, overwrite=False):
    if not TAB_ICON_SOURCE.exists():
        return []

    from PIL import Image

    source_image = Image.open(TAB_ICON_SOURCE).convert("RGBA")
    written_paths = []
    for tab_key, bounds in TAB_ICON_BOUNDS.items():
        output_path = output_root / "tabs" / f"{tab_key}.png"
        if output_path.exists() and not overwrite:
            written_paths.append(output_path)
            continue

        icon_image = source_image.crop(bounds)
        icon_image = _trim_icon_image(icon_image, padding=6, min_component_pixels=24)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        icon_image.save(output_path)
        written_paths.append(output_path)

    return written_paths


def _get_cell_bounds(icon_key, *, category, faction_key):
    faction_bounds = FACTION_ICON_CELL_BOUNDS.get(faction_key, {})
    category_bounds = faction_bounds.get(category, {})
    if icon_key in category_bounds:
        return category_bounds[icon_key]
    return ICON_CELL_BOUNDS.get(category, {}).get(icon_key)


def _slice_custom_icon_source(icon_key, *, category, faction_key):
    source_definition = CUSTOM_ICON_SOURCES.get(category, {}).get(icon_key)
    if source_definition is None:
        return None

    source_path = source_definition["source"]
    if not source_path.exists():
        return None

    side = source_definition.get("factions", {}).get(faction_key)
    if side not in {"left", "right"}:
        return None

    from PIL import Image

    source_image = Image.open(source_path).convert("RGBA")
    width, height = source_image.size
    midpoint = width // 2
    if side == "left":
        return source_image.crop((0, 0, midpoint, height))
    return source_image.crop((midpoint, 0, width, height))


def _trim_icon_image(image, threshold=18, padding=10, min_component_pixels=48):
    width, height = image.size
    pixels = image.load()
    active = [[False for _ in range(width)] for _ in range(height)]

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            active[y][x] = a > 0 and (r > threshold or g > threshold or b > threshold)

    components = []
    visited = [[False for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if visited[y][x] or not active[y][x]:
                continue

            queue = deque([(x, y)])
            visited[y][x] = True
            count = 0
            min_x = max_x = x
            min_y = max_y = y

            while queue:
                current_x, current_y = queue.popleft()
                count += 1
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)

                for next_x, next_y in (
                    (current_x + 1, current_y),
                    (current_x - 1, current_y),
                    (current_x, current_y + 1),
                    (current_x, current_y - 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    if visited[next_y][next_x] or not active[next_y][next_x]:
                        continue
                    visited[next_y][next_x] = True
                    queue.append((next_x, next_y))

            components.append(
                {
                    "pixels": count,
                    "bounds": (min_x, min_y, max_x + 1, max_y + 1),
                }
            )

    if not components:
        return image

    largest_component = max(component["pixels"] for component in components)
    component_cutoff = max(min_component_pixels, int(largest_component * 0.08))
    kept_bounds = [component["bounds"] for component in components if component["pixels"] >= component_cutoff]
    if not kept_bounds:
        kept_bounds = [max(components, key=lambda component: component["pixels"])["bounds"]]

    left = min(bounds[0] for bounds in kept_bounds)
    top = min(bounds[1] for bounds in kept_bounds)
    right = max(bounds[2] for bounds in kept_bounds)
    bottom = max(bounds[3] for bounds in kept_bounds)

    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(width, right + padding)
    bottom = min(height, bottom + padding)
    return image.crop((left, top, right, bottom))
