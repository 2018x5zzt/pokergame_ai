"""游戏控制器 - 驱动斗地主一局游戏的完整流程"""

import random
from typing import List, Optional, Protocol

from src.engine.card import Card, create_deck, shuffle_and_deal
from src.engine.hand_type import HandType, PlayedHand
from src.engine.hand_detector import detect_hand, can_beat
from src.game.player import Player, Role
from src.game.game_state import GameState, GamePhase, GameEvent


class AIStrategy(Protocol):
    """AI 决策接口（策略模式）"""

    def decide_bid(self, player: Player, state: GameState) -> int:
        """决定叫分：0=不叫, 1/2/3=叫分"""
        ...

    def decide_play(self, player: Player, state: GameState) -> Optional[List[Card]]:
        """决定出牌：返回要出的牌列表，None=不出(PASS)"""
        ...


class GameController:
    """游戏控制器：驱动一局斗地主的完整流程"""

    def __init__(self, player_names: List[str], strategies: List[AIStrategy]):
        assert len(player_names) == 3 and len(strategies) == 3
        self.players = [
            Player(id=i, name=name) for i, name in enumerate(player_names)
        ]
        self.strategies = strategies
        self.state = GameState(players=self.players)
        self._callbacks: List = []  # 事件回调（用于 UI 通知）

    def on_event(self, callback) -> None:
        """注册事件回调"""
        self._callbacks.append(callback)

    def _emit(self, event: GameEvent) -> None:
        """触发事件通知"""
        self.state.events.append(event)
        for cb in self._callbacks:
            cb(event)

    # ============================================================
    #  发牌阶段
    # ============================================================

    def deal(self) -> None:
        """洗牌发牌"""
        self.state.phase = GamePhase.DEALING
        deck = create_deck()
        h1, h2, h3, dizhu = shuffle_and_deal(deck)

        self.players[0].hand = h1
        self.players[1].hand = h2
        self.players[2].hand = h3
        self.state.dizhu_cards = dizhu

        for p in self.players:
            p.sort_hand()

        # 随机选首叫玩家
        self.state.first_bidder = random.randint(0, 2)
        self.state.current_bidder = self.state.first_bidder
        self.state.phase = GamePhase.BIDDING

    # ============================================================
    #  叫地主阶段
    # ============================================================

    def run_bidding(self) -> bool:
        """
        执行叫地主流程。
        返回 True=成功确定地主，False=三人都不叫需重新发牌。
        """
        s = self.state
        for _ in range(3):
            pid = s.current_bidder
            player = self.players[pid]
            bid = self.strategies[pid].decide_bid(player, s)

            # 约束叫分合法性
            bid = self._validate_bid(bid)

            s.bid_scores[pid] = bid
            s.bid_round_done += 1

            self._emit(GameEvent(GamePhase.BIDDING, pid, "bid", bid))

            if bid > s.highest_bid:
                s.highest_bid = bid
                s.highest_bidder = pid

            # 叫3分直接确定
            if bid == 3:
                break

            s.current_bidder = (pid + 1) % 3

        # 判定结果
        if s.highest_bidder is None:
            return False  # 三人都不叫

        self._assign_landlord(s.highest_bidder)
        return True

    def _validate_bid(self, bid: int) -> int:
        """约束叫分合法性：必须高于当前最高叫分，或不叫(0)"""
        if bid <= 0:
            return 0
        if bid > 3:
            bid = 3
        if bid <= self.state.highest_bid:
            return 0  # 不够高，视为不叫
        return bid

    def _assign_landlord(self, pid: int) -> None:
        """确定地主：分配角色、发底牌"""
        landlord = self.players[pid]
        landlord.role = Role.LANDLORD
        landlord.hand.extend(self.state.dizhu_cards)
        landlord.sort_hand()

        for p in self.players:
            if p.id != pid:
                p.role = Role.FARMER

        self.state.current_player = pid
        self.state.phase = GamePhase.PLAYING

    # ============================================================
    #  出牌阶段
    # ============================================================

    def run_playing(self) -> None:
        """执行出牌流程，直到有人出完牌"""
        s = self.state
        while s.phase == GamePhase.PLAYING:
            self._play_one_turn()

    def _play_one_turn(self) -> None:
        """执行一个玩家的出牌回合"""
        s = self.state
        pid = s.current_player
        player = self.players[pid]

        # 判断是否自由出牌
        is_free = (s.last_play is None) or (s.pass_count >= 2)
        if is_free:
            s.last_play = None
            s.last_player = None
            s.pass_count = 0

        # AI 决策
        cards = self.strategies[pid].decide_play(player, s)

        if cards is None:
            # 不出 (PASS)
            self._handle_pass(pid)
        else:
            self._handle_play(pid, cards)

    def _handle_pass(self, pid: int) -> None:
        """处理不出"""
        s = self.state
        s.pass_count += 1
        self._emit(GameEvent(GamePhase.PLAYING, pid, "pass"))
        s.current_player = (pid + 1) % 3

    def _handle_play(self, pid: int, cards: List[Card]) -> None:
        """处理出牌"""
        s = self.state
        player = self.players[pid]

        # 验证手牌中有这些牌
        if not player.has_cards(cards):
            # AI 出了不存在的牌，强制 PASS
            self._handle_pass(pid)
            return

        # 识别牌型
        hand = detect_hand(cards)
        if hand is None:
            self._handle_pass(pid)
            return

        # 跟牌时验证能否压过
        if s.last_play is not None and not can_beat(hand, s.last_play):
            self._handle_pass(pid)
            return

        # 合法出牌
        player.remove_cards(cards)
        player.play_count += 1

        # 记录炸弹/火箭
        if hand.is_bomb_like:
            s.bomb_count += 1

        s.last_play = hand
        s.last_player = pid
        s.pass_count = 0
        s.play_history.append((pid, hand))

        self._emit(GameEvent(GamePhase.PLAYING, pid, "play", hand))

        # 检查是否出完
        if player.hand_size == 0:
            self._finish_game(pid)
            return

        s.current_player = (pid + 1) % 3

    # ============================================================
    #  结算阶段
    # ============================================================

    def _finish_game(self, winner_id: int) -> None:
        """游戏结束，计算结果"""
        s = self.state
        s.phase = GamePhase.FINISHED
        s.winner = winner_id

        landlord = next(p for p in self.players if p.is_landlord)
        farmers = [p for p in self.players if not p.is_landlord]

        # 春天判定：地主赢 + 农民都没出过牌 = 春天
        # 反春判定：农民赢 + 地主只出了一手牌 = 反春
        if landlord.id == winner_id:
            if all(f.play_count == 0 for f in farmers):
                s.is_spring = True
        else:
            if landlord.play_count <= 1:
                s.is_anti_spring = True

        multiplier = self._calc_multiplier()
        landlord_wins = (landlord.id == winner_id)
        self._settle_scores(landlord, farmers, multiplier, landlord_wins)

    def _calc_multiplier(self) -> int:
        """计算本局最终倍数"""
        s = self.state
        m = max(s.highest_bid, 1)  # 基础倍数（叫分值）
        m *= (2 ** s.bomb_count)   # 每个炸弹/火箭 ×2
        if s.is_spring or s.is_anti_spring:
            m *= 2
        return m

    @staticmethod
    def _settle_scores(
        landlord: Player,
        farmers: List[Player],
        multiplier: int,
        landlord_wins: bool,
    ) -> None:
        """结算积分"""
        if landlord_wins:
            landlord.score += 2 * multiplier
            for f in farmers:
                f.score -= multiplier
        else:
            landlord.score -= 2 * multiplier
            for f in farmers:
                f.score += multiplier

    # ============================================================
    #  完整游戏入口
    # ============================================================

    def run_game(self, max_redeal: int = 3) -> GameState:
        """
        运行一局完整游戏。
        max_redeal: 三人都不叫时最多重新发牌次数。
        """
        for _ in range(max_redeal):
            self._reset_round()
            self.deal()
            if self.run_bidding():
                break
        else:
            # 超过重发次数，强制第一个玩家当地主（叫1分）
            self.state.highest_bid = 1
            self._assign_landlord(self.state.first_bidder)

        self.run_playing()
        return self.state

    def _reset_round(self) -> None:
        """重置一轮的状态（用于重新发牌）"""
        for p in self.players:
            p.reset_for_new_game()
        self.state = GameState(players=self.players)
        self.state.events = []
