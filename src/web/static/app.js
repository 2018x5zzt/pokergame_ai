/* ============================================================
   AI 斗地主 - 前端主逻辑
   ============================================================ */

// 红色花色符号（后端传的 suit 值就是符号：♠♥♦♣🃏）
const RED_SUITS = new Set(['♥', '♦']);

// ============================================================
//  WebSocket 连接
// ============================================================

let ws = null;

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
        el.classList.remove('anim-fade', 'anim-bomb', 'anim-pop');
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
//  消息分发
// ============================================================

function handleMessage(msg) {
    switch (msg.type) {
        case 'deal':       onDeal(msg);      break;
        case 'deal_start': onDealStart(msg); break;
        case 'deal_card':  onDealCard(msg);  break;
        case 'deal_done':  onDealDone(msg);  break;
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
const dealState = { hands: [[], [], []] };

/** 发牌开始：初始化界面 */
function onDealStart(msg) {
    $('phase-text').textContent = '发牌中';
    $('multiplier-text').textContent = '';
    $('result-modal').style.display = 'none';
    clearAllActions();
    $('dizhu-cards-list').innerHTML = '';
    dealState.hands = [[], [], []];

    msg.players.forEach(p => {
        $(`name-${p.id}`).textContent = p.name;
        setRole(p.id, '');
        $(`hand-${p.id}`).innerHTML = '';
        updateCount(p.id, 0);
    });
}

/** 逐张发牌：收到一张牌 */
function onDealCard(msg) {
    const pid = msg.player_id;
    dealState.hands[pid].push(msg.card);
    renderHandCards(pid, dealState.hands[pid]);
    updateCount(pid, dealState.hands[pid].length);
}

/** 发牌完成：显示完整手牌 */
function onDealDone(msg) {
    $('phase-text').textContent = '叫地主阶段';
    msg.players.forEach(p => {
        if (p.hand && p.hand.length > 0) {
            renderHandCards(p.id, p.hand);
        }
        updateCount(p.id, p.hand_size);
    });
    // 显示底牌
    if (msg.dizhu_cards) {
        $('dizhu-cards-list').innerHTML = msg.dizhu_cards.map(c => cardHTML(c)).join('');
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

/** 叫地主 */
function onBid(msg) {
    $('phase-text').textContent = '叫地主阶段';
    highlightSeat(msg.player_id);
    const bidText = msg.bid > 0 ? `叫 ${msg.bid} 分` : '不叫';
    setAction(msg.player_id,
        `<span class="action-text">${bidText}</span>`,
        'anim-fade'
    );
}

/** 地主确定 */
function onLandlord(msg) {
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

    // 显示底牌
    $('dizhu-cards-list').innerHTML = msg.dizhu_cards.map(c => cardHTML(c)).join('');
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
    const label = msg.hand_type ? `<div style="font-size:12px;color:#aaa;margin-bottom:4px">${msg.hand_type}</div>` : '';
    const strategy = msg.strategy ? `<div class="strategy-text">${msg.strategy}</div>` : '';
    const anim = msg.is_bomb ? 'anim-bomb' : 'anim-fade';

    setAction(msg.player_id, label + cardsHtml + strategy, anim);

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
        'anim-fade'
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
}

// ============================================================
//  初始化
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    connect();

    // 开始按钮
    $('btn-start').addEventListener('click', () => {
        $('start-overlay').style.display = 'none';
        send({ action: 'start' });
    });

    // 再来一局
    $('btn-restart').addEventListener('click', () => {
        $('result-modal').style.display = 'none';
        send({ action: 'start' });
    });
});
