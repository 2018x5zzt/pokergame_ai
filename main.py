"""斗地主 AI 对局 - 主入口"""

import sys
import argparse

from src.ai.rule_ai import RuleAI
from src.ai.llm_ai import LlmAI
from src.game.controller import GameController
from src.ui.renderer import TerminalRenderer


def create_players():
    """创建三个 AI 角色"""
    names = ["烈焰哥🔥", "冰山姐❄️", "戏精弟🎭"]
    strategies = [RuleAI(), RuleAI(), RuleAI()]
    return names, strategies


def run_one_game(delay: float = 0.8) -> None:
    """运行一局完整对局"""
    renderer = TerminalRenderer(delay=delay)
    names, strategies = create_players()

    gc = GameController(player_names=names, strategies=strategies)

    # 注册可视化回调
    cb = renderer.make_event_callback(gc.players)
    gc.on_event(cb)

    renderer.clear()
    renderer.print_header("🀄 AI 斗地主对局开始")

    # 发牌
    gc.deal()
    renderer.show_deal(gc.players, gc.state.dizhu_cards)
    renderer.pause(1.0)

    # 叫地主
    renderer.print_header("📢 叫地主阶段")
    success = gc.run_bidding()

    if not success:
        print("  三人都不叫，重新发牌...")
        gc._reset_round()
        gc.deal()
        renderer.show_deal(gc.players, gc.state.dizhu_cards)
        gc.state.highest_bid = 1
        gc._assign_landlord(gc.state.first_bidder)

    # 展示地主信息
    landlord = next(p for p in gc.players if p.is_landlord)
    renderer.show_landlord(landlord, gc.state.dizhu_cards)
    renderer.pause(1.0)

    # 出牌
    renderer.print_header("🎴 出牌阶段")
    gc.run_playing()

    # 结算
    renderer.show_result(gc.state, gc.players)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="AI 斗地主对局")
    parser.add_argument("--rounds", type=int, default=1, help="对局数 (默认1)")
    parser.add_argument("--delay", type=float, default=0.8, help="出牌延迟秒数 (默认0.8)")
    parser.add_argument("--fast", action="store_true", help="快速模式 (无延迟)")
    args = parser.parse_args()

    delay = 0.0 if args.fast else args.delay

    for i in range(args.rounds):
        if args.rounds > 1:
            print(f"\n{'=' * 60}")
            print(f"  第 {i + 1}/{args.rounds} 局")
            print(f"{'=' * 60}")
        run_one_game(delay=delay)


if __name__ == "__main__":
    main()
