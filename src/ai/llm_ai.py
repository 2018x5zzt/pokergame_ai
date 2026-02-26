"""LLM AI - 基于大语言模型的出牌策略"""

import asyncio
import json
import logging
import os
from typing import List, Optional, Tuple

from openai import AsyncOpenAI

from src.engine.card import Card, Rank, Suit, RANK_DISPLAY
from src.engine.hand_detector import detect_hand, can_beat
from src.game.player import Player
from src.game.game_state import GameState
from src.ai.rule_ai import RuleAI

logger = logging.getLogger(__name__)

# 超时上限（秒）
LLM_TIMEOUT = 10

# 角色性格 prompt 片段
CHARACTER_PROMPTS = {
    "烈焰哥🔥": (
        "你是「烈焰哥」，性格激进、好胜、霸气。"
        "你喜欢主动出击，大牌先行，炸弹不留。"
        "口头禅风格：热血、张扬、自信爆棚。"
    ),
    "冰山姐❄️": (
        "你是「冰山姐」，性格冷静、稳健、善于防守。"
        "你喜欢先出小牌试探，保留大牌和炸弹作为后手。"
        "口头禅风格：冷淡、理性、一针见血。"
    ),
    "戏精弟🎭": (
        "你是「戏精弟」，性格花式、搞怪、出其不意。"
        "你喜欢出人意料的打法，偶尔故意示弱再反杀。"
        "口头禅风格：夸张、戏剧化、爱用网络梗。"
    ),
}

# 默认性格（兜底）
DEFAULT_CHARACTER_PROMPT = (
    "你是一个斗地主 AI 玩家，风格均衡。"
)


# ============================================================
#  序列化辅助
# ============================================================

def _card_str(c: Card) -> str:
    """卡牌 → 简短文本（如 ♠A, ♥3, 小王, 大王）"""
    return c.display


def _hand_str(cards: List[Card]) -> str:
    """手牌列表 → 空格分隔文本"""
    return " ".join(_card_str(c) for c in cards)


def _rank_from_display(text: str) -> Optional[Rank]:
    """从显示文本反查 Rank（如 'A' → Rank.ACE）"""
    _map = {v: k for k, v in RANK_DISPLAY.items()}
    return _map.get(text)


def _parse_card_text(text: str) -> Optional[Card]:
    """解析 LLM 返回的单张牌文本（如 '♠A', '小王'）"""
    text = text.strip()
    if text == "小王":
        return Card(rank=Rank.SMALL_JOKER, suit=Suit.JOKER)
    if text == "大王":
        return Card(rank=Rank.BIG_JOKER, suit=Suit.JOKER)
    if len(text) < 2:
        return None
    suit_char = text[0]
    rank_text = text[1:]
    suit_map = {"♠": Suit.SPADE, "♥": Suit.HEART, "♦": Suit.DIAMOND, "♣": Suit.CLUB}
    suit = suit_map.get(suit_char)
    if suit is None:
        return None
    rank = _rank_from_display(rank_text)
    if rank is None:
        return None
    return Card(rank=rank, suit=suit)


# ============================================================
#  Prompt 构建
# ============================================================

def _build_game_context(player: Player, state: GameState) -> str:
    """构建游戏状态上下文文本"""
    role_text = "地主" if player.is_landlord else "农民"
    lines = [
        f"你的座位号: {player.id}，角色: {role_text}",
        f"你的手牌({player.hand_size}张): {_hand_str(player.hand)}",
    ]
    # 其他玩家手牌数
    for p in state.players:
        if p.id != player.id:
            p_role = "地主" if p.is_landlord else "农民"
            lines.append(f"玩家{p.id}({p.name}, {p_role}): {p.hand_size}张")

    # 上一手牌
    if state.last_play is not None:
        last_cards = _hand_str(state.last_play.cards)
        lines.append(f"上一手出牌(玩家{state.last_player}): {last_cards}")
    else:
        lines.append("当前你是自由出牌（没有需要压的牌）")

    # 炸弹计数
    if state.bomb_count > 0:
        lines.append(f"本局已出炸弹/火箭: {state.bomb_count}个")

    return "\n".join(lines)


