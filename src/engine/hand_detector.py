"""牌型检测器 - 识别一组牌的牌型并构建 PlayedHand"""

from typing import List, Optional
from collections import Counter

from .card import Card, Rank
from .hand_type import HandType, PlayedHand


# 顺子/连对/飞机中不允许出现的点数
_CHAIN_FORBIDDEN = {Rank.TWO, Rank.SMALL_JOKER, Rank.BIG_JOKER}


def detect_hand(cards: List[Card]) -> Optional[PlayedHand]:
    """
    识别一组牌的牌型。
    返回 PlayedHand 或 None（非法牌型）。
    """
    if not cards:
        return None

    n = len(cards)
    rank_counts = Counter(c.rank for c in cards)

    # 按检测优先级依次尝试
    # 火箭 > 炸弹 > 单张/对子/三条 > 带牌类 > 顺子类
    result = (
        _detect_rocket(cards, n, rank_counts)
        or _detect_bomb(cards, n, rank_counts)
        or _detect_single(cards, n, rank_counts)
        or _detect_pair(cards, n, rank_counts)
        or _detect_triple(cards, n, rank_counts)
        or _detect_triple_with_single(cards, n, rank_counts)
        or _detect_triple_with_pair(cards, n, rank_counts)
        or _detect_straight(cards, n, rank_counts)
        or _detect_straight_pair(cards, n, rank_counts)
        or _detect_airplane(cards, n, rank_counts)
        or _detect_airplane_with_singles(cards, n, rank_counts)
        or _detect_airplane_with_pairs(cards, n, rank_counts)
        or _detect_four_with_two_singles(cards, n, rank_counts)
        or _detect_four_with_two_pairs(cards, n, rank_counts)
    )
    return result


# ============================================================
#  辅助函数
# ============================================================

def _groups_by_count(rank_counts: Counter, count: int) -> List[Rank]:
    """返回出现恰好 count 次的所有点数，按点数排序"""
    return sorted(r for r, c in rank_counts.items() if c == count)


def _find_consecutive(ranks: List[Rank], length: int) -> Optional[List[Rank]]:
    """
    在已排序的 ranks 中找到恰好 length 个连续点数的序列。
    排除 2 和大小王。返回该序列或 None。
    """
    filtered = [r for r in ranks if r not in _CHAIN_FORBIDDEN]
    if len(filtered) < length:
        return None
    # 检查是否恰好连续
    if len(filtered) != length:
        return None
    for i in range(len(filtered) - 1):
        if filtered[i + 1] - filtered[i] != 1:
            return None
    return filtered


# ============================================================
#  基础牌型检测
# ============================================================

