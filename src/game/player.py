"""玩家模型 - 斗地主三人玩家的数据结构"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

from src.engine.card import Card, sort_cards


class Role(str, Enum):
    """玩家角色"""
    LANDLORD = "LANDLORD"   # 地主
    FARMER = "FARMER"       # 农民
    UNKNOWN = "UNKNOWN"     # 未确定


@dataclass
class Player:
    """一个玩家"""
    id: int                          # 座位号 0/1/2
    name: str                        # 显示名
    hand: List[Card] = field(default_factory=list)
    role: Role = Role.UNKNOWN
    play_count: int = 0              # 本局出牌次数（用于春天判定）
    score: int = 0                   # 累计积分

    @property
    def hand_size(self) -> int:
        return len(self.hand)

    @property
    def is_landlord(self) -> bool:
        return self.role == Role.LANDLORD

    def sort_hand(self) -> None:
        """手牌排序"""
        self.hand = sort_cards(self.hand)

    def remove_cards(self, cards: List[Card]) -> None:
        """从手牌中移除指定的牌"""
        for card in cards:
            self.hand.remove(card)

    def has_cards(self, cards: List[Card]) -> bool:
        """检查手牌中是否包含指定的牌"""
        hand_copy = list(self.hand)
        for card in cards:
            if card in hand_copy:
                hand_copy.remove(card)
            else:
                return False
        return True

    def reset_for_new_game(self) -> None:
        """新一局重置"""
        self.hand.clear()
        self.role = Role.UNKNOWN
        self.play_count = 0