def _build_play_prompt(player: Player, state: GameState, character: str) -> str:
    """构建出牌决策 prompt"""
    char_prompt = CHARACTER_PROMPTS.get(character, DEFAULT_CHARACTER_PROMPT)
    context = _build_game_context(player, state)

    is_free = state.last_play is None
    constraint = "你可以自由出牌，选择任意合法牌型。" if is_free else (
        "你必须出比上一手更大的同类型牌，或者出炸弹/火箭。如果没有能压的牌，选择 PASS。"
    )

    return f"""{char_prompt}

你正在玩斗地主。请根据当前局面做出出牌决策。

【当前局面】
{context}

【规则约束】
{constraint}
合法牌型：单张、对子、三条、三带一、三带二、顺子(≥5张连续)、连对(≥3对连续)、飞机、四带二、炸弹(4张同点)、火箭(双王)。

【输出格式】严格返回 JSON，不要输出其他内容：
{{
  "action": "play" 或 "pass",
  "cards": ["♠A", "♥A"] (出的牌，pass时为空数组),
  "strategy": "一句话解说你的策略（15字以内，符合你的性格）"
}}"""


def _build_bid_prompt(player: Player, state: GameState, character: str) -> str:
    """构建叫分决策 prompt"""
    char_prompt = CHARACTER_PROMPTS.get(character, DEFAULT_CHARACTER_PROMPT)
    hand_text = _hand_str(player.hand)
    highest = state.highest_bid

    return f"""{char_prompt}

你正在玩斗地主，现在是叫地主阶段。请根据手牌强度决定叫分。

【你的手牌(17张)】
{hand_text}

【当前最高叫分】{highest}分（你必须叫比这更高的分，或者不叫）
叫分范围：0=不叫, 1分, 2分, 3分（必须高于当前最高分）

【判断依据】
- 有火箭(双王)：强烈建议叫3分
- 有炸弹(4张同点)：加分项
- 2和A多：加分项
- 手牌散乱无大牌：建议不叫

【输出格式】严格返回 JSON，不要输出其他内容：
{{
  "bid": 0-3的整数,
  "strategy": "一句话解说你的叫分理由（15字以内，符合你的性格）"
}}"""


# ============================================================
#  JSON 响应解析
# ============================================================

