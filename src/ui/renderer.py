"""终端可视化渲染器 - 在终端中展示斗地主对局过程"""

import os
import time
from typing import List, Optional

from src.engine.card import Card, RANK_DISPLAY
from src.engine.hand_type import HandType, PlayedHand
from src.game.player import Player, Role
from src.game.game_state import GameState, GamePhase, GameEvent


# 颜色常量 (ANSI)
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# 角色颜色映射
ROLE_COLOR = {
    Role.LANDLORD: RED,
    Role.FARMER: GREEN,
    Role.UNKNOWN: DIM,
}

# 牌型中文名
HAND_TYPE_NAME = {
    HandType.SINGLE: "单张",
    HandType.PAIR: "对子",
    HandType.TRIPLE: "三条",
    HandType.TRIPLE_WITH_SINGLE: "三带一",
    HandType.TRIPLE_WITH_PAIR: "三带二",
    HandType.STRAIGHT: "顺子",
    HandType.STRAIGHT_PAIR: "连对",
    HandType.AIRPLANE: "飞机",
    HandType.AIRPLANE_WITH_SINGLES: "飞机带翅膀(单)",
    HandType.AIRPLANE_WITH_PAIRS: "飞机带翅膀(对)",
    HandType.FOUR_WITH_TWO_SINGLES: "四带二(单)",
    HandType.FOUR_WITH_TWO_PAIRS: "四带二(对)",
    HandType.BOMB: "炸弹 💣",
    HandType.ROCKET: "火箭 🚀",
}


class TerminalRenderer:
    """终端可视化渲染器"""

    def __init__(self, delay: float = 0.8):
        self.delay = delay  # 每步之间的延迟（秒）

    def clear(self) -> None:
        """清屏"""
        os.system("clear" if os.name != "nt" else "cls")

    def pause(self, seconds: float = 0) -> None:
        """暂停"""
        time.sleep(seconds or self.delay)

    # ============================================================
    #  牌面渲染
    # ============================================================

    @staticmethod
    def format_cards(cards: List[Card]) -> str:
        """将牌列表格式化为彩色字符串"""
        parts = []
        for c in cards:
            display = c.display
            # 红色花色高亮
            if c.suit.value in ("♥", "♦"):
                parts.append(f"{RED}{display}{RESET}")
            elif c.suit.value == "🃏":
                if "大" in display:
                    parts.append(f"{RED}{BOLD}{display}{RESET}")
                else:
                    parts.append(f"{CYAN}{display}{RESET}")
            else:
                parts.append(display)
        return " ".join(parts)

    @staticmethod
    def format_player_name(player: Player) -> str:
        """格式化玩家名（带角色颜色）"""
        color = ROLE_COLOR.get(player.role, DIM)
        role_tag = ""
        if player.role == Role.LANDLORD:
            role_tag = " [地主👑]"
        elif player.role == Role.FARMER:
            role_tag = " [农民🌾]"
        return f"{color}{BOLD}{player.name}{role_tag}{RESET}"

    # ============================================================
    #  分隔线与标题
    # ============================================================

    @staticmethod
    def separator(char: str = "─", width: int = 60) -> str:
        return char * width

    def print_header(self, title: str) -> None:
        """打印带框的标题"""
        print(f"\n{YELLOW}{BOLD}{'═' * 60}{RESET}")
        print(f"{YELLOW}{BOLD}  {title}{RESET}")
        print(f"{YELLOW}{BOLD}{'═' * 60}{RESET}\n")

    # ============================================================
    #  发牌阶段展示
    # ============================================================

    def show_deal(self, players: List[Player], dizhu_cards: List[Card]) -> None:
        """展示发牌结果"""
        self.print_header("🃏 发牌完成")
        for p in players:
            name = self.format_player_name(p)
            cards = self.format_cards(p.hand)
            print(f"  {name} ({p.hand_size}张): {cards}")
        print(f"\n  {MAGENTA}底牌: {self.format_cards(dizhu_cards)}{RESET}")
        print()

    # ============================================================
    #  叫地主阶段展示
    # ============================================================

    def show_bid(self, player: Player, bid: int) -> None:
        """展示一次叫分"""
        name = self.format_player_name(player)
        if bid == 0:
            print(f"  {name}: {DIM}不叫{RESET}")
        else:
            print(f"  {name}: {YELLOW}叫 {bid} 分！{RESET}")

    def show_landlord(self, player: Player, dizhu_cards: List[Card]) -> None:
        """展示地主确定"""
        name = self.format_player_name(player)
        print(f"\n  🎉 {name} 成为地主！")
        print(f"  底牌亮出: {self.format_cards(dizhu_cards)}")
        print(f"  地主手牌 ({player.hand_size}张): {self.format_cards(player.hand)}")
        print()

    # ============================================================
    #  出牌阶段展示
    # ============================================================

    def show_play(self, player: Player, hand: PlayedHand) -> None:
        """展示一次出牌"""
        name = self.format_player_name(player)
        type_name = HAND_TYPE_NAME.get(hand.type, str(hand.type))
        cards_str = self.format_cards(hand.cards)
        print(f"  {name} 出牌 [{type_name}]: {cards_str}  (剩余{player.hand_size}张)")

    def show_pass(self, player: Player) -> None:
        """展示不出"""
        name = self.format_player_name(player)
        print(f"  {name}: {DIM}不出{RESET}")

    # ============================================================
    #  结算阶段展示
    # ============================================================

    def show_result(self, state: GameState, players: List[Player]) -> None:
        """展示游戏结果"""
        self.print_header("🏆 游戏结束")

        winner = players[state.winner]
        name = self.format_player_name(winner)
        side = "地主" if winner.is_landlord else "农民"
        print(f"  胜利方: {name} ({side}方获胜)")

        if state.is_spring:
            print(f"  {RED}{BOLD}  🌸 春天！地主一张没出！{RESET}")
        elif state.is_anti_spring:
            print(f"  {RED}{BOLD}  🌸 反春天！农民一张没出！{RESET}")

        if state.bomb_count > 0:
            print(f"  炸弹/火箭数: {state.bomb_count}")

        print(f"  叫分: {state.highest_bid}  最终倍数: {self._calc_display_mult(state)}")
        print(f"\n  {self.separator('─', 40)}")
        print(f"  {'玩家':<12} {'角色':<8} {'积分变化':<10}")
        print(f"  {self.separator('─', 40)}")
        for p in players:
            role = "地主" if p.is_landlord else "农民"
            sign = "+" if p.score > 0 else ""
            print(f"  {p.name:<10} {role:<6} {sign}{p.score}")
        print()

    @staticmethod
    def _calc_display_mult(state: GameState) -> int:
        """计算展示用倍数"""
        m = max(state.highest_bid, 1)
        m *= (2 ** state.bomb_count)
        if state.is_spring or state.is_anti_spring:
            m *= 2
        return m

    # ============================================================
    #  事件回调（注册到 GameController）
    # ============================================================

    def make_event_callback(self, players: List[Player]):
        """创建事件回调函数，供 GameController.on_event() 使用"""
        renderer = self

        def callback(event: GameEvent) -> None:
            pid = event.player_id
            player = players[pid]

            if event.phase == GamePhase.BIDDING and event.action == "bid":
                renderer.show_bid(player, event.data)
                renderer.pause(0.5)

            elif event.phase == GamePhase.PLAYING:
                if event.action == "play":
                    renderer.show_play(player, event.data)
                    renderer.pause()
                elif event.action == "pass":
                    renderer.show_pass(player)
                    renderer.pause(0.3)

        return callback
