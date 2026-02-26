"""WebSocket 后端服务 - 驱动对局并实时推送事件到前端"""

import asyncio
import json
import random
from typing import List, Set
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.engine.card import Card, Rank, RANK_DISPLAY
from src.engine.hand_type import HandType, PlayedHand
from src.engine.hand_detector import detect_hand, can_beat
from src.game.player import Player, Role
from src.game.game_state import GameState, GamePhase, GameEvent
from src.game.controller import GameController
from src.ai.rule_ai import RuleAI


# 牌型中文名
HAND_TYPE_NAME = {
    HandType.SINGLE: "单张", HandType.PAIR: "对子",
    HandType.TRIPLE: "三条", HandType.TRIPLE_WITH_SINGLE: "三带一",
    HandType.TRIPLE_WITH_PAIR: "三带二", HandType.STRAIGHT: "顺子",
    HandType.STRAIGHT_PAIR: "连对", HandType.AIRPLANE: "飞机",
    HandType.AIRPLANE_WITH_SINGLES: "飞机带翅膀(单)",
    HandType.AIRPLANE_WITH_PAIRS: "飞机带翅膀(对)",
    HandType.FOUR_WITH_TWO_SINGLES: "四带二(单)",
    HandType.FOUR_WITH_TWO_PAIRS: "四带二(对)",
    HandType.BOMB: "炸弹", HandType.ROCKET: "火箭",
}

# AI 策略描述（用于直播展示）
def describe_strategy(player: Player, state: GameState, cards, is_pass: bool) -> str:
    """生成 AI 出牌策略的简短描述"""
    hand = player.hand
    rc = Counter(c.rank for c in hand)
    hand_size = len(hand)

    if is_pass:
        if state.last_play and state.last_play.is_bomb_like:
            return "对方炸弹太大，忍一手"
        if state.last_play and state.last_play.main_rank and state.last_play.main_rank >= Rank.ACE:
            return "大牌压不住，选择不出"
        return "暂时不出，等待时机"

    if not cards:
        return ""

    played = detect_hand(cards)
    if not played:
        return ""

    if hand_size == 0:
        return "最后一手牌，直接清空！"

    if played.type == HandType.ROCKET:
        return "王炸！一锤定音！"
    if played.type == HandType.BOMB:
        return "炸弹出击！"

    if state.last_play is None:
        # 自由出牌
        if hand_size <= 3:
            return f"只剩{hand_size}张，准备收尾"
        if played.main_rank and played.main_rank <= Rank.SEVEN:
            return "先出小牌试探"
        return "主动出击"
    else:
        # 跟牌
        if played.main_rank and played.main_rank >= Rank.TWO:
            return "大牌压制！"
        return "跟牌压制"


# ============================================================
#  序列化工具
# ============================================================

def card_to_dict(c: Card) -> dict:
    """将 Card 序列化为前端可用的 dict"""
    return {
        "rank": int(c.rank),
        "suit": c.suit.value,
        "display": c.display,
    }


def player_to_dict(p: Player) -> dict:
    """将 Player 序列化"""
    return {
        "id": p.id,
        "name": p.name,
        "role": p.role.value,
        "hand_size": p.hand_size,
        "hand": [card_to_dict(c) for c in p.hand],
    }


# ============================================================
#  FastAPI 应用
# ============================================================

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI 斗地主")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# WebSocket 连接池
connections: Set[WebSocket] = set()


async def broadcast_thinking(player_id: int, phase: str, seconds: int) -> None:
    """广播 AI 思考倒计时：先发 thinking 开始，然后逐秒倒计时"""
    await broadcast({
        "type": "thinking",
        "player_id": player_id,
        "phase": phase,
        "total": seconds,
        "remaining": seconds,
    })
    for i in range(seconds, 0, -1):
        await asyncio.sleep(1.0)
        await broadcast({
            "type": "countdown",
            "player_id": player_id,
            "remaining": i - 1,
        })


def get_thinking_seconds(phase: str) -> int:
    """获取思考时间（秒），带随机波动模拟真实感"""
    if phase == "bid":
        return random.randint(2, 4)
    else:  # play
        return random.randint(2, 5)


async def broadcast(msg: dict) -> None:
    """向所有连接的客户端广播消息"""
    data = json.dumps(msg, ensure_ascii=False)
    dead = set()
    for ws in connections:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    connections.difference_update(dead)


