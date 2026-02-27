# 🀄 AI 斗地主直播平台

三个 AI 智能体实时对战斗地主，WebSocket 驱动的前端可视化直播画面，支持 OBS 推流到抖音/B站等平台。

## 特性

- **完整斗地主引擎** — 支持所有标准牌型（顺子、连对、飞机、炸弹、火箭等）
- **双 AI 策略** — RuleAI 规则引擎 + LLM AI（接入 DeepSeek/OpenAI 等大模型）
- **实时直播画面** — 1920×1080 横屏 / 1080×1920 竖屏一键切换
- **AI 人格化** — 三个角色各有性格，LLM 生成策略解说文本
- **丰富动画** — 发牌飞入、底牌翻转、炸弹震屏、火箭特效
- **Web Audio 音效** — 纯合成音效，无需音频文件
- **累计积分系统** — 跨局积分排行榜，持久化记录
- **出牌历史** — 侧边栏实时记录每手出牌

## AI 角色

| 角色 | 性格 | 策略风格 |
|------|------|----------|
| 🔥 烈焰哥 | 激进、自信 | 进攻型，喜欢抢地主 |
| ❄️ 冰山姐 | 冷静、理性 | 防守型，善于配合 |
| 🎭 戏精弟 | 搞笑、夸张 | 随机型，出其不意 |

## 快速开始

### 环境要求

- Python 3.10+
- (可选) DeepSeek / OpenAI API Key（用于 LLM AI 模式）

### 安装

```bash
git clone https://github.com/your-username/zhibo_doudizhu.git
cd zhibo_doudizhu
pip install -r requirements.txt
```

### 配置 LLM（可选）

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

`.env` 支持为三个 AI 角色分别配置不同的模型和 API：

```env
AI_PLAYER1_API_KEY=your_api_key_here
AI_PLAYER1_BASE_URL=https://api.deepseek.com/v1
AI_PLAYER1_MODEL=deepseek-chat
```

> 未配置 API Key 时，系统自动降级为 RuleAI 规则引擎，无需联网即可运行。

## 使用方式

### Web 直播模式（推荐）

```bash
python -m uvicorn src.web.server:app --host 0.0.0.0 --port 8000
```

打开浏览器访问 `http://localhost:8000`，点击"开始对局"即可观看 AI 对战。

OBS 推流：添加"浏览器源"，URL 填 `http://localhost:8000`，分辨率设为 1920×1080（横屏）或 1080×1920（竖屏）。

### 终端 CLI 模式

```bash
# 单局对战
python -m src.main

# 多局连续对战
python -m src.main --rounds 10

# 快速模式（无延迟）
python -m src.main --fast
```

### Docker 部署

```bash
docker compose up --build
```

服务启动后访问 `http://localhost:8000`。

## 项目结构

```
zhibo_doudizhu/
├── src/
│   ├── engine/          # 斗地主核心引擎
│   │   ├── card.py          # 牌面定义（Rank, Suit, Card）
│   │   ├── hand_type.py     # 牌型枚举与 PlayedHand
│   │   └── hand_detector.py # 牌型检测与比较
│   ├── game/            # 对局管理
│   │   ├── player.py        # 玩家模型（手牌、角色、积分）
│   │   ├── game_state.py    # 对局状态机
│   │   └── controller.py    # 对局控制器（发牌、叫地主、出牌、结算）
│   ├── ai/              # AI 策略
│   │   ├── rule_ai.py       # 规则引擎（支持全牌型拆解）
│   │   └── llm_ai.py        # LLM AI（AsyncOpenAI + 人格化 Prompt）
│   ├── web/             # Web 直播服务
│   │   ├── server.py        # FastAPI + WebSocket 后端
│   │   └── static/          # 前端静态资源
│   │       ├── index.html
│   │       ├── app.js
│   │       └── style.css
│   └── ui/              # 终端可视化
│       └── renderer.py      # Rich 终端渲染器
├── tests/               # 测试
├── docs/                # 策划文档（10份）
├── main.py              # CLI 入口
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example         # 环境变量模板
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 实时通信 | WebSocket |
| AI 规则引擎 | 自研 RuleAI（全牌型拆解与评估） |
| AI 大模型 | AsyncOpenAI SDK（兼容 DeepSeek / OpenAI） |
| 前端渲染 | 原生 HTML/CSS/JS（无框架依赖） |
| 音效系统 | Web Audio API 合成音效 |
| 终端模式 | Rich 终端渲染 |
| 容器化 | Docker + Docker Compose |

## 支持的牌型

单张、对子、三条、三带一、三带二、顺子（5+张）、连对（3+对）、飞机、飞机带翅膀（单/对）、四带二（单/对）、炸弹、火箭（双王）。

## 测试

```bash
pytest tests/ -v
```

## 策划文档

| 编号 | 文档 | 内容 |
|------|------|------|
| 00 | [项目总纲](docs/00-项目总纲.md) | 项目全局视图、目标、架构、里程碑 |
| 01 | [斗地主规则](docs/01-斗地主规则-AI版.md) | 面向 AI 的完整斗地主规则定义 |
| 02 | [前端界面设计](docs/02-前端界面设计.md) | UI 布局、配色、组件设计 |
| 03 | [特效与动画](docs/03-特效与动画设计.md) | 游戏动画、特效、音效方案 |
| 04 | [OBS 直播方案](docs/04-OBS直播技术方案.md) | 推流配置、场景管理 |
| 05 | [礼物互动系统](docs/05-礼物互动系统.md) | 礼物监听、效果映射 |
| 06 | [赛事策划](docs/06-直播内容与赛事策划.md) | 直播节目编排、赛事体系 |
| 07 | [合规与风控](docs/07-抖音合规与风控.md) | 平台规则、合规策略 |
| 08 | [技术架构](docs/08-技术架构设计.md) | 系统架构、模块设计、技术选型 |
| 09 | [运营与商业化](docs/09-运营与商业化.md) | 运营策略、商业模式 |

## License

MIT
