# 04 - OBS 直播技术方案

> AI 斗地主直播项目 · 技术文档
> 版本：v1.0 | 最后更新：2026-02-25

---

## 目录

1. [概述](#1-概述)
2. [OBS Studio 基础配置](#2-obs-studio-基础配置)
3. [抖音直播推流地址获取](#3-抖音直播推流地址获取)
4. [画面捕获方案选择](#4-画面捕获方案选择)
5. [多场景切换设计](#5-多场景切换设计)
6. [音频配置方案](#6-音频配置方案)
7. [OBS WebSocket 自动化控制](#7-obs-websocket-自动化控制)
8. [网络要求与稳定性保障](#8-网络要求与稳定性保障)
9. [备用方案与容灾策略](#9-备用方案与容灾策略)
10. [推流参数优化建议](#10-推流参数优化建议)
11. [多平台同时推流方案](#11-多平台同时推流方案)
12. [附录](#12-附录)

---

## 1. 概述

### 1.1 文档目的

本文档详细描述 AI 斗地主直播项目中，从游戏画面渲染到抖音直播推流的完整技术链路，涵盖 OBS Studio 配置、场景管理、音频混合、自动化控制、网络保障及多平台推流等全部环节。

### 1.2 技术链路总览

```
┌─────────────┐    窗口捕获     ┌─────────────┐    RTMP推流     ┌─────────────┐
│  游戏前端    │ ──────────────→ │  OBS Studio │ ──────────────→ │  抖音直播    │
│  (浏览器)    │                 │  (编码+混流) │                 │  (CDN分发)   │
└─────────────┘                 └─────────────┘                 └─────────────┘
       ↑                              ↑ ↓                            ↑
  React+PixiJS                   WebSocket API                   RTMP/SRT
  渲染游戏画面                  自动化场景切换                   推流协议
```

### 1.3 环境要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 / macOS 12 | Windows 11 / macOS 14 |
| CPU | Intel i5-8400 / AMD R5 3600 | Intel i7-12700 / AMD R7 5800X |
| 内存 | 8GB | 16GB+ |
| 显卡 | GTX 1050 (NVENC支持) | RTX 3060+ |
| 网络上行 | 5 Mbps | 10 Mbps+ |
| OBS 版本 | 30.0+ | 30.2+ (最新稳定版) |

---

## 2. OBS Studio 基础配置

### 2.1 视频设置

#### 基础分辨率（画布大小）

```
推荐：1920×1080 (1080p)
```

抖音直播主流为竖屏（9:16），但斗地主游戏画面更适合横屏（16:9）展示。我们采用 **横屏 1080p** 方案，理由如下：

- 斗地主牌面信息量大，横屏能完整展示三家手牌区域
- 抖音支持横屏直播，观众可横屏观看
- 1080p 是抖音推荐的最高分辨率，画质清晰

#### 输出分辨率（缩放）

```
输出分辨率：1920×1080（不缩放）
缩放过滤器：Lanczos（锐化缩放，36采样）
```

> 如果机器性能不足，可降至 1280×720，但会损失画面细节。

#### 帧率设置

```
FPS 类型：常用 FPS 值
常用 FPS 值：30
```

| 帧率 | 适用场景 | 码率需求 |
|------|---------|---------|
| 24 fps | 极低性能机器 | 较低 |
| 30 fps | **推荐** - 斗地主节奏适中 | 适中 |
| 60 fps | 需要丝滑动画效果 | 较高 |

斗地主不是高速动作游戏，30fps 完全满足流畅度需求，且能显著降低编码压力和带宽消耗。

### 2.2 编码器设置

#### 编码器选择优先级

```
1. NVIDIA NVENC H.264 (硬件编码，推荐)
2. Apple VT H264 硬件编码器 (macOS)
3. AMD AMF H.264 (AMD显卡)
4. x264 (软件编码，CPU占用高)
```

#### NVENC H.264 推荐配置

```yaml
编码器:        NVIDIA NVENC H.264
码率控制:      CBR (恒定码率)
码率:          4000 Kbps
关键帧间隔:    2 秒
预设:          Quality (质量优先)
Profile:       high
Look-ahead:    开启
B帧数量:       2
```

#### x264 软件编码配置（备选）

```yaml
编码器:        x264
码率控制:      CBR
码率:          3500 Kbps
CPU 使用预设:  veryfast (平衡性能与质量)
Profile:       high
关键帧间隔:    2 秒
微调:          无
```

### 2.3 码率选择指南

| 分辨率 | 帧率 | 推荐码率 | 最低码率 | 上行带宽需求 |
|--------|------|---------|---------|-------------|
| 1920×1080 | 30fps | 4000 Kbps | 3000 Kbps | ≥6 Mbps |
| 1920×1080 | 60fps | 6000 Kbps | 4500 Kbps | ≥8 Mbps |
| 1280×720 | 30fps | 2500 Kbps | 1500 Kbps | ≥4 Mbps |

> **抖音码率上限**：抖音直播推流码率上限约为 8000 Kbps，超过可能被服务端限流。推荐不超过 6000 Kbps。

### 2.4 音频设置

```yaml
采样率:     44.1 kHz
声道:       立体声
音频码率:   128 Kbps (AAC)
```

### 2.5 高级设置

```yaml
进程优先级:       高于正常
渲染器:           Direct3D 11 (Windows) / Metal (macOS)
颜色格式:         NV12
色彩空间:         709
色彩范围:         部分
```

---

## 3. 抖音直播推流地址获取

### 3.1 获取方式概览

抖音直播推流地址有以下几种获取途径：

| 方式 | 适用场景 | 难度 | 稳定性 |
|------|---------|------|--------|
| 抖音直播伴侣 | 官方工具，最简单 | ★☆☆ | ★★★ |
| 抖音创作者中心（网页版） | 电脑端操作 | ★★☆ | ★★★ |
| 抖音开放平台 API | 自动化获取 | ★★★ | ★★☆ |

### 3.2 方式一：抖音直播伴侣获取

1. 下载安装「抖音直播伴侣」（官方 PC 端推流工具）
2. 登录抖音账号
3. 选择「开始直播」→「游戏直播」
4. 在设置中找到「推流地址」，复制 RTMP URL 和推流码

```
推流地址格式：
  服务器:  rtmp://push.douyin.com/live/
  推流码:  stream_xxxxxx?wsSecret=xxx&wsTime=xxx
```

### 3.3 方式二：抖音创作者中心（网页版）

1. 访问 `https://creator.douyin.com`
2. 登录后进入「直播中心」→「开始直播」
3. 选择「推流直播」模式
4. 系统生成推流地址和推流码
5. 复制到 OBS 的「推流」设置中

> **注意**：推流地址有时效性，通常 24 小时内有效，每次开播需重新获取。

### 3.4 方式三：抖音开放平台 API（自动化）

适用于需要自动化开播的场景：

```python
# 伪代码 - 通过抖音开放平台获取推流地址
import requests

class DouyinLiveAPI:
    BASE_URL = "https://open.douyin.com"

    def __init__(self, client_key, client_secret):
        self.client_key = client_key
        self.client_secret = client_secret
        self.access_token = None

    def get_access_token(self):
        """获取 access_token"""
        resp = requests.post(f"{self.BASE_URL}/oauth/client_token/", json={
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "client_credential"
        })
        self.access_token = resp.json()["data"]["access_token"]

    def get_push_url(self, open_id):
        """获取推流地址（需要用户授权）"""
        resp = requests.post(
            f"{self.BASE_URL}/live/push_url/",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={"open_id": open_id}
        )
        data = resp.json()["data"]
        return {
            "rtmp_url": data["rtmp_url"],
            "stream_key": data["stream_key"]
        }
```

> **开放平台接入要求**：需要企业资质认证，个人开发者可先使用方式一或方式二。

### 3.5 OBS 推流设置

在 OBS 中配置推流地址：

```
设置 → 推流
  服务:     自定义
  服务器:   rtmp://push.douyin.com/live/
  推流码:   [从抖音获取的推流码]
```

---

## 4. 画面捕获方案选择

### 4.1 方案对比

| 特性 | 窗口捕获 | 显示捕获 | 浏览器源 |
|------|---------|---------|---------|
| 捕获范围 | 指定窗口 | 整个屏幕/显示器 | 内嵌网页 |
| 性能开销 | 低 | 中 | 低 |
| 窗口遮挡影响 | 不受影响(Windows) | 受影响 | 不受影响 |
| 画面裁剪 | 自动适配窗口 | 需手动裁剪 | 自动适配 |
| 多窗口支持 | 每个窗口单独捕获 | 捕获所有内容 | 单页面 |
| **推荐度** | **★★★** | ★★☆ | ★★★ |

### 4.2 推荐方案：窗口捕获 + 浏览器源混合

```
主画面：窗口捕获 → 游戏前端浏览器窗口
叠加层：浏览器源 → 直播信息覆盖层（弹幕、礼物特效、计分板）
```

#### 窗口捕获配置

```yaml
来源类型:     窗口捕获
窗口:         [Chrome/Edge - AI斗地主]
捕获方式:     Windows Graphics Capture (Win10+) / 自动 (macOS)
客户端区域:   启用（仅捕获窗口内容，不含标题栏）
```

#### 浏览器源配置（叠加层）

```yaml
来源类型:     浏览器
URL:          http://localhost:3001/overlay
宽度:         1920
高度:         1080
自定义CSS:    body { background: transparent !important; }
关闭时关闭源: 否
页面加载后刷新: 是
```

### 4.3 各平台捕获注意事项

#### Windows

- 优先使用 `Windows Graphics Capture` 方式，兼容性最好
- 如果游戏窗口使用硬件加速渲染，确保 OBS 以管理员权限运行
- 窗口最小化后仍可捕获（WGC 模式）

#### macOS

- macOS 需要在「系统设置 → 隐私与安全 → 屏幕录制」中授权 OBS
- 窗口捕获在 macOS 上性能优于显示捕获
- macOS Sonoma+ 可能需要额外的屏幕录制权限确认

### 4.4 画面布局设计

```
┌──────────────────────────────────────────────┐
│  ┌─ 顶部信息栏 ──────────────────────────┐   │
│  │ 🏆 第3局 | 底分×2 | 春天 | 观众: 1.2w │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  ┌──────┐    ┌──────────────┐    ┌──────┐    │
│  │ 左家  │    │   牌桌中央    │    │ 右家  │    │
│  │ 手牌  │    │  出牌区域     │    │ 手牌  │    │
│  │ 背面  │    │              │    │ 背面  │    │
│  └──────┘    └──────────────┘    └──────┘    │
│                                                │
│  ┌─ 底部玩家区 ──────────────────────────┐   │
│  │         当前玩家手牌（正面展示）         │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  ┌─ 底部信息 ─┐  ┌─ 礼物特效区 ─────────┐   │
│  │ AI思考状态  │  │ 🎁 观众互动信息       │   │
│  └────────────┘  └───────────────────────┘   │
└──────────────────────────────────────────────┘
```

---

## 5. 多场景切换设计

### 5.1 场景规划

本项目设计 5 个核心场景，覆盖直播全流程：

| 场景编号 | 场景名称 | 用途 | 触发时机 |
|---------|---------|------|---------|
| S1 | 开场/等待 | 直播开始前的等待画面 | 开播时 / 对局间隔 |
| S2 | 叫地主阶段 | 展示叫分过程 | 发牌完成后 |
| S3 | 对局进行中 | 核心游戏画面 | 叫地主结束后 |
| S4 | 结算画面 | 展示本局结果和数据 | 一局结束时 |
| S5 | 中场休息 | 插播内容/数据统计 | 每N局后 |

### 5.2 各场景详细设计

#### S1 - 开场/等待场景

```yaml
来源列表:
  - 图片源: 背景图（斗地主主题壁纸）
  - 文字源: "AI 斗地主直播 · 即将开始"（滚动文字）
  - 浏览器源: 倒计时组件 (http://localhost:3001/countdown)
  - 音频源: 背景音乐（轻松BGM循环播放）
  - 图片源: AI 内容标识水印（合规要求）
```

#### S2 - 叫地主阶段

```yaml
来源列表:
  - 窗口捕获: 游戏主窗口
  - 浏览器源: 叫分信息覆盖层
  - 浏览器源: 观众投票面板（"你觉得谁会当地主？"）
  - 音频源: 游戏音效 + 紧张BGM
  - 图片源: AI 内容标识水印
```

#### S3 - 对局进行中

```yaml
来源列表:
  - 窗口捕获: 游戏主窗口（全屏）
  - 浏览器源: 实时信息覆盖层（剩余牌数、当前倍数）
  - 浏览器源: 礼物特效层（透明背景）
  - 浏览器源: AI 思考气泡（展示AI决策过程）
  - 音频源: 游戏音效 + 出牌音效 + TTS解说
  - 图片源: AI 内容标识水印
```

#### S4 - 结算画面

```yaml
来源列表:
  - 窗口捕获: 游戏结算界面
  - 浏览器源: 详细数据面板（胜率、关键牌、精彩回放提示）
  - 浏览器源: 礼物贡献榜
  - 文字源: "下一局即将开始..."
  - 音频源: 胜利/失败音效 + 结算BGM
  - 图片源: AI 内容标识水印
```

#### S5 - 中场休息

```yaml
来源列表:
  - 图片源: 休息画面背景
  - 浏览器源: 战绩统计面板（总胜率、最佳牌局、礼物排行）
  - 浏览器源: 互动小游戏（观众猜牌等）
  - 文字源: "休息一下，马上回来"
  - 音频源: 轻松BGM
  - 图片源: AI 内容标识水印
```

### 5.3 场景切换转场效果

```yaml
转场类型:     淡入淡出 (Fade)
转场时长:     500ms
切换方式:     自动（由游戏引擎通过 WebSocket 触发）
```

| 切换路径 | 转场效果 | 时长 |
|---------|---------|------|
| S1 → S2 | 淡入淡出 | 800ms |
| S2 → S3 | 快速切换 | 300ms |
| S3 → S4 | 滑动（从右到左） | 600ms |
| S4 → S1/S3 | 淡入淡出 | 500ms |
| 任意 → S5 | 淡入淡出 | 1000ms |

---

## 6. 音频配置方案

### 6.1 音频源规划

本项目需要混合 4 路音频：

| 音频源 | 类型 | 用途 | 音量建议 |
|--------|------|------|---------|
| 游戏音效 | 应用音频捕获 | 出牌、叫地主等操作音效 | 70% |
| 背景音乐 | 媒体源 | 营造直播氛围 | 30-40% |
| AI 解说 TTS | 应用音频捕获 | AI 语音解说对局 | 85% |
| 礼物提示音 | 浏览器源音频 | 礼物到达提示 | 60% |

### 6.2 OBS 音频混合器配置

```yaml
音频轨道分配:
  轨道1 (主输出):  所有音频混合 → 推流输出
  轨道2:          仅游戏音效 → 备用录制
  轨道3:          仅TTS解说 → 备用录制
  轨道4:          仅背景音乐 → 备用录制
```

### 6.3 各音频源详细配置

#### 游戏音效

```yaml
来源类型:       应用音频捕获 (Application Audio Capture)
目标应用:       Chrome/Edge (游戏前端)
音量:           -6 dB
滤镜:
  - 噪声抑制: RNNoise
  - 压缩器: 阈值 -18dB, 比率 4:1
```

#### 背景音乐

```yaml
来源类型:       媒体源
文件路径:       /assets/bgm/playlist/
循环播放:       是
音量:           -12 dB
滤镜:
  - 压缩器: 阈值 -20dB, 比率 3:1 (防止音量突变)
  - 侧链压缩: 当TTS说话时自动降低BGM音量 (ducking)
```

#### AI 解说 TTS

```yaml
来源类型:       应用音频捕获
目标应用:       TTS引擎进程
音量:           -3 dB (最高优先级)
滤镜:
  - 噪声门: 关闭阈值 -40dB, 开启阈值 -30dB
  - 压缩器: 阈值 -15dB, 比率 3:1
```

### 6.4 TTS 解说方案

#### 推荐 TTS 引擎

| 引擎 | 延迟 | 音质 | 费用 | 推荐度 |
|------|------|------|------|--------|
| Edge TTS (edge-tts) | 低 | 高 | 免费 | ★★★ |
| 阿里云 TTS | 中 | 高 | 按量付费 | ★★☆ |
| 讯飞 TTS | 中 | 高 | 按量付费 | ★★☆ |
| 本地 Piper TTS | 极低 | 中 | 免费 | ★★☆ |

#### TTS 集成架构

```
游戏引擎 → 生成解说文本 → TTS引擎 → 音频流 → OBS音频捕获
                                         ↓
                                    本地音频设备
                                  (虚拟音频线缆)
```

#### 虚拟音频设备

为了将 TTS 音频独立路由到 OBS，需要虚拟音频设备：

- **Windows**: VB-Audio Virtual Cable 或 VoiceMeeter
- **macOS**: BlackHole 或 Loopback

---

## 7. OBS WebSocket 自动化控制

### 7.1 概述

OBS Studio 内置 WebSocket 服务器（v28+ 自带 obs-websocket 5.x），允许外部程序通过 WebSocket 协议远程控制 OBS 的几乎所有功能。本项目利用此能力实现游戏引擎与 OBS 的联动自动化。

### 7.2 WebSocket 服务器配置

```yaml
# OBS → 工具 → WebSocket服务器设置
启用WebSocket服务器:  是
服务器端口:           4455
启用身份验证:         是
服务器密码:           [自定义强密码]
```

### 7.3 核心控制能力

| 功能 | WebSocket 请求 | 用途 |
|------|---------------|------|
| 切换场景 | `SetCurrentProgramScene` | 游戏阶段切换 |
| 显示/隐藏源 | `SetSceneItemEnabled` | 动态显示礼物特效 |
| 开始推流 | `StartStream` | 自动开播 |
| 停止推流 | `StopStream` | 自动停播 |
| 设置源属性 | `SetInputSettings` | 更新浏览器源URL |
| 获取推流状态 | `GetStreamStatus` | 监控推流健康 |
| 截图 | `SaveSourceScreenshot` | 精彩瞬间截图 |

### 7.4 自动化控制脚本（TypeScript）

```typescript
import OBSWebSocket from 'obs-websocket-js';

class OBSController {
  private obs: OBSWebSocket;
  private connected: boolean = false;

  constructor() {
    this.obs = new OBSWebSocket();
  }

  /** 连接 OBS WebSocket 服务器 */
  async connect(url: string = 'ws://localhost:4455', password: string): Promise<void> {
    try {
      await this.obs.connect(url, password);
      this.connected = true;
      console.log('[OBS] 连接成功');

      // 监听断开事件，自动重连
      this.obs.on('ConnectionClosed', () => {
        this.connected = false;
        console.warn('[OBS] 连接断开，5秒后重连...');
        setTimeout(() => this.connect(url, password), 5000);
      });
    } catch (err) {
      console.error('[OBS] 连接失败:', err);
      throw err;
    }
  }

  /** 切换场景 */
  async switchScene(sceneName: string): Promise<void> {
    await this.obs.call('SetCurrentProgramScene', {
      sceneName
    });
    console.log(`[OBS] 切换到场景: ${sceneName}`);
  }

  /** 显示/隐藏指定源 */
  async setSourceVisible(
    sceneName: string,
    sourceName: string,
    visible: boolean
  ): Promise<void> {
    const { sceneItemId } = await this.obs.call('GetSceneItemId', {
      sceneName,
      sourceName
    });
    await this.obs.call('SetSceneItemEnabled', {
      sceneName,
      sceneItemId,
      sceneItemEnabled: visible
    });
  }

  /** 获取推流状态 */
  async getStreamStatus(): Promise<{
    active: boolean;
    duration: number;
    kbitsPerSec: number;
    droppedFrames: number;
  }> {
    const status = await this.obs.call('GetStreamStatus');
    return {
      active: status.outputActive,
      duration: status.outputDuration,
      kbitsPerSec: status.outputBytes / 125, // 近似
      droppedFrames: status.outputSkippedFrames
    };
  }

  /** 刷新浏览器源 */
  async refreshBrowserSource(sourceName: string): Promise<void> {
    await this.obs.call('PressInputPropertiesButton', {
      inputName: sourceName,
      propertyName: 'refreshnocache'
    });
  }
}

export default OBSController;
```

### 7.5 游戏引擎集成示例

```typescript
// 游戏状态变化时自动切换 OBS 场景
import OBSController from './obs-controller';

const obs = new OBSController();

// 场景名称映射
const SCENES = {
  WAITING: '开场等待',
  BIDDING: '叫地主阶段',
  PLAYING: '对局进行中',
  SETTLEMENT: '结算画面',
  BREAK: '中场休息'
};

// 监听游戏状态变化
gameEngine.on('stateChange', async (newState: string) => {
  switch (newState) {
    case 'DEALING':
      await obs.switchScene(SCENES.BIDDING);
      break;
    case 'PLAYING':
      await obs.switchScene(SCENES.PLAYING);
      break;
    case 'FINISHED':
      await obs.switchScene(SCENES.SETTLEMENT);
      // 8秒后自动切回等待
      setTimeout(() => obs.switchScene(SCENES.WAITING), 8000);
      break;
  }
});

// 监听礼物事件，触发特效源显示
giftListener.on('gift', async (gift) => {
  await obs.setSourceVisible(SCENES.PLAYING, '礼物特效层', true);
  setTimeout(async () => {
    await obs.setSourceVisible(SCENES.PLAYING, '礼物特效层', false);
  }, 3000);
});
```

---

## 8. 网络要求与稳定性保障

### 8.1 网络带宽要求

| 推流质量 | 视频码率 | 音频码率 | 最低上行带宽 | 推荐上行带宽 |
|---------|---------|---------|-------------|-------------|
| 标清 720p | 2500 Kbps | 128 Kbps | 4 Mbps | 6 Mbps |
| 高清 1080p | 4000 Kbps | 128 Kbps | 6 Mbps | 10 Mbps |
| 超清 1080p60 | 6000 Kbps | 160 Kbps | 8 Mbps | 15 Mbps |

> 推荐上行带宽为推流码率的 1.5-2 倍，预留余量应对网络波动。

### 8.2 网络质量监控

#### 关键指标

| 指标 | 正常范围 | 警告阈值 | 危险阈值 |
|------|---------|---------|---------|
| 丢帧率 | < 0.1% | 0.1% - 1% | > 1% |
| 网络延迟 (RTT) | < 50ms | 50-150ms | > 150ms |
| 码率波动 | ±5% | ±10% | ±20% |
| 编码器负载 | < 80% | 80-95% | > 95% |

#### 自动监控脚本

```typescript
// 推流健康监控 - 每10秒检查一次
async function monitorStreamHealth(obs: OBSController) {
  setInterval(async () => {
    const status = await obs.getStreamStatus();
    if (!status.active) return;

    // 丢帧率检查
    if (status.droppedFrames > 100) {
      console.warn('[监控] 丢帧过多，考虑降低码率');
      // 可触发自动降级
    }

    // 码率检查
    if (status.kbitsPerSec < 2000) {
      console.warn('[监控] 码率过低，网络可能不稳定');
    }
  }, 10000);
}
```

### 8.3 网络优化建议

1. **使用有线网络**：WiFi 不稳定，强烈建议使用网线直连
2. **QoS 设置**：路由器中为推流设备设置最高优先级
3. **关闭后台上传**：暂停云盘同步、系统更新等上传任务
4. **DNS 优化**：使用运营商 DNS 或 114.114.114.114，减少解析延迟
5. **MTU 调整**：设置为 1500（默认值），避免分片

### 8.4 推流服务器选择

抖音 RTMP 推流服务器会根据地理位置自动分配最近节点。如果遇到延迟问题：

- 使用 `ping` 或 `traceroute` 测试到推流服务器的延迟
- 联系抖音客服申请指定推流节点
- 考虑使用 SRT 协议替代 RTMP（如抖音支持）

---

## 9. 备用方案与容灾策略

### 9.1 故障场景分类

| 故障级别 | 场景 | 影响 | 恢复目标 |
|---------|------|------|---------|
| P0 - 致命 | 推流完全中断 | 直播黑屏 | 30秒内恢复 |
| P1 - 严重 | 画面卡顿/花屏 | 观看体验差 | 1分钟内恢复 |
| P2 - 一般 | 音频异常 | 无声/杂音 | 2分钟内恢复 |
| P3 - 轻微 | 覆盖层显示异常 | 信息缺失 | 下局前恢复 |

### 9.2 断流自动重连

```typescript
// 断流检测与自动重连
class StreamGuard {
  private obs: OBSController;
  private maxRetries = 5;
  private retryDelay = 3000; // 3秒

  async startMonitoring(): Promise<void> {
    setInterval(async () => {
      const status = await this.obs.getStreamStatus();
      if (!status.active) {
        console.error('[StreamGuard] 推流中断，启动重连...');
        await this.reconnect();
      }
    }, 5000);
  }

  private async reconnect(): Promise<void> {
    for (let i = 0; i < this.maxRetries; i++) {
      try {
        await this.obs.call('StartStream');
        console.log(`[StreamGuard] 第${i + 1}次重连成功`);
        return;
      } catch {
        console.warn(`[StreamGuard] 第${i + 1}次重连失败，等待重试...`);
        await this.sleep(this.retryDelay * (i + 1));
      }
    }
    console.error('[StreamGuard] 重连失败，切换备用方案');
    await this.fallbackToBackupStream();
  }

  private async fallbackToBackupStream(): Promise<void> {
    // 切换到备用推流服务器或降级模式
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 9.3 降级策略

当网络或性能出现问题时，按以下优先级逐步降级：

| 降级级别 | 操作 | 触发条件 |
|---------|------|---------|
| L1 | 关闭覆盖层特效 | 编码器负载 > 90% |
| L2 | 降低帧率 30→24fps | 丢帧率 > 0.5% |
| L3 | 降低分辨率 1080p→720p | 丢帧率 > 1% |
| L4 | 降低码率至 2000Kbps | 上行带宽不足 |
| L5 | 切换到静态画面+音频 | 严重卡顿 |

### 9.4 备用推流链路

```
主链路:  OBS → RTMP → 抖音CDN
备用链路: OBS → 本地RTMP服务器(nginx-rtmp) → 转推抖音
```

备用方案使用本地 nginx-rtmp 作为中继，好处是：
- 本地推流不受外网波动影响
- nginx-rtmp 可缓存数据，平滑网络抖动
- 支持同时录制本地备份

---

## 10. 推流参数优化建议

### 10.1 针对斗地主场景的优化

斗地主画面特点：大面积静态背景 + 局部动态（出牌动画、特效），适合以下优化：

| 参数 | 默认值 | 优化值 | 原因 |
|------|--------|--------|------|
| 关键帧间隔 | 自动 | 2秒 | 抖音要求，利于切片 |
| B帧数量 | 0 | 2 | 静态画面多，B帧压缩效率高 |
| Look-ahead | 关 | 开 | 预分析帧间差异，提升质量 |
| 码率控制 | VBR | CBR | 抖音推荐CBR，码率更稳定 |
| Profile | main | high | 支持B帧和更高压缩效率 |

### 10.2 OBS 性能优化

```yaml
# 设置 → 高级
进程优先级:         高于正常
网络:
  动态码率变化:     启用 (网络波动时自动调整)
  自动重连:         启用
  重试延迟:         2秒
  最大重试次数:     20
```

### 10.3 编码质量调优

#### NVENC 进阶参数

```
--rc cbr
--preset p5 (slow, 质量优先)
--tune hq
--multipass fullres
--rc-lookahead 32
--bframes 2
--ref 4
```

#### 画面锐化滤镜

对于斗地主的文字和牌面，适当锐化可提升清晰度：

```yaml
来源滤镜:
  - 类型: 锐化
  - 锐化程度: 0.08 (轻微锐化，避免噪点放大)
```

---

## 11. 多平台同时推流方案

### 11.1 方案概述

除抖音外，可同时推流到 B站、快手、视频号等平台，扩大覆盖面。

| 方案 | 原理 | 性能开销 | 推荐度 |
|------|------|---------|--------|
| obs-multi-rtmp 插件 | OBS 插件，多路输出 | 中（多路编码） | ★★★ |
| nginx-rtmp 转推 | 本地中继服务器分发 | 低（单次编码） | ★★☆ |
| 第三方转推服务 | 云端转推 | 无本地开销 | ★★☆ |

### 11.2 obs-multi-rtmp 插件方案

#### 安装

1. 从 GitHub 下载 obs-multi-rtmp 插件（搜索 `sorayuki/obs-multi-rtmp`）
2. 解压到 OBS 插件目录：
   - Windows: `C:\Program Files\obs-studio\obs-plugins\64bit\`
   - macOS: `/Library/Application Support/obs-studio/plugins/`
3. 重启 OBS，在「停靠窗口」中启用「多路推流」面板

#### 配置示例

```yaml
# 主推流（OBS 内置设置）
平台: 抖音
服务器: rtmp://push.douyin.com/live/
推流码: [抖音推流码]

# 副推流1（插件面板添加）
平台: B站
服务器: rtmp://live-push.bilivideo.com/live-bvc/
推流码: [B站推流码]
编码器: 跟随主推流

# 副推流2（插件面板添加）
平台: 快手
服务器: rtmp://push.kuaishou.com/live/
推流码: [快手推流码]
编码器: 跟随主推流
```

> **性能提示**：每增加一路推流，CPU/GPU 编码负载增加约 30-50%。建议不超过 3 路同时推流。

### 11.3 nginx-rtmp 转推方案（推荐）

性能更优的方案：OBS 只推一路到本地 nginx-rtmp，由 nginx 负责转推到多个平台。

#### nginx-rtmp 配置

```nginx
rtmp {
    server {
        listen 1935;
        chunk_size 4096;

        application live {
            live on;
            record off;

            # 转推到抖音
            push rtmp://push.douyin.com/live/[推流码];

            # 转推到B站
            push rtmp://live-push.bilivideo.com/live-bvc/[推流码];

            # 转推到快手
            push rtmp://push.kuaishou.com/live/[推流码];
        }
    }
}
```

#### OBS 推流设置

```yaml
服务器: rtmp://localhost:1935/live
推流码: stream
```

> 优势：OBS 只需编码一次，nginx 负责分发，CPU/GPU 负载不随平台数增加。

---

## 12. 附录

### 12.1 OBS 快捷键配置建议

| 快捷键 | 功能 | 用途 |
|--------|------|------|
| F1 | 切换到「开场等待」场景 | 手动应急切换 |
| F2 | 切换到「叫地主」场景 | 手动应急切换 |
| F3 | 切换到「对局进行中」场景 | 手动应急切换 |
| F4 | 切换到「结算画面」场景 | 手动应急切换 |
| F5 | 切换到「中场休息」场景 | 手动应急切换 |
| F9 | 开始/停止推流 | 紧急操作 |
| F10 | 开始/停止录制 | 本地备份 |

### 12.2 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 推流后抖音显示黑屏 | 编码器不兼容 | 切换到 x264 软编码 |
| 画面卡顿/掉帧 | CPU/GPU 负载过高 | 降低分辨率或帧率 |
| 推流频繁断开 | 网络不稳定 | 使用有线网络，降低码率 |
| 音画不同步 | 音频延迟 | 在音频源添加同步偏移 |
| 浏览器源白屏 | 页面加载失败 | 检查本地服务是否启动 |
| OBS WebSocket 连接失败 | 端口/密码错误 | 检查 OBS WebSocket 设置 |

### 12.3 依赖软件清单

| 软件 | 版本要求 | 用途 | 下载地址 |
|------|---------|------|---------|
| OBS Studio | 30.0+ | 推流核心 | obsproject.com |
| obs-websocket | 5.x (内置) | 自动化控制 | OBS 自带 |
| obs-multi-rtmp | 最新版 | 多平台推流 | GitHub |
| Node.js | 18+ | 控制脚本运行 | nodejs.org |
| obs-websocket-js | 5.x | WebSocket 客户端库 | npm |
| nginx + nginx-rtmp | 最新版 | 转推中继（可选） | nginx.org |
| VB-Audio / BlackHole | 最新版 | 虚拟音频设备 | 官网 |

### 12.4 参考资料

- OBS Studio 官方文档：https://obsproject.com/wiki/
- obs-websocket 协议文档：https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
- 抖音直播开放平台：https://open.douyin.com
- nginx-rtmp-module：https://github.com/arut/nginx-rtmp-module

---

> 文档结束 | AI 斗地主直播项目 · OBS 直播技术方案 v1.0
