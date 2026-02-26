"""牌的定义 - 斗地主54张扑克牌的数据模型"""

from enum import IntEnum, Enum
from dataclasses import dataclass
from typing import List
import random


class Rank(IntEnum):
    """点数枚举（数值越大牌越大）"""
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14
    TWO = 15
    SMALL_JOKER = 16
    BIG_JOKER = 17


class Suit(str, Enum):
    """花色枚举"""
    SPADE = "♠"
    HEART = "♥"
    DIAMOND = "♦"
    CLUB = "♣"
    JOKER = "🃏"


# 点数显示映射
RANK_DISPLAY = {
    Rank.THREE: "3", Rank.FOUR: "4", Rank.FIVE: "5",
    Rank.SIX: "6", Rank.SEVEN: "7", Rank.EIGHT: "8",
    Rank.NINE: "9", Rank.TEN: "10", Rank.JACK: "J",
    Rank.QUEEN: "Q", Rank.KING: "K", Rank.ACE: "A",
    Rank.TWO: "2", Rank.SMALL_JOKER: "小王", Rank.BIG_JOKER: "大王",
}


@dataclass(frozen=True)
class Card:
    """一张扑克牌"""
    rank: Rank
    suit: Suit

    @property
    def display(self) -> str:
        if self.rank == Rank.SMALL_JOKER:
            return "小王"
        if self.rank == Rank.BIG_JOKER:
            return "大王"
        return f"{self.suit.value}{RANK_DISPLAY[self.rank]}"

    def __repr__(self) -> str:
        return self.display

    def __lt__(self, other: "Card") -> bool:
        return self.rank < other.rank

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))


def create_deck() -> List[Card]:
    """创建一副54张标准扑克牌"""
    deck: List[Card] = []
    suits = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
    ranks = [r for r in Rank if r not in (Rank.SMALL_JOKER, Rank.BIG_JOKER)]

    for rank in ranks:
        for suit in suits:
            deck.append(Card(rank=rank, suit=suit))

    deck.append(Card(rank=Rank.SMALL_JOKER, suit=Suit.JOKER))
    deck.append(Card(rank=Rank.BIG_JOKER, suit=Suit.JOKER))

    assert len(deck) == 54, f"牌数错误: {len(deck)}"
    return deck


def shuffle_and_deal(deck: List[Card]) -> tuple[List[Card], List[Card], List[Card], List[Card]]:
    """洗牌并发牌: 返回 (玩家1手牌, 玩家2手牌, 玩家3手牌, 底牌)"""
    shuffled = deck.copy()
    random.shuffle(shuffled)

    hand1 = sorted(shuffled[0:17], key=lambda c: c.rank)
    hand2 = sorted(shuffled[17:34], key=lambda c: c.rank)
    hand3 = sorted(shuffled[34:51], key=lambda c: c.rank)
    dizhu_cards = sorted(shuffled[51:54], key=lambda c: c.rank)

    return hand1, hand2, hand3, dizhu_cards


def sort_cards(cards: List[Card]) -> List[Card]:
    """按点数排序手牌（从小到大）"""
    return sorted(cards, key=lambda c: c.rank)
