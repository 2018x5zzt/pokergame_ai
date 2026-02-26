/* ============================================================
   AI 斗地主 - 前端主逻辑
   ============================================================ */

// 红色花色符号（后端传的 suit 值就是符号：♠♥♦♣🃏）
const RED_SUITS = new Set(['♥', '♦']);

// ============================================================
//  WebSocket 连接
// ============================================================

let ws = null;
let restartTimer = null;  // 结算倒计时 timer

function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => console.log('[WS] 已连接');
    ws.onclose = () => {
        console.log('[WS] 断开，3秒后重连...');
        setTimeout(connect, 3000);
    };
    ws.onerror = (e) => console.error('[WS] 错误', e);
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        handleMessage(msg);
    };
}

function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(obj));
    }
}

// ============================================================
//  卡牌渲染
// ============================================================

/** rank 数字 → 显示文本 */
function rankDisplay(rank) {
    const map = {
        3:'3', 4:'4', 5:'5', 6:'6', 7:'7', 8:'8', 9:'9', 10:'10',
        11:'J', 12:'Q', 13:'K', 14:'A', 15:'2', 16:'小王', 17:'大王',
    };
    return map[rank] || String(rank);
}

/** 生成一张正面牌的 HTML */
function cardHTML(card) {
    const isJokerSmall = card.rank === 16;
    const isJokerBig = card.rank === 17;

    if (isJokerSmall) {
        return `<span class="card joker-small"><span class="rank-text">小</span><span class="rank-text">王</span></span>`;
    }
    if (isJokerBig) {
        return `<span class="card joker-big"><span class="rank-text">大</span><span class="rank-text">王</span></span>`;
    }

    const isRed = RED_SUITS.has(card.suit);
    const cls = isRed ? 'card red' : 'card';
    const suit = card.suit;  // 后端已传花色符号（♠♥♦♣）
    const display = rankDisplay(card.rank);

    return `<span class="${cls}"><span class="suit">${suit}</span><span class="rank-text">${display}</span></span>`;
}

/** 生成一张背面牌的 HTML */
function cardBackHTML() {
    return `<span class="card-back"></span>`;
}

// ============================================================
//  DOM 辅助
// ============================================================

const $ = (id) => document.getElementById(id);

/** 更新玩家手牌显示（背面牌，按数量） */
function renderHandBacks(playerId, count) {
    const el = $(`hand-${playerId}`);
    el.innerHTML = Array.from({ length: count }, () => cardBackHTML()).join('');
}

/** 更新玩家手牌显示（正面牌） */
function renderHandCards(playerId, cards) {
    const el = $(`hand-${playerId}`);
    el.innerHTML = cards.map(c => cardHTML(c)).join('');
}

/** 更新手牌数量文本 */
function updateCount(playerId, count) {
    $(`count-${playerId}`).textContent = `${count}张`;
}

/** 设置角色标签 */
function setRole(playerId, role) {
    const el = $(`role-${playerId}`);
    const r = (role || '').toUpperCase();
    if (r === 'LANDLORD') {
        el.textContent = '地主';
        el.className = 'role-tag landlord';
    } else if (r === 'FARMER') {
        el.textContent = '农民';
        el.className = 'role-tag farmer';
    } else {
        el.textContent = '';
        el.className = 'role-tag';
    }
}

/** 设置玩家出牌动作区内容 */
function setAction(playerId, html, animClass) {
    const el = $(`action-${playerId}`);
    el.innerHTML = html;
    if (animClass) {
        el.classList.remove('anim-fade', 'anim-bomb', 'anim-pop', 'anim-pass', 'anim-fly-in');
        void el.offsetWidth; // 触发 reflow 重置动画
        el.classList.add(animClass);
    }
}

/** 清空所有玩家的动作区 */
function clearAllActions() {
    for (let i = 0; i < 3; i++) {
        $(`action-${i}`).innerHTML = '';
    }
}

/** 高亮当前出牌玩家 */
function highlightSeat(playerId) {
    document.querySelectorAll('.seat').forEach(s => s.classList.remove('active'));
    if (playerId !== null && playerId !== undefined) {
        $(`seat-${playerId}`).classList.add('active');
    }
}

// ============================================================
//  发牌飞入动画
// ============================================================

/** 获取手牌区的屏幕中心坐标（飞入目标点） */
function getHandTarget(playerId) {
    const el = $(`hand-${playerId}`);
    const rect = el.getBoundingClientRect();
    return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
    };
}