def _detect_rocket(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """火箭：大王 + 小王"""
    if n == 2 and Rank.SMALL_JOKER in rc and Rank.BIG_JOKER in rc:
        return PlayedHand(HandType.ROCKET, cards, Rank.BIG_JOKER)
    return None


def _detect_bomb(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """炸弹：四张相同点数"""
    if n == 4 and len(rc) == 1:
        rank = next(iter(rc))
        return PlayedHand(HandType.BOMB, cards, rank)
    return None


def _detect_single(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """单张"""
    if n == 1:
        return PlayedHand(HandType.SINGLE, cards, cards[0].rank)
    return None


def _detect_pair(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """对子：两张相同点数"""
    if n == 2 and len(rc) == 1:
        rank = next(iter(rc))
        return PlayedHand(HandType.PAIR, cards, rank)
    return None


def _detect_triple(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """三条：三张相同点数"""
    if n == 3 and len(rc) == 1:
        rank = next(iter(rc))
        return PlayedHand(HandType.TRIPLE, cards, rank)
    return None


# ============================================================
#  带牌类检测
# ============================================================

def _detect_triple_with_single(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """三带一：三条 + 一张单牌"""
    if n != 4:
        return None
    triples = _groups_by_count(rc, 3)
    if len(triples) == 1:
        return PlayedHand(HandType.TRIPLE_WITH_SINGLE, cards, triples[0])
    return None


def _detect_triple_with_pair(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """三带一对：三条 + 一个对子"""
    if n != 5:
        return None
    triples = _groups_by_count(rc, 3)
    pairs = _groups_by_count(rc, 2)
    if len(triples) == 1 and len(pairs) == 1:
        return PlayedHand(HandType.TRIPLE_WITH_PAIR, cards, triples[0])
    return None


def _detect_four_with_two_singles(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """四带二单：四条 + 两张单牌（两张单牌可以相同点数）"""
    if n != 6:
        return None
    fours = _groups_by_count(rc, 4)
    if len(fours) == 1:
        # 剩余2张不能构成对子（否则是四带一对的歧义，但规则上四带二单允许两张相同）
        # 实际上四带二单的两张可以相同，只要不是一个对子形式的"四带一对"
        # 这里只要有一个四条 + 剩余恰好2张即可
        return PlayedHand(HandType.FOUR_WITH_TWO_SINGLES, cards, fours[0])
    return None


def _detect_four_with_two_pairs(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """四带二对：四条 + 两个不同对子"""
    if n != 8:
        return None
    fours = _groups_by_count(rc, 4)
    pairs = _groups_by_count(rc, 2)
    if len(fours) == 1 and len(pairs) == 2:
        return PlayedHand(HandType.FOUR_WITH_TWO_PAIRS, cards, fours[0])
    return None


# ============================================================
#  顺子类检测
# ============================================================

def _detect_straight(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """顺子：≥5张连续单牌，不含2和王"""
    if n < 5 or n > 12:
        return None
    # 每个点数恰好出现1次
    if any(c != 1 for c in rc.values()):
        return None
    ranks = sorted(rc.keys())
    seq = _find_consecutive(ranks, n)
    if seq:
        return PlayedHand(HandType.STRAIGHT, cards, max(seq), chain_length=n)
    return None


def _detect_straight_pair(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """连对：≥3对连续对子，不含2和王"""
    if n < 6 or n % 2 != 0:
        return None
    pair_count = n // 2
    if pair_count < 3:
        return None
    # 每个点数恰好出现2次
    if any(c != 2 for c in rc.values()):
        return None
    ranks = sorted(rc.keys())
    seq = _find_consecutive(ranks, pair_count)
    if seq:
        return PlayedHand(HandType.STRAIGHT_PAIR, cards, max(seq), chain_length=pair_count)
    return None


# ============================================================
#  飞机类检测
# ============================================================

def _find_consecutive_triples(rc: Counter) -> Optional[List[Rank]]:
    """
    从 rank_counts 中找出所有 ≥3 次的点数，
    然后找到最长的连续序列（排除2和王）。
    返回排序后的连续三条点数列表，至少2组才算飞机。
    """
    triple_ranks = sorted(
        r for r, c in rc.items()
        if c >= 3 and r not in _CHAIN_FORBIDDEN
    )
    if len(triple_ranks) < 2:
        return None

    # 找最长连续子序列
    best = []
    current = [triple_ranks[0]]
    for i in range(1, len(triple_ranks)):
        if triple_ranks[i] - triple_ranks[i - 1] == 1:
            current.append(triple_ranks[i])
        else:
            if len(current) > len(best):
                best = current
            current = [triple_ranks[i]]
    if len(current) > len(best):
        best = current

    return best if len(best) >= 2 else None


def _detect_airplane(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """飞机不带：≥2组连续三条，不含2和王"""
    if n < 6 or n % 3 != 0:
        return None
    triple_count = n // 3
    if triple_count < 2:
        return None
    # 每个点数恰好出现3次
    if any(c != 3 for c in rc.values()):
        return None
    seq = _find_consecutive_triples(rc)
    if seq and len(seq) == triple_count:
        return PlayedHand(HandType.AIRPLANE, cards, max(seq), chain_length=triple_count)
    return None


def _detect_airplane_with_singles(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """飞机带单：连续三条 + 等量单牌"""
    seq = _find_consecutive_triples(rc)
    if not seq:
        return None
    triple_count = len(seq)
    # 飞机带单总张数 = 三条数×3 + 三条数×1 = 三条数×4
    if n != triple_count * 4:
        return None
    # 带的牌不能是炸弹（即不能有4张相同的作为翅膀）
    remaining_rc = Counter(rc)
    for r in seq:
        remaining_rc[r] -= 3
        if remaining_rc[r] == 0:
            del remaining_rc[r]
    # 剩余牌的张数应等于三条数
    if sum(remaining_rc.values()) != triple_count:
        return None
    return PlayedHand(
        HandType.AIRPLANE_WITH_SINGLES, cards, max(seq), chain_length=triple_count
    )


def _detect_airplane_with_pairs(cards: List[Card], n: int, rc: Counter) -> Optional[PlayedHand]:
    """飞机带对：连续三条 + 等量对子"""
    seq = _find_consecutive_triples(rc)
    if not seq:
        return None
    triple_count = len(seq)
    # 飞机带对总张数 = 三条数×3 + 三条数×2 = 三条数×5
    if n != triple_count * 5:
        return None
    # 去掉三条部分，剩余应全是对子
    remaining_rc = Counter(rc)
    for r in seq:
        remaining_rc[r] -= 3
        if remaining_rc[r] == 0:
            del remaining_rc[r]
    # 剩余每个点数恰好2张，且数量等于三条数
    if len(remaining_rc) != triple_count:
        return None
    if any(c != 2 for c in remaining_rc.values()):
        return None
    return PlayedHand(
        HandType.AIRPLANE_WITH_PAIRS, cards, max(seq), chain_length=triple_count
    )


# ============================================================
#  牌型比较
# ============================================================

def can_beat(current: PlayedHand, previous: PlayedHand) -> bool:
    """
    判断 current 能否压过 previous。
    规则：
    1. 火箭压一切
    2. 炸弹压非炸弹/非火箭，炸弹之间比点数
    3. 同类型同长度，比主牌点数
    """
    # 火箭压一切
    if current.type == HandType.ROCKET:
        return True
    if previous.type == HandType.ROCKET:
        return False

    # 炸弹逻辑
    if current.type == HandType.BOMB:
        if previous.type == HandType.BOMB:
            return current.main_rank > previous.main_rank
        return True  # 炸弹压非炸弹
    if previous.type == HandType.BOMB:
        return False  # 非炸弹不能压炸弹

    # 同类型同长度比较
    if current.type != previous.type:
        return False
    if current.chain_length != previous.chain_length:
        return False
    return current.main_rank > previous.main_rank
