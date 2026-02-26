"""RuleAI 单元测试"""

import pytest
from collections import Counter
from typing import List, Optional

from src.engine.card import Card, Rank, Suit
from src.engine.hand_type import HandType, PlayedHand
from src.engine.hand_detector import detect_hand
from src.game.player import Player, Role
from src.game.game_state import GameState, GamePhase
from src.ai.rule_ai import RuleAI


# ============================================================
#  辅助工具
# ============================================================

def _c(rank: Rank, suit: Suit = Suit.SPADE) -> Card:
    """快速创建一张牌"""
    return Card(rank=rank, suit=suit)


def _make_player(cards: List[Card], pid: int = 0) -> Player:
    """创建一个持有指定手牌的玩家"""
    p = Player(id=pid, name=f"P{pid}")
    p.hand = list(cards)
    return p


def _make_state(**kwargs) -> GameState:
    """创建一个基础 GameState"""
    players = [Player(id=i, name=f"P{i}") for i in range(3)]
    s = GameState(players=players)
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


# ============================================================
#  叫分决策测试
# ============================================================

class TestDecideBid:
    """测试叫分策略"""

    def setup_method(self):
        self.ai = RuleAI()

    def test_strong_hand_bid_3(self):
        """火箭 + 炸弹 → 叫3分"""
        cards = [
            _c(Rank.SMALL_JOKER, Suit.JOKER), _c(Rank.BIG_JOKER, Suit.JOKER),
            _c(Rank.ACE, Suit.SPADE), _c(Rank.ACE, Suit.HEART),
            _c(Rank.ACE, Suit.DIAMOND), _c(Rank.ACE, Suit.CLUB),
            _c(Rank.THREE), _c(Rank.FOUR), _c(Rank.FIVE),
        ]
        player = _make_player(cards)
        state = _make_state(highest_bid=0)
        assert self.ai.decide_bid(player, state) == 3

    def test_medium_hand_bid_2(self):
        """两个2 + 一个A → score=5, 叫2分区间"""
        cards = [
            _c(Rank.TWO, Suit.SPADE), _c(Rank.TWO, Suit.HEART),
            _c(Rank.ACE), _c(Rank.THREE), _c(Rank.FOUR),
        ]
        player = _make_player(cards)
        state = _make_state(highest_bid=0)
        bid = self.ai.decide_bid(player, state)
        # score=5, 在 3<=score<6 区间
        assert bid >= 1

    def test_weak_hand_pass(self):
        """全小牌 → 不叫"""
        cards = [_c(Rank.THREE), _c(Rank.FOUR), _c(Rank.FIVE),
                 _c(Rank.SIX), _c(Rank.SEVEN)]
        player = _make_player(cards)
        state = _make_state(highest_bid=0)
        assert self.ai.decide_bid(player, state) == 0

    def test_bid_must_exceed_highest(self):
        """叫分必须高于当前最高叫分，否则不叫"""
        cards = [_c(Rank.TWO), _c(Rank.ACE), _c(Rank.THREE)]
        player = _make_player(cards)
        # score=3, 在 3<=score<6 区间，会尝试叫 max(1, highest_bid+1)
        state = _make_state(highest_bid=2)
        bid = self.ai.decide_bid(player, state)
        assert bid == 3 or bid == 0  # 要么叫3要么不叫


# ============================================================
#  自由出牌测试
# ============================================================

class TestFreePlay:
    """测试自由出牌策略"""

    def setup_method(self):
        self.ai = RuleAI()

    def test_last_hand_all_out(self):
        """只剩一手牌（如一个对子）直接全出"""
        cards = [_c(Rank.THREE, Suit.SPADE), _c(Rank.THREE, Suit.HEART)]
        player = _make_player(cards)
        state = _make_state(last_play=None)
        result = self.ai.decide_play(player, state)
        assert len(result) == 2
        assert all(c.rank == Rank.THREE for c in result)

    def test_play_smallest_single(self):
        """有单张时优先出最小单张"""
        cards = [
            _c(Rank.THREE), _c(Rank.FIVE, Suit.SPADE), _c(Rank.FIVE, Suit.HEART),
            _c(Rank.KING),
        ]
        player = _make_player(cards)
        state = _make_state(last_play=None)
        result = self.ai.decide_play(player, state)
        assert len(result) == 1
        assert result[0].rank == Rank.THREE

    def test_play_smallest_pair(self):
        """没有单张时出最小对子"""
        cards = [
            _c(Rank.FOUR, Suit.SPADE), _c(Rank.FOUR, Suit.HEART),
            _c(Rank.KING, Suit.SPADE), _c(Rank.KING, Suit.HEART),
        ]
        player = _make_player(cards)
        state = _make_state(last_play=None)
        result = self.ai.decide_play(player, state)
        assert len(result) == 2
        assert all(c.rank == Rank.FOUR for c in result)

    def test_empty_hand_returns_none(self):
        """空手牌返回 None"""
        player = _make_player([])
        state = _make_state(last_play=None)
        assert self.ai.decide_play(player, state) is None


