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

        # 尝试出顺子（消牌效率高）
        straight = self._find_free_straight(hand, rc)
        if straight:
            return straight

        # 尝试出连对
        consec_pairs = self._find_free_straight_pair(hand, rc)
        if consec_pairs:
            return consec_pairs

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
        elif target_type == HandType.STRAIGHT:
            return self._beat_straight(hand, rc, last)
        elif target_type == HandType.STRAIGHT_PAIR:
            return self._beat_straight_pair(hand, rc, last)
        elif target_type in (HandType.AIRPLANE, HandType.AIRPLANE_WITH_SINGLES, HandType.AIRPLANE_WITH_PAIRS):
            return self._beat_airplane(hand, rc, last)

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

    # 顺子/连对/飞机不允许的点数
    _CHAIN_FORBIDDEN = {Rank.TWO, Rank.SMALL_JOKER, Rank.BIG_JOKER}

    def _beat_straight(self, hand: List[Card], rc: Counter, last: 'PlayedHand') -> Optional[List[Card]]:
        """跟顺子：找同长度、main_rank 更大的顺子"""
        length = last.chain_length
        target_max = last.main_rank
        # 收集可用的单张点数（排除2和王，排除四条保留炸弹）
        avail = sorted(r for r in rc if r not in self._CHAIN_FORBIDDEN and rc[r] >= 1 and rc[r] < 4)
        seq = self._find_chain(avail, length, target_max)
        if seq is None:
            return None
        return [next(c for c in hand if c.rank == r) for r in seq]

    def _beat_straight_pair(self, hand: List[Card], rc: Counter, last: 'PlayedHand') -> Optional[List[Card]]:
        """跟连对：找同长度、main_rank 更大的连对"""
        length = last.chain_length
        target_max = last.main_rank
        avail = sorted(r for r in rc if r not in self._CHAIN_FORBIDDEN and rc[r] >= 2 and rc[r] < 4)
        seq = self._find_chain(avail, length, target_max)
        if seq is None:
            return None
        cards = []
        for r in seq:
            cards.extend([c for c in hand if c.rank == r][:2])
        return cards

    def _beat_airplane(self, hand: List[Card], rc: Counter, last: 'PlayedHand') -> Optional[List[Card]]:
        """跟飞机（含不带/带单/带对）：找同长度、main_rank 更大的连续三条"""
        length = last.chain_length
        target_max = last.main_rank
        # 找可用的三条点数
        avail = sorted(r for r in rc if r not in self._CHAIN_FORBIDDEN and rc[r] >= 3)
        seq = self._find_chain(avail, length, target_max)
        if seq is None:
            return None
        cards = []
        for r in seq:
            cards.extend([c for c in hand if c.rank == r][:3])
        seq_set = set(seq)
        # 根据原牌型决定带牌
        if last.type == HandType.AIRPLANE_WITH_SINGLES:
            for _ in range(length):
                k = self._find_kicker(hand, seq_set, 1)
                if k is None:
                    return None
                cards.extend(k)
                seq_set.add(k[0].rank)
        elif last.type == HandType.AIRPLANE_WITH_PAIRS:
            remaining_rc = Counter(rc)
            for r in seq:
                remaining_rc[r] -= 3
            for _ in range(length):
                k = self._find_kicker_pair(hand, remaining_rc, seq_set)
                if k is None:
                    return None
                cards.extend(k)
                seq_set.add(k[0].rank)
                remaining_rc[k[0].rank] -= 2
        return cards

    # ============================================================
    #  链式查找辅助
    # ============================================================

    @staticmethod
    def _find_chain(avail_ranks: List[Rank], length: int, min_max_rank: Rank) -> Optional[List[Rank]]:
        """
        在 avail_ranks（已排序）中找到 length 个连续点数的序列，
        且序列最大值 > min_max_rank。返回最小的满足条件的序列。
        """
        if len(avail_ranks) < length:
            return None
        for i in range(len(avail_ranks) - length + 1):
            window = avail_ranks[i:i + length]
            # 检查连续性
            is_consecutive = all(window[j + 1] - window[j] == 1 for j in range(length - 1))
            if is_consecutive and window[-1] > min_max_rank:
                return window
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

    # ============================================================
    #  自由出牌：顺子/连对查找
    # ============================================================

    def _find_free_straight(self, hand: List[Card], rc: Counter) -> Optional[List[Card]]:
        """自由出牌时找最小的顺子（≥5张连续，排除2和王，保留炸弹）"""
        avail = sorted(
            r for r in rc
            if r not in self._CHAIN_FORBIDDEN and rc[r] >= 1 and rc[r] < 4
        )
        for length in range(5, len(avail) + 1):
            for i in range(len(avail) - length + 1):
                window = avail[i:i + length]
                is_consec = all(
                    window[j + 1] - window[j] == 1
                    for j in range(length - 1)
                )
                if is_consec:
                    return [
                        next(c for c in hand if c.rank == r)
                        for r in window
                    ]
        return None

    def _find_free_straight_pair(self, hand: List[Card], rc: Counter) -> Optional[List[Card]]:
        """自由出牌时找最小的连对（≥3对连续，排除2和王，保留炸弹）"""
        avail = sorted(
            r for r in rc
            if r not in self._CHAIN_FORBIDDEN and rc[r] >= 2 and rc[r] < 4
        )
        for length in range(3, len(avail) + 1):
            for i in range(len(avail) - length + 1):
                window = avail[i:i + length]
                is_consec = all(
                    window[j + 1] - window[j] == 1
                    for j in range(length - 1)
                )
                if is_consec:
                    cards = []
                    for r in window:
                        cards.extend(
                            [c for c in hand if c.rank == r][:2]
                        )
                    return cards
        return None