/** 创建一张飞行中的背面牌，从屏幕中央飞向目标玩家手牌区 */
function flyCardToHand(playerId) {
    const table = document.querySelector('.table');
    const app = document.getElementById('app');
    const isVertical = app.classList.contains('vertical');
    const card = document.createElement('span');
    card.className = 'flying-card';
    card.innerHTML = '<span class="card-back" style="width:40px;height:58px;margin:0"></span>';
    table.appendChild(card);

    // 起点：牌桌中央（根据布局模式）
    const startX = isVertical ? 540 : 960;
    const startY = isVertical ? 934 : 512;
    card.style.left = startX + 'px';
    card.style.top = startY + 'px';
    card.style.transform = 'translate(-50%, -50%) scale(0.8)';
    card.style.opacity = '1';

    // 计算目标位置
    const target = getHandTarget(playerId);
    // 目标坐标相对于 .table（横屏 top-bar=56px，竖屏=52px）
    const topBarH = isVertical ? 52 : 56;
    const endX = target.x;
    const endY = target.y - topBarH;

    // 触发 reflow 后设置终点
    void card.offsetWidth;
    card.style.transform = `translate(${endX - startX - 20}px, ${endY - startY}px) scale(1)`;
    card.style.opacity = '0.3';

    // 动画结束后移除
    setTimeout(() => {
        if (card.parentNode) card.parentNode.removeChild(card);
    }, 380);
}

// ============================================================
//  底牌翻转动画
// ============================================================

/** 炸弹/火箭全屏特效：闪光 + 屏幕震动 */
function triggerBombEffect(isRocket) {
    // 全屏闪光层
    const flash = document.createElement('div');
    flash.className = isRocket ? 'rocket-flash' : 'bomb-flash';
    document.body.appendChild(flash);
    setTimeout(() => flash.remove(), isRocket ? 850 : 650);

    // 屏幕震动（应用到 .table 避免与 fitScale 的 transform 冲突）
    const table = document.querySelector('.table');
    table.classList.remove('screen-shake');
    void table.offsetWidth;
    table.classList.add('screen-shake');
    setTimeout(() => table.classList.remove('screen-shake'), 550);
}

/** 生成底牌翻转卡片 HTML（初始显示背面） */
function dizhuFlipCardHTML(card) {
    return `<div class="dizhu-flip-card">` +
        `<div class="flip-back"><span class="card-back" style="width:42px;height:60px;margin:0"></span></div>` +
        `<div class="flip-front">${cardHTML(card)}</div>` +
        `</div>`;
}

/** 执行底牌翻转动画（依次翻转3张） */
async function flipDizhuCards(cards) {
    const container = $('dizhu-cards-list');
    // 先放置背面牌
    container.innerHTML = cards.map(c => dizhuFlipCardHTML(c)).join('');

    // 依次翻转
    const flipCards = container.querySelectorAll('.dizhu-flip-card');
    for (let i = 0; i < flipCards.length; i++) {
        await sleep(200);
        flipCards[i].classList.add('flipped');
    }
}

// ============================================================
//  消息分发
// ============================================================

function handleMessage(msg) {
    switch (msg.type) {
        case 'deal':       onDeal(msg);      break;
        case 'deal_start': onDealStart(msg); break;
        case 'deal_card':  onDealCard(msg);  break;
        case 'deal_done':  onDealDone(msg);  break;
        case 'thinking':   onThinking(msg);  break;
        case 'countdown':  onCountdown(msg); break;
        case 'bid':        onBid(msg);       break;
        case 'landlord':   onLandlord(msg);  break;
        case 'play':       onPlay(msg);      break;
        case 'pass':       onPass(msg);      break;
        case 'result':     onResult(msg);    break;
    }
}

// ============================================================
//  事件处理器
// ============================================================

// 逐张发牌状态
const dealState = { hands: [[], [], []], dizhuCards: [] };

/** 发牌开始：初始化界面 */
function onDealStart(msg) {
    clearRestartCountdown();  // 清除结算倒计时，防止 timer 叠加
    $('phase-text').textContent = '发牌中';
    $('multiplier-text').textContent = '';
    $('result-modal').style.display = 'none';
    clearAllActions();
    $('dizhu-cards-list').innerHTML = '';
    dealState.hands = [[], [], []];
    dealState.dizhuCards = [];

    msg.players.forEach(p => {
        $(`name-${p.id}`).textContent = p.name;
        setRole(p.id, '');
        $(`hand-${p.id}`).innerHTML = '';
        updateCount(p.id, 0);
    });
}

/** 逐张发牌：收到一张牌（带飞入动画） */
function onDealCard(msg) {
    const pid = msg.player_id;
    dealState.hands[pid].push(msg.card);

    // 触发飞入动画
    flyCardToHand(pid);

    // 同时更新手牌显示
    renderHandCards(pid, dealState.hands[pid]);
    updateCount(pid, dealState.hands[pid].length);
}

