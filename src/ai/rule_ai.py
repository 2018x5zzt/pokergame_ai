"""规则引擎 AI - 基于简单规则的出牌策略，不依赖 LLM"""

import random
from typing import List, Optional
from collections import Counter

from src.engine.card import Card, Rank, Suit
from src.engine.hand_type import HandType, PlayedHand
from src.engine.hand_detector import detect_hand, can_beat
from src.game.player import Player
from src.game.game_state import GameState


class RuleAI:
    """基于简单规则的 AI 策略"""

    def decide_bid(self, player: Player, state: GameState) -> int:
        """
        叫分决策：根据手牌强度决定叫分。
        简单策略：数炸弹和大牌数量。
        """
        hand = player.hand
        rc = Counter(c.rank for c in hand)

        score = 0
        # 炸弹 +6 分
        for r, cnt in rc.items():
            if cnt == 4:
                score += 6
        # 火箭 +8 分
        if Rank.SMALL_JOKER in rc and Rank.BIG_JOKER in rc:
            score += 8
        # 2 的数量 +2 分
        score += rc.get(Rank.TWO, 0) * 2
        # A 的数量 +1 分
        score += rc.get(Rank.ACE, 0)

        if score >= 10:
            return 3
        elif score >= 6:
            return max(2, state.highest_bid + 1)
        elif score >= 3:
            return max(1, state.highest_bid + 1)
        return 0

    def decide_play(self, player: Player, state: GameState) -> Optional[List[Card]]:
        """
        出牌决策。
        自由出牌：从小到大出最小的合法牌型。
        跟牌：找能压过上家的最小牌型。
        """
        hand = player.hand
        if not hand:
            return None

        is_free = (state.last_play is None)

        if is_free:
            return self._free_play(hand)
        else:
            return self._follow_play(hand, state.last_play)

    def _free_play(self, hand: List[Card]) -> List[Card]:
        """自由出牌：优先出小牌，保留炸弹"""
        rc = Counter(c.rank for c in hand)

        # 只剩一手牌直接出完
        test = detect_hand(hand)
        if test is not None:
            return list(hand)

        # 优先出单张（最小的）
        singles = sorted(r for r, cnt in rc.items() if cnt == 1)
        if singles:
            r = singles[0]
            return [c for c in hand if c.rank == r][:1]

        # 出对子（最小的）
        pairs = sorted(r for r, cnt in rc.items() if cnt == 2)
        if pairs:
            r = pairs[0]
            return [c for c in hand if c.rank == r][:2]

        # 出三条（最小的）
        triples = sorted(r for r, cnt in rc.items() if cnt == 3)
        if triples:
            r = triples[0]
            cards = [c for c in hand if c.rank == r][:3]
            # 尝试带一张单牌
            kicker = self._find_kicker(hand, {r}, 1)
            if kicker:
                cards.extend(kicker)
            return cards

        # 最后出最小的单张
        return [min(hand, key=lambda c: c.rank)]

    def _follow_play(self, hand: List[Card], last: PlayedHand) -> Optional[List[Card]]:
        """跟牌：找能压过上家的最小组合"""
        rc = Counter(c.rank for c in hand)
        target_type = last.type
        target_rank = last.main_rank

        # 按牌型分别处理
        if target_type == HandType.SINGLE:
            return self._beat_single(hand, rc, target_rank)
        elif target_type == HandType.PAIR:
            return self._beat_pair(hand, rc, target_rank)
        elif target_type == HandType.TRIPLE:
            return self._beat_triple(hand, rc, target_rank, kicker=0)
        elif target_type == HandType.TRIPLE_WITH_SINGLE:
            return self._beat_triple(hand, rc, target_rank, kicker=1)
        elif target_type == HandType.TRIPLE_WITH_PAIR:
            return self._beat_triple(hand, rc, target_rank, kicker=2)
        elif target_type == HandType.BOMB:
            return self._beat_bomb(hand, rc, target_rank)

        # 其他复杂牌型暂时不跟，直接 PASS
        return None

    # ============================================================
    #  跟牌辅助方法
    # ============================================================

    def _beat_single(self, hand: List[Card], rc: Counter, target: Rank) -> Optional[List[Card]]:
        """找比 target 大的最小单张"""
        candidates = sorted(r for r in rc if r > target and rc[r] < 4)
        if candidates:
            r = candidates[0]
            return [c for c in hand if c.rank == r][:1]
        return None

    def _beat_triple(
        self, hand: List[Card], rc: Counter, target: Rank, kicker: int
    ) -> Optional[List[Card]]:
        """找比 target 大的最小三条，kicker=0/1/2 表示带牌数"""
        candidates = sorted(r for r in rc if r > target and rc[r] >= 3 and rc[r] < 4)
        if not candidates:
            return None
        r = candidates[0]
        cards = [c for c in hand if c.rank == r][:3]
        if kicker == 1:
            k = self._find_kicker(hand, {r}, 1)
            if not k:
                return None
            cards.extend(k)
        elif kicker == 2:
            k = self._find_kicker_pair(hand, rc, {r})
            if not k:
                return None
            cards.extend(k)
        return cards

    def _beat_pair(self, hand: List[Card], rc: Counter, target: Rank) -> Optional[List[Card]]:
        """找比 target 大的最小对子"""
        candidates = sorted(r for r in rc if r > target and rc[r] >= 2 and rc[r] < 4)
        if candidates:
            r = candidates[0]
            return [c for c in hand if c.rank == r][:2]
        return None

    def _beat_bomb(self, hand: List[Card], rc: Counter, target: Rank) -> Optional[List[Card]]:
        """找比 target 大的最小炸弹"""
        candidates = sorted(r for r in rc if r > target and rc[r] == 4)
        if candidates:
            r = candidates[0]
            return [c for c in hand if c.rank == r]
        # 火箭压炸弹
        if Rank.SMALL_JOKER in rc and Rank.BIG_JOKER in rc:
            return [c for c in hand if c.rank in (Rank.SMALL_JOKER, Rank.BIG_JOKER)]
        return None

    # ============================================================
    #  带牌辅助方法
    # ============================================================

    def _find_kicker(self, hand: List[Card], exclude: set, count: int) -> Optional[List[Card]]:
        """找 count 张单牌作为踢脚牌，排除 exclude 中的 rank"""
        rc = Counter(c.rank for c in hand)
        # 优先从单张/对子中找最小的
        for r in sorted(rc):
            if r in exclude or rc[r] >= 4:
                continue
            available = [c for c in hand if c.rank == r]
            if len(available) >= count:
                return available[:count]
        return None

    def _find_kicker_pair(self, hand: List[Card], rc: Counter, exclude: set) -> Optional[List[Card]]:
        """找一个对子作为踢脚牌"""
        candidates = sorted(r for r in rc if r not in exclude and rc[r] >= 2 and rc[r] < 4)
        if candidates:
            r = candidates[0]
            return [c for c in hand if c.rank == r][:2]
        return None
