"""牌型检测器单元测试 - 覆盖14种合法牌型 + 比较逻辑"""

import pytest
from src.engine.card import Card, Rank, Suit
from src.engine.hand_type import HandType
from src.engine.hand_detector import detect_hand, can_beat


# ============================================================
#  辅助：快速构造牌
# ============================================================

def c(rank: Rank, suit: Suit = Suit.SPADE) -> Card:
    """快捷构造一张牌"""
    return Card(rank=rank, suit=suit)


def cards_of_rank(rank: Rank, count: int) -> list[Card]:
    """构造同点数的多张牌（自动分配不同花色）"""
    suits = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
    return [Card(rank=rank, suit=suits[i]) for i in range(count)]


# ============================================================
#  基础牌型测试
# ============================================================

class TestBasicTypes:
    """单张、对子、三条、炸弹、火箭"""

    def test_single(self):
        hand = detect_hand([c(Rank.ACE)])
        assert hand is not None
        assert hand.type == HandType.SINGLE
        assert hand.main_rank == Rank.ACE

    def test_single_joker(self):
        hand = detect_hand([Card(Rank.BIG_JOKER, Suit.JOKER)])
        assert hand.type == HandType.SINGLE
        assert hand.main_rank == Rank.BIG_JOKER

    def test_pair(self):
        hand = detect_hand(cards_of_rank(Rank.KING, 2))
        assert hand.type == HandType.PAIR
        assert hand.main_rank == Rank.KING

    def test_triple(self):
        hand = detect_hand(cards_of_rank(Rank.SEVEN, 3))
        assert hand.type == HandType.TRIPLE
        assert hand.main_rank == Rank.SEVEN

    def test_bomb(self):
        hand = detect_hand(cards_of_rank(Rank.ACE, 4))
        assert hand.type == HandType.BOMB
        assert hand.main_rank == Rank.ACE

    def test_rocket(self):
        cards = [
            Card(Rank.SMALL_JOKER, Suit.JOKER),
            Card(Rank.BIG_JOKER, Suit.JOKER),
        ]
        hand = detect_hand(cards)
        assert hand.type == HandType.ROCKET
        assert hand.main_rank == Rank.BIG_JOKER

    def test_empty_returns_none(self):
        assert detect_hand([]) is None


# ============================================================
#  带牌类测试
# ============================================================

class TestWithKickers:
    """三带一、三带对、四带二单、四带二对"""

    def test_triple_with_single(self):
        cards = cards_of_rank(Rank.EIGHT, 3) + [c(Rank.THREE)]
        hand = detect_hand(cards)
        assert hand.type == HandType.TRIPLE_WITH_SINGLE
        assert hand.main_rank == Rank.EIGHT

    def test_triple_with_pair(self):
        cards = cards_of_rank(Rank.JACK, 3) + cards_of_rank(Rank.FIVE, 2)
        hand = detect_hand(cards)
        assert hand.type == HandType.TRIPLE_WITH_PAIR
        assert hand.main_rank == Rank.JACK

    def test_four_with_two_singles(self):
        cards = cards_of_rank(Rank.TEN, 4) + [c(Rank.THREE), c(Rank.FIVE)]
        hand = detect_hand(cards)
        assert hand.type == HandType.FOUR_WITH_TWO_SINGLES
        assert hand.main_rank == Rank.TEN

    def test_four_with_two_pairs(self):
        cards = (
            cards_of_rank(Rank.QUEEN, 4)
            + cards_of_rank(Rank.THREE, 2)
            + cards_of_rank(Rank.FIVE, 2)
        )
        hand = detect_hand(cards)
        assert hand.type == HandType.FOUR_WITH_TWO_PAIRS
        assert hand.main_rank == Rank.QUEEN


# ============================================================
#  顺子类测试
# ============================================================

class TestStraights:
    """顺子、连对"""

    def test_straight_5(self):
        """5张顺子: 3-4-5-6-7"""
        cards = [c(Rank.THREE), c(Rank.FOUR), c(Rank.FIVE),
                 c(Rank.SIX), c(Rank.SEVEN)]
        hand = detect_hand(cards)
        assert hand.type == HandType.STRAIGHT
        assert hand.main_rank == Rank.SEVEN
        assert hand.chain_length == 5

    def test_straight_12(self):
        """最长顺子: 3到A共12张"""
        cards = [c(r) for r in range(Rank.THREE, Rank.ACE + 1)]
        hand = detect_hand(cards)
        assert hand.type == HandType.STRAIGHT
        assert hand.chain_length == 12

    def test_straight_with_2_invalid(self):
        """包含2的顺子非法"""
        cards = [c(Rank.TEN), c(Rank.JACK), c(Rank.QUEEN),
                 c(Rank.KING), c(Rank.ACE), c(Rank.TWO)]
        hand = detect_hand(cards)
        assert hand is None

    def test_straight_pair_3(self):
        """3对连对: 33-44-55"""
        cards = (cards_of_rank(Rank.THREE, 2)
                 + cards_of_rank(Rank.FOUR, 2)
                 + cards_of_rank(Rank.FIVE, 2))
        hand = detect_hand(cards)
        assert hand.type == HandType.STRAIGHT_PAIR
        assert hand.main_rank == Rank.FIVE
        assert hand.chain_length == 3