/** 发牌完成：显示完整手牌，底牌显示背面 */
function onDealDone(msg) {
    $('phase-text').textContent = '叫地主阶段';
    msg.players.forEach(p => {
        if (p.hand && p.hand.length > 0) {
            renderHandCards(p.id, p.hand);
        }
        updateCount(p.id, p.hand_size);
    });
    // 底牌先显示背面（等地主确定时翻转）
    if (msg.dizhu_cards) {
        dealState.dizhuCards = msg.dizhu_cards;
        $('dizhu-cards-list').innerHTML = msg.dizhu_cards.map(() =>
            `<span class="card-back" style="width:42px;height:60px;margin:0"></span>`
        ).join('');
    }
}

/** AI 开始思考：显示倒计时 */
function onThinking(msg) {
    const pid = msg.player_id;
    highlightSeat(pid);
    const phaseText = msg.phase === 'bid' ? '思考叫分中' : '思考出牌中';
    setAction(pid,
        `<div class="thinking-indicator">` +
        `<span class="thinking-dots">${phaseText}</span>` +
        `<span class="countdown-num" id="cd-${pid}">${msg.remaining}</span>` +
        `</div>`,
        'anim-fade'
    );
}

/** 倒计时更新 */
function onCountdown(msg) {
    const el = $(`cd-${msg.player_id}`);
    if (el) {
        el.textContent = msg.remaining;
        // 最后1秒闪烁
        if (msg.remaining <= 1) {
            el.classList.add('countdown-urgent');
        }
    }
}

/** 发牌（旧版兼容：带动画逐张发牌） */
async function onDeal(msg) {
    $('phase-text').textContent = '发牌中';
    $('multiplier-text').textContent = '';
    $('result-modal').style.display = 'none';
    clearAllActions();
    $('dizhu-cards-list').innerHTML = '';

    // 初始化玩家名称和空手牌
    msg.players.forEach(p => {
        $(`name-${p.id}`).textContent = p.name;
        setRole(p.id, '');
        $(`hand-${p.id}`).innerHTML = '';
        updateCount(p.id, 0);
    });

    // 逐张发牌动画：每人17张，轮流发
    const hands = [[], [], []];
    const allCards = msg.players.map(p => p.hand || []);

    // 如果后端传了完整手牌数据，做逐张发牌动画
    if (allCards[0] && allCards[0].length > 0) {
        const maxLen = Math.max(...allCards.map(h => h.length));
        for (let i = 0; i < maxLen; i++) {
            for (let pid = 0; pid < 3; pid++) {
                if (i < allCards[pid].length) {
                    hands[pid].push(allCards[pid][i]);
                    renderHandCards(pid, hands[pid]);
                    updateCount(pid, hands[pid].length);
                }
            }
            // 每轮3张发完后短暂停顿
            await sleep(60);
        }
    } else {
        // 后端未传手牌数据时，降级为背面牌
        msg.players.forEach(p => {
            renderHandBacks(p.id, p.hand_size);
            updateCount(p.id, p.hand_size);
        });
    }
}

/** 异步等待工具函数 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
//  结算倒计时（自动再来一局）
// ============================================================

/** 启动结算倒计时，countdown 秒后自动开始下一局 */
function startRestartCountdown(seconds) {
    clearRestartCountdown();
    let remaining = seconds;
    const btn = $('btn-restart');
    btn.textContent = `再来一局 (${remaining}s)`;

    restartTimer = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearRestartCountdown();
            $('result-modal').style.display = 'none';
            send({ action: 'start' });
        } else {
            btn.textContent = `再来一局 (${remaining}s)`;
        }
    }, 1000);
}

/** 清除结算倒计时 */
function clearRestartCountdown() {
    if (restartTimer !== null) {
        clearInterval(restartTimer);
        restartTimer = null;
    }
    const btn = $('btn-restart');
    if (btn) btn.textContent = '再来一局';
}

/** 叫地主 */
function onBid(msg) {
    $('phase-text').textContent = '叫地主阶段';
    highlightSeat(msg.player_id);
    const bidText = msg.bid > 0 ? `叫 ${msg.bid} 分` : '不叫';
    const strategy = msg.strategy ? `<div class="strategy-text">${msg.strategy}</div>` : '';
    setAction(msg.player_id,
        `<span class="action-text">${bidText}</span>${strategy}`,
        'anim-fade'
    );
}

/** 地主确定（带底牌翻转动画） */
async function onLandlord(msg) {
    $('phase-text').textContent = '出牌阶段';
    $('multiplier-text').textContent = `倍数: ${msg.highest_bid}`;
    clearAllActions();
    highlightSeat(null);

    // 设置角色标签 + 更新手牌（正面显示）
    msg.players.forEach(p => {
        setRole(p.id, p.role);
        if (p.hand && p.hand.length > 0) {
            renderHandCards(p.id, p.hand);
        } else {
            renderHandBacks(p.id, p.hand_size);
        }
        updateCount(p.id, p.hand_size);
    });

    // 底牌翻转动画
    await flipDizhuCards(msg.dizhu_cards);
}

