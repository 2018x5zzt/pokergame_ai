"""牌型定义与识别 - 斗地主14种合法牌型"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from collections import Counter

from .card import Card, Rank


class HandType(str, Enum):
    """牌型枚举"""
    SINGLE = "SINGLE"                           # 单张
    PAIR = "PAIR"                               # 对子
    TRIPLE = "TRIPLE"                           # 三条
    TRIPLE_WITH_SINGLE = "TRIPLE_WITH_SINGLE"   # 三带一
    TRIPLE_WITH_PAIR = "TRIPLE_WITH_PAIR"       # 三带一对
    STRAIGHT = "STRAIGHT"                       # 顺子 (≥5张)
    STRAIGHT_PAIR = "STRAIGHT_PAIR"             # 连对 (≥3对)
    AIRPLANE = "AIRPLANE"                       # 飞机不带
    AIRPLANE_WITH_SINGLES = "AIRPLANE_WITH_SINGLES"  # 飞机带单
    AIRPLANE_WITH_PAIRS = "AIRPLANE_WITH_PAIRS"      # 飞机带对
    FOUR_WITH_TWO_SINGLES = "FOUR_WITH_TWO_SINGLES"  # 四带二单
    FOUR_WITH_TWO_PAIRS = "FOUR_WITH_TWO_PAIRS"      # 四带二对
    BOMB = "BOMB"                               # 炸弹
    ROCKET = "ROCKET"                           # 火箭(王炸)
    PASS = "PASS"                               # 不出


@dataclass
class PlayedHand:
    """一手出牌的结构化表示"""
    type: HandType
    cards: List[Card]
    main_rank: Rank       # 主牌点数（用于比较大小）
    chain_length: int = 1  # 顺子/连对/飞机的连续组数

    @property
    def is_bomb_like(self) -> bool:
        return self.type in (HandType.BOMB, HandType.ROCKET)

    def __repr__(self) -> str:
        cards_str = " ".join(c.display for c in self.cards)
        return f"[{self.type.value}] {cards_str}"
