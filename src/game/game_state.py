"""游戏状态机 - 控制斗地主一局游戏的完整流程"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any

from src.engine.card import Card, Rank, create_deck, shuffle_and_deal, sort_cards
from src.engine.hand_type import HandType, PlayedHand
from src.engine.hand_detector import detect_hand, can_beat
from src.game.player import Player, Role


class GamePhase(str, Enum):
    """游戏阶段"""
    WAITING = "WAITING"         # 等待开始
    DEALING = "DEALING"         # 发牌中
    BIDDING = "BIDDING"         # 叫地主
    PLAYING = "PLAYING"         # 出牌中
    FINISHED = "FINISHED"       # 已结束


@dataclass
class GameEvent:
    """游戏事件记录"""
    phase: GamePhase
    player_id: int
    action: str                  # "bid", "play", "pass"
    data: Any = None             # 叫分值 / PlayedHand / None


@dataclass
class GameState:
    """一局游戏的完整状态"""
    players: List[Player]
    phase: GamePhase = GamePhase.WAITING
    dizhu_cards: List[Card] = field(default_factory=list)

    # 叫地主相关
    current_bidder: int = 0          # 当前叫分玩家座位号
    first_bidder: int = 0            # 首叫玩家
    bid_scores: List[Optional[int]] = field(default_factory=lambda: [None, None, None])
    highest_bid: int = 0
    highest_bidder: Optional[int] = None
    bid_round_done: int = 0          # 已表态人数

    # 出牌相关
    current_player: int = 0          # 当前出牌玩家
    last_play: Optional[PlayedHand] = None
    last_player: Optional[int] = None
    pass_count: int = 0              # 连续不出次数
    bomb_count: int = 0              # 本局炸弹/火箭数

    # 结算相关
    winner: Optional[int] = None
    is_spring: bool = False          # 春天
    is_anti_spring: bool = False     # 反春天

    # 事件日志
    events: List[GameEvent] = field(default_factory=list)
    play_history: List[tuple] = field(default_factory=list)  # (player_id, PlayedHand)