/** 出牌 */
function onPlay(msg) {
    highlightSeat(msg.player_id);
    updateCount(msg.player_id, msg.hand_size);

    // 用正面牌显示剩余手牌（观众视角）
    if (msg.hand && msg.hand.length > 0) {
        renderHandCards(msg.player_id, msg.hand);
    } else {
        renderHandBacks(msg.player_id, msg.hand_size);
    }

    // 构建出牌卡片 HTML
    const cardsHtml = msg.cards.map(c => cardHTML(c)).join('');
    const label = msg.hand_type ? `<div class="hand-type-label">${msg.hand_type}</div>` : '';
    const strategy = msg.strategy ? `<div class="strategy-text">${msg.strategy}</div>` : '';

    // 根据牌型选择动画
    if (msg.is_bomb) {
        triggerBombEffect(msg.hand_type === '火箭');
        setAction(msg.player_id, label + cardsHtml + strategy, 'anim-bomb');
    } else {
        setAction(msg.player_id, label + cardsHtml + strategy, 'anim-fly-in');
    }

    // 炸弹时更新倍数显示
    if (msg.is_bomb) {
        const cur = $('multiplier-text').textContent;
        const m = parseInt(cur.replace(/\D/g, '')) || 1;
        $('multiplier-text').textContent = `倍数: ${m * 2}`;
    }
}

/** 不出 */
function onPass(msg) {
    highlightSeat(msg.player_id);
    const strategy = msg.strategy ? `<div class="strategy-text">${msg.strategy}</div>` : '';
    setAction(msg.player_id,
        `<span class="action-text">不出</span>${strategy}`,
        'anim-pass'
    );
}

/** 结算 */
function onResult(msg) {
    $('phase-text').textContent = '对局结束';
    highlightSeat(null);

    // 标题
    const emoji = msg.winner_is_landlord ? '👑' : '🌾';
    const roleText = msg.winner_is_landlord ? '地主' : '农民';
    $('result-title').textContent = `${emoji} ${msg.winner_name} (${roleText}) 获胜！`;

    // 详情
    const details = [];
    if (msg.is_spring) details.push('🌸 春天！');
    if (msg.is_anti_spring) details.push('🔄 反春！');
    if (msg.bomb_count > 0) details.push(`💣 炸弹 ×${msg.bomb_count}`);
    details.push(`倍数: ${msg.multiplier}`);
    $('result-detail').textContent = details.join('  ');

    // 积分表格
    const table = $('result-table');
    let html = '<tr><th>玩家</th><th>角色</th><th>积分</th></tr>';
    msg.scores.forEach(s => {
        const r = s.role.toUpperCase() === 'LANDLORD' ? '地主' : '农民';
        const color = s.score > 0 ? '#4caf50' : '#e74c3c';
        html += `<tr><td>${s.name}</td><td>${r}</td><td style="color:${color}">${s.score > 0 ? '+' : ''}${s.score}</td></tr>`;
    });
    table.innerHTML = html;

    // 显示弹窗
    $('result-modal').style.display = 'flex';

    // 自动倒计时 10 秒后开始下一局
    startRestartCountdown(10);
}

// ============================================================
//  自适应缩放（1920×1080 设计稿 → 任意窗口）
// ============================================================

function fitScale() {
    const app = document.getElementById('app');
    const isVertical = app.classList.contains('vertical');
    const designW = isVertical ? 1080 : 1920;
    const designH = isVertical ? 1920 : 1080;
    const scaleX = window.innerWidth / designW;
    const scaleY = window.innerHeight / designH;
    const scale = Math.min(scaleX, scaleY);
    const offsetX = (window.innerWidth - designW * scale) / 2;
    const offsetY = (window.innerHeight - designH * scale) / 2;
    app.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
}

// ============================================================
//  初始化
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    fitScale();
    window.addEventListener('resize', fitScale);
    connect();

    // 开始按钮
    $('btn-start').addEventListener('click', () => {
        $('start-overlay').style.display = 'none';
        send({ action: 'start' });
    });

    // 再来一局（手动点击跳过倒计时）
    $('btn-restart').addEventListener('click', () => {
        clearRestartCountdown();
        $('result-modal').style.display = 'none';
        send({ action: 'start' });
    });

    // 横屏/竖屏切换
    $('btn-layout').addEventListener('click', () => {
        const app = document.getElementById('app');
        const btn = $('btn-layout');
        app.classList.toggle('vertical');
        const isVertical = app.classList.contains('vertical');
        btn.textContent = isVertical ? '🖥️ 横屏' : '📱 竖屏';
        fitScale();
    });
});