# ============================================================
#  跟牌测试
# ============================================================

class TestFollowPlay:
    """测试跟牌策略"""

    def setup_method(self):
        self.ai = RuleAI()

    def test_beat_single(self):
        """能压过单张时出最小的"""
        cards = [_c(Rank.FIVE), _c(Rank.SEVEN), _c(Rank.KING)]
        player = _make_player(cards)
        last = PlayedHand(
            type=HandType.SINGLE, cards=[_c(Rank.FOUR)],
            main_rank=Rank.FOUR, chain_length=1,
        )
        state = _make_state(last_play=last)
        result = self.ai.decide_play(player, state)
        assert len(result) == 1
        assert result[0].rank == Rank.FIVE

    def test_cannot_beat_single(self):
        """压不过时返回 None (PASS)"""
        cards = [_c(Rank.THREE), _c(Rank.FOUR)]
        player = _make_player(cards)
        last = PlayedHand(
            type=HandType.SINGLE, cards=[_c(Rank.ACE)],
            main_rank=Rank.ACE, chain_length=1,
        )
        state = _make_state(last_play=last)
        assert self.ai.decide_play(player, state) is None

    def test_beat_pair(self):
        """能压过对子时出最小的对子"""
        cards = [
            _c(Rank.SIX, Suit.SPADE), _c(Rank.SIX, Suit.HEART),
            _c(Rank.TEN, Suit.SPADE), _c(Rank.TEN, Suit.HEART),
        ]
        player = _make_player(cards)
        last = PlayedHand(
            type=HandType.PAIR,
            cards=[_c(Rank.FIVE, Suit.SPADE), _c(Rank.FIVE, Suit.HEART)],
            main_rank=Rank.FIVE, chain_length=1,
        )
        state = _make_state(last_play=last)
        result = self.ai.decide_play(player, state)
        assert len(result) == 2
        assert all(c.rank == Rank.SIX for c in result)

    def test_beat_triple_with_single(self):
        """压三带一"""
        cards = [
            _c(Rank.EIGHT, Suit.SPADE), _c(Rank.EIGHT, Suit.HEART),
            _c(Rank.EIGHT, Suit.DIAMOND), _c(Rank.THREE),
        ]
        player = _make_player(cards)
        last = PlayedHand(
            type=HandType.TRIPLE_WITH_SINGLE,
            cards=[_c(Rank.SEVEN)] * 3 + [_c(Rank.FOUR)],
            main_rank=Rank.SEVEN, chain_length=1,
        )
        state = _make_state(last_play=last)
        result = self.ai.decide_play(player, state)
        assert result is not None
        assert len(result) == 4
        ranks = [c.rank for c in result]
        assert ranks.count(Rank.EIGHT) == 3

    def test_preserve_bomb_on_single(self):
        """出单张时不拆炸弹"""
        cards = [
            _c(Rank.KING, Suit.SPADE), _c(Rank.KING, Suit.HEART),
            _c(Rank.KING, Suit.DIAMOND), _c(Rank.KING, Suit.CLUB),
        ]
        player = _make_player(cards)
        last = PlayedHand(
            type=HandType.SINGLE, cards=[_c(Rank.QUEEN)],
            main_rank=Rank.QUEEN, chain_length=1,
        )
        state = _make_state(last_play=last)
        # 只有4张K（炸弹），不应拆开出单张
        assert self.ai.decide_play(player, state) is None
