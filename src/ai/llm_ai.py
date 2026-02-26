"""LLM AI - 基于大语言模型的出牌策略（接口桩）"""

from typing import List, Optional

from src.engine.card import Card
from src.game.player import Player
from src.game.game_state import GameState
from src.ai.rule_ai import RuleAI


class LlmAI:
    """
    基于 LLM 的 AI 策略。
    当前为桩实现，内部回退到 RuleAI。
    后续接入国产大模型 API（OpenAI 兼容接口）。
    """

    def __init__(self, character: str = "default", api_key: str = "", base_url: str = ""):
        self.character = character  # 角色性格：烈焰哥/冰山姐/戏精弟
        self.api_key = api_key
        self.base_url = base_url
        self._fallback = RuleAI()

    def decide_bid(self, player: Player, state: GameState) -> int:
        """叫分决策 - 当前回退到规则引擎"""
        # TODO: 接入 LLM，根据角色性格生成叫分决策
        return self._fallback.decide_bid(player, state)

    def decide_play(self, player: Player, state: GameState) -> Optional[List[Card]]:
        """出牌决策 - 当前回退到规则引擎"""
        # TODO: 接入 LLM，根据角色性格生成出牌决策
        return self._fallback.decide_play(player, state)