# ============================================================
#  飞机类测试
# ============================================================

class TestAirplanes:
    """飞机不带、飞机带单、飞机带对"""

    def test_airplane_plain(self):
        """飞机不带: 333-444"""
        cards = cards_of_rank(Rank.THREE, 3) + cards_of_rank(Rank.FOUR, 3)
        hand = detect_hand(cards)
        assert hand.type == HandType.AIRPLANE
        assert hand.main_rank == Rank.FOUR
        assert hand.chain_length == 2

    def test_airplane_with_singles(self):
        """飞机带单: 333-444 + 5 + 6"""
        cards = (cards_of_rank(Rank.THREE, 3)
                 + cards_of_rank(Rank.FOUR, 3)
                 + [c(Rank.FIVE), c(Rank.SIX)])
        hand = detect_hand(cards)
        assert hand.type == HandType.AIRPLANE_WITH_SINGLES
        assert hand.main_rank == Rank.FOUR
        assert hand.chain_length == 2

    def test_airplane_with_pairs(self):
        """飞机带对: 333-444 + 55 + 66"""
        cards = (cards_of_rank(Rank.THREE, 3)
                 + cards_of_rank(Rank.FOUR, 3)
                 + cards_of_rank(Rank.FIVE, 2)
                 + cards_of_rank(Rank.SIX, 2))
        hand = detect_hand(cards)
        assert hand.type == HandType.AIRPLANE_WITH_PAIRS
        assert hand.main_rank == Rank.FOUR
        assert hand.chain_length == 2

    def test_airplane_3_groups(self):
        """3组飞机不带: 333-444-555"""
        cards = (cards_of_rank(Rank.THREE, 3)
                 + cards_of_rank(Rank.FOUR, 3)
                 + cards_of_rank(Rank.FIVE, 3))
        hand = detect_hand(cards)
        assert hand.type == HandType.AIRPLANE
        assert hand.chain_length == 3


# ============================================================
#  牌型比较测试
# ============================================================

class TestCanBeat:
    """can_beat 比较逻辑"""

    def test_bigger_single_beats(self):
        h1 = detect_hand([c(Rank.ACE)])
        h2 = detect_hand([c(Rank.KING)])
        assert can_beat(h1, h2) is True
        assert can_beat(h2, h1) is False

    def test_bomb_beats_single(self):
        bomb = detect_hand(cards_of_rank(Rank.THREE, 4))
        single = detect_hand([c(Rank.ACE)])
        assert can_beat(bomb, single) is True

    def test_bigger_bomb_beats_smaller(self):
        big = detect_hand(cards_of_rank(Rank.ACE, 4))
        small = detect_hand(cards_of_rank(Rank.THREE, 4))
        assert can_beat(big, small) is True
        assert can_beat(small, big) is False

    def test_rocket_beats_bomb(self):
        rocket = detect_hand([
            Card(Rank.SMALL_JOKER, Suit.JOKER),
            Card(Rank.BIG_JOKER, Suit.JOKER),
        ])
        bomb = detect_hand(cards_of_rank(Rank.TWO, 4))
        assert can_beat(rocket, bomb) is True
        assert can_beat(bomb, rocket) is False

    def test_different_type_cannot_beat(self):
        single = detect_hand([c(Rank.ACE)])
        pair = detect_hand(cards_of_rank(Rank.THREE, 2))
        assert can_beat(single, pair) is False
        assert can_beat(pair, single) is False

    def test_different_length_straight_cannot_beat(self):
        s5 = detect_hand([c(Rank.THREE), c(Rank.FOUR), c(Rank.FIVE),
                          c(Rank.SIX), c(Rank.SEVEN)])
        s6 = detect_hand([c(Rank.THREE), c(Rank.FOUR), c(Rank.FIVE),
                          c(Rank.SIX), c(Rank.SEVEN), c(Rank.EIGHT)])
        assert can_beat(s6, s5) is False
        assert can_beat(s5, s6) is False

    def test_same_length_straight_comparison(self):
        low = detect_hand([c(Rank.THREE), c(Rank.FOUR), c(Rank.FIVE),
                           c(Rank.SIX), c(Rank.SEVEN)])
        high = detect_hand([c(Rank.FOUR), c(Rank.FIVE), c(Rank.SIX),
                            c(Rank.SEVEN), c(Rank.EIGHT)])
        assert can_beat(high, low) is True
        assert can_beat(low, high) is False
