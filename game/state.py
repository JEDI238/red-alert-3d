from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from .config import DEFAULT_STATUS, STARTING_CREDITS
from factions import ENEMY_FACTION_KEY, PLAYER_FACTION_KEY

if TYPE_CHECKING:
    from entities.building import Building
    from entities.unit import Unit


@dataclass
class GameState:
    credits: int = STARTING_CREDITS
    enemy_credits: int = STARTING_CREDITS
    player_faction_key: str = PLAYER_FACTION_KEY
    enemy_faction_key: str = ENEMY_FACTION_KEY
    selected_units: list["Unit"] = field(default_factory=list)
    selected_building: Optional["Building"] = None
    pending_building_key: Optional[str] = None
    ready_building_key: Optional[str] = None
    construction_building_key: Optional[str] = None
    construction_time_left: float = 0.0
    construction_total_time: float = 0.0
    status_message: str = DEFAULT_STATUS
    game_started: bool = False