def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 返回文本中提取 JSON 对象（兼容 markdown 代码块包裹）"""
    text = text.strip()
    # 去除 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


# ============================================================
#  LlmAI 类
# ============================================================

class LlmAI:
    """基于 LLM 的斗地主 AI 策略。

    提供两套接口：
    - decide_bid / decide_play：同步方法，满足 AIStrategy Protocol，内部 fallback 到 RuleAI
    - async_decide_bid / async_decide_play：异步方法，供 server.py 层 await 调用
    """

    def __init__(
        self,
        character: str,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
    ):
        self.character = character
        self.model = model
        self._fallback = RuleAI()

        # 若未配置 API key，仅使用 fallback
        self._enabled = bool(api_key)
        if self._enabled:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        else:
            self._client = None
            logger.warning("LlmAI(%s): 未配置 API key，将使用 RuleAI fallback", character)

    # ----------------------------------------------------------
    #  同步接口（AIStrategy Protocol 兼容，fallback 到 RuleAI）
    # ----------------------------------------------------------

    def decide_bid(self, player: Player, state: GameState) -> int:
        """同步叫分 - 直接委托 RuleAI"""
        return self._fallback.decide_bid(player, state)

    def decide_play(self, player: Player, state: GameState) -> Optional[List[Card]]:
        """同步出牌 - 直接委托 RuleAI"""
        return self._fallback.decide_play(player, state)

    # ----------------------------------------------------------
    #  LLM 通用调用（带超时 + 错误处理）
    # ----------------------------------------------------------

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """调用 LLM API，返回文本响应。超时或异常返回 None。"""
        if not self._enabled or self._client is None:
            return None
        try:
            resp = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=256,
                ),
                timeout=LLM_TIMEOUT,
            )
            content = resp.choices[0].message.content
            logger.info("LlmAI(%s) 响应: %s", self.character, content[:200])
            return content
        except asyncio.TimeoutError:
            logger.warning("LlmAI(%s): LLM 调用超时(%ds)", self.character, LLM_TIMEOUT)
            return None
        except Exception as e:
            logger.warning("LlmAI(%s): LLM 调用异常: %s", self.character, e)
            return None

    # ----------------------------------------------------------
    #  异步叫分
    # ----------------------------------------------------------

    async def async_decide_bid(
        self, player: Player, state: GameState
    ) -> Tuple[int, str]:
        """异步叫分，返回 (bid, strategy_text)。失败时 fallback 到 RuleAI。"""
        prompt = _build_bid_prompt(player, state, self.character)
        raw = await self._call_llm(prompt)

        if raw is not None:
            data = _extract_json(raw)
            if data is not None:
                bid = data.get("bid", 0)
                strategy = data.get("strategy", "")
                # 校验叫分合法性
                if isinstance(bid, (int, float)) and 0 <= int(bid) <= 3:
                    bid = int(bid)
                    if bid == 0 or bid > state.highest_bid:
                        return bid, strategy
                logger.warning("LlmAI(%s): 叫分值非法 bid=%s", self.character, bid)

        # fallback
        fb_bid = self._fallback.decide_bid(player, state)
        return fb_bid, ""

    # ----------------------------------------------------------
    #  异步出牌
    # ----------------------------------------------------------

    async def async_decide_play(
        self, player: Player, state: GameState
    ) -> Tuple[Optional[List[Card]], str]:
        """异步出牌，返回 (cards_or_None, strategy_text)。失败时 fallback 到 RuleAI。"""
        prompt = _build_play_prompt(player, state, self.character)
        raw = await self._call_llm(prompt)

        if raw is not None:
            result = self._parse_play_response(raw, player, state)
            if result is not None:
                return result

        # fallback
        fb_cards = self._fallback.decide_play(player, state)
        return fb_cards, ""

    # ----------------------------------------------------------
    #  出牌响应解析与验证
    # ----------------------------------------------------------

    def _parse_play_response(
        self, raw: str, player: Player, state: GameState
    ) -> Optional[Tuple[Optional[List[Card]], str]]:
        """解析 LLM 出牌响应，验证合法性。返回 None 表示解析失败需 fallback。"""
        data = _extract_json(raw)
        if data is None:
            logger.warning("LlmAI(%s): JSON 解析失败", self.character)
            return None

        action = data.get("action", "").lower()
        strategy = data.get("strategy", "")

        # PASS
        if action == "pass":
            if state.last_play is None:
                # 自由出牌不允许 pass，fallback
                logger.warning("LlmAI(%s): 自由出牌时选择 pass，fallback", self.character)
                return None
            return None, strategy

        # PLAY
        if action != "play":
            logger.warning("LlmAI(%s): 未知 action=%s", self.character, action)
            return None

        card_texts = data.get("cards", [])
        if not card_texts or not isinstance(card_texts, list):
            logger.warning("LlmAI(%s): cards 字段为空或非数组", self.character)
            return None

        return self._validate_cards(card_texts, player, state, strategy)

    def _validate_cards(
        self,
        card_texts: List[str],
        player: Player,
        state: GameState,
        strategy: str,
    ) -> Optional[Tuple[Optional[List[Card]], str]]:
        """解析卡牌文本并验证：手牌持有、牌型合法、能否压过上家。"""
        # 1. 解析文本 → Card 对象
        parsed: List[Card] = []
        for t in card_texts:
            c = _parse_card_text(t)
            if c is None:
                logger.warning("LlmAI(%s): 无法解析卡牌 '%s'", self.character, t)
                return None
            parsed.append(c)

        # 2. 检查玩家是否持有这些牌
        if not player.has_cards(parsed):
            logger.warning("LlmAI(%s): 手牌中不包含所出的牌", self.character)
            return None

        # 3. 检测牌型
        hand = detect_hand(parsed)
        if hand is None:
            logger.warning("LlmAI(%s): 所出的牌不构成合法牌型", self.character)
            return None

        # 4. 跟牌时检查能否压过上家
        if state.last_play is not None and not can_beat(hand, state.last_play):
            logger.warning("LlmAI(%s): 所出的牌无法压过上家", self.character)
            return None

        return parsed, strategy


# ============================================================
#  工厂函数：从环境变量创建三个 LLM AI 实例
# ============================================================

def create_llm_players(names: List[str]) -> List[LlmAI]:
    """根据环境变量创建三个 LlmAI 实例（对应三位玩家）。

    环境变量命名规则：
      AI_PLAYER{i}_API_KEY / AI_PLAYER{i}_BASE_URL / AI_PLAYER{i}_MODEL
    未配置 API key 的玩家自动 fallback 到 RuleAI。
    """
    players: List[LlmAI] = []
    for i, name in enumerate(names):
        idx = i + 1  # 环境变量从 1 开始
        api_key = os.getenv(f"AI_PLAYER{idx}_API_KEY", "")
        base_url = os.getenv(f"AI_PLAYER{idx}_BASE_URL", "https://api.deepseek.com/v1")
        model = os.getenv(f"AI_PLAYER{idx}_MODEL", "deepseek-chat")
        players.append(LlmAI(
            character=name,
            api_key=api_key,
            base_url=base_url,
            model=model,
        ))
    return players