@app.get("/")
async def index():
    """返回前端页面"""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket 端点：客户端连接后等待 start 指令"""
    await ws.accept()
    connections.add(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "start":
                await run_game_async()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        connections.discard(ws)


# ============================================================
#  异步对局驱动
# ============================================================

async def run_game_async() -> None:
    """异步驱动一局完整对局，每步实时推送事件到前端"""
    names = ["烈焰哥🔥", "冰山姐❄️", "戏精弟🎭"]
    strategies = [RuleAI(), RuleAI(), RuleAI()]
    gc = GameController(player_names=names, strategies=strategies)

    # 发牌
    gc.deal()

    # 逐张发牌动画：先发空手牌，再逐张添加
    await broadcast({
        "type": "deal_start",
        "players": [{"id": p.id, "name": p.name} for p in gc.players],
    })
    await asyncio.sleep(0.5)

    # 模拟逐张发牌（每人17张，轮流发）
    deal_order = []
    for i in range(17):
        for pid in range(3):
            deal_order.append((pid, gc.players[pid].hand[i]))

    for idx, (pid, card) in enumerate(deal_order):
        await broadcast({
            "type": "deal_card",
            "player_id": pid,
            "card": card_to_dict(card),
            "card_index": idx // 3,
        })
        # 每3张一组稍快，组间稍慢
        await asyncio.sleep(0.04)

    # 发牌完成，发送完整手牌
    await broadcast({
        "type": "deal_done",
        "players": [player_to_dict(p) for p in gc.players],
        "dizhu_cards": [card_to_dict(c) for c in gc.state.dizhu_cards],
    })
    await asyncio.sleep(1.0)

    # 叫地主阶段（异步逐步，带思考倒计时）
    await run_bidding_async(gc, strategies)

    if gc.state.highest_bidder is None:
        gc.state.highest_bid = 1
        gc._assign_landlord(gc.state.first_bidder)
    else:
        gc._assign_landlord(gc.state.highest_bidder)

    # 地主确定
    landlord = next(p for p in gc.players if p.is_landlord)
    await broadcast({
        "type": "landlord",
        "player_id": landlord.id,
        "players": [player_to_dict(p) for p in gc.players],
        "dizhu_cards": [card_to_dict(c) for c in gc.state.dizhu_cards],
        "highest_bid": gc.state.highest_bid,
    })
    await asyncio.sleep(1.5)

    # 出牌阶段：逐步执行，每步实时推送
    await run_playing_async(gc, strategies)


# ============================================================
#  异步叫地主（带思考倒计时）
# ============================================================

async def run_bidding_async(gc: GameController, strategies) -> None:
    """异步执行叫地主，每人决策前有思考倒计时"""
    s = gc.state
    for _ in range(3):
        pid = s.current_bidder
        player = gc.players[pid]

        # 思考倒计时
        think_time = get_thinking_seconds("bid")
        await broadcast_thinking(pid, "bid", think_time)

        # AI 决策
        bid = strategies[pid].decide_bid(player, s)
        bid = gc._validate_bid(bid)

        s.bid_scores[pid] = bid
        s.bid_round_done += 1
        gc._emit(GameEvent(GamePhase.BIDDING, pid, "bid", bid))

        if bid > s.highest_bid:
            s.highest_bid = bid
            s.highest_bidder = pid

        # 广播叫分结果
        await broadcast({
            "type": "bid",
            "player_id": pid,
            "bid": bid,
        })
        await asyncio.sleep(0.8)

        if bid == 3:
            break
        s.current_bidder = (pid + 1) % 3


# ============================================================
#  逐步异步出牌（带思考倒计时）
# ============================================================

async def run_playing_async(gc: GameController, strategies) -> None:
    """逐步执行出牌，每步实时推送正确的手牌和 hand_size"""
    s = gc.state

    while s.phase == GamePhase.PLAYING:
        pid = s.current_player
        player = gc.players[pid]

        # 判断是否自由出牌
        is_free = (s.last_play is None) or (s.pass_count >= 2)
        if is_free:
            s.last_play = None
            s.last_player = None
            s.pass_count = 0

        # 思考倒计时
        think_time = get_thinking_seconds("play")
        await broadcast_thinking(pid, "play", think_time)

        # AI 决策
        cards = strategies[pid].decide_play(player, s)

        if cards is None:
            # 不出 (PASS)
            strategy_text = describe_strategy(player, s, None, True)
            s.pass_count += 1
            gc._emit(GameEvent(GamePhase.PLAYING, pid, "pass"))
            s.current_player = (pid + 1) % 3

            await broadcast({
                "type": "pass",
                "player_id": pid,
                "strategy": strategy_text,
            })
            await asyncio.sleep(0.5)
        else:
            # 出牌前生成策略描述
            strategy_text = describe_strategy(player, s, cards, False)

            # 验证并执行出牌
            if not player.has_cards(cards):
                s.pass_count += 1
                s.current_player = (pid + 1) % 3
                continue

            hand = detect_hand(cards)
            if hand is None:
                s.pass_count += 1
                s.current_player = (pid + 1) % 3
                continue

            if s.last_play is not None and not can_beat(hand, s.last_play):
                s.pass_count += 1
                s.current_player = (pid + 1) % 3
                continue

            # 合法出牌：先移除手牌
            player.remove_cards(cards)
            player.play_count += 1

            if hand.is_bomb_like:
                s.bomb_count += 1

            s.last_play = hand
            s.last_player = pid
            s.pass_count = 0
            s.play_history.append((pid, hand))
            gc._emit(GameEvent(GamePhase.PLAYING, pid, "play", hand))

            # 实时推送：此时 hand_size 是准确的
            await broadcast({
                "type": "play",
                "player_id": pid,
                "hand_type": HAND_TYPE_NAME.get(hand.type, ""),
                "cards": [card_to_dict(c) for c in hand.cards],
                "is_bomb": hand.is_bomb_like,
                "hand_size": player.hand_size,
                "hand": [card_to_dict(c) for c in player.hand],
                "strategy": strategy_text,
            })
            delay = 1.2 if hand.is_bomb_like else 0.6
            await asyncio.sleep(delay)

            # 检查是否出完
            if player.hand_size == 0:
                gc._finish_game(pid)
                break

            s.current_player = (pid + 1) % 3

    # 结算
    await send_result(gc)


async def send_result(gc: GameController) -> None:
    """推送结算信息"""
    s = gc.state
    winner = gc.players[s.winner]
    m = max(s.highest_bid, 1) * (2 ** s.bomb_count)
    if s.is_spring or s.is_anti_spring:
        m *= 2

    await broadcast({
        "type": "result",
        "winner_id": s.winner,
        "winner_name": winner.name,
        "winner_is_landlord": winner.is_landlord,
        "is_spring": s.is_spring,
        "is_anti_spring": s.is_anti_spring,
        "bomb_count": s.bomb_count,
        "multiplier": m,
        "scores": [
            {"name": p.name, "role": p.role.value, "score": p.score}
            for p in gc.players
        ],
    })
