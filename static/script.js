// Vocaloid Song Guessing Game - Frontend

// ===== STATE =====
const state = {
    // Single player
    difficulty: 'ja_legend',
    maxGuesses: 8,
    guessesUsed: 0,
    gameStatus: 'idle',
    guesses: [],
    guessedSongIds: new Set(),
    targetSong: null,
    selectedSuggestionIndex: -1,
    
    // Multiplayer
    mp: {
        roomCode: null,
        playerId: null,
        ws: null,
        matchFormat: 3,
        difficulty: 'all_legend',
        totalRounds: 3,
        currentRound: 0,
        roundStatus: 'waiting',
        matchStatus: 'waiting',
        scores: {},
        players: {},
        timerRemaining: 0,
        timerInterval: null,
        roundGuesses: [],
        guessedMpSongIds: new Set(),
        mpSelectedIndex: -1,
    },
};

// ===== DOM ELEMENTS =====
// Single player
const searchInput = document.getElementById('searchInput');
const suggestions = document.getElementById('suggestions');
const guessesBody = document.getElementById('guessesBody');
const guessesContainer = document.getElementById('guessesContainer');
const emptyState = document.getElementById('emptyState');
const guessCount = document.getElementById('guessCount');
const gameStatus = document.getElementById('gameStatus');
const resultModal = document.getElementById('resultModal');
const modalIcon = document.getElementById('modalIcon');
const modalTitle = document.getElementById('modalTitle');
const modalDetails = document.getElementById('modalDetails');
const btnNewGame = document.getElementById('btnNewGame');
const btnHint = document.getElementById('btnHint');
const btnModalNewGame = document.getElementById('btnModalNewGame');
const diffBtns = document.querySelectorAll('#panel-single .diff-btn');

// Tabs
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanels = document.querySelectorAll('.tab-panel');

// Multiplayer
const mpLobby = document.getElementById('mpLobby');
const mpRoom = document.getElementById('mpRoom');
const mpSearchInput = document.getElementById('mpSearchInput');
const mpSuggestions = document.getElementById('mpSuggestions');
const mpGuessesBody = document.getElementById('mpGuessesBody');
const mpGuessesContainer = document.getElementById('mpGuessesContainer');
const mpGuessCount = document.getElementById('mpGuessCount');
const mpTimer = document.getElementById('mpTimer');
const mpNotification = document.getElementById('mpNotification');
const mpFormatLabel = document.getElementById('mpFormatLabel');
const mpRoomCode = document.getElementById('mpRoomCode');
const cardSelf = document.getElementById('cardSelf');
const cardOpponent = document.getElementById('cardOpponent');
const scoreSelf = document.getElementById('scoreSelf');
const scoreOpp = document.getElementById('scoreOpp');
const statusSelf = document.getElementById('statusSelf');
const statusOpp = document.getElementById('statusOpp');
const btnCreateRoom = document.getElementById('btnCreateRoom');
const btnJoinRoom = document.getElementById('btnJoinRoom');
const btnCopyRoom = document.getElementById('btnCopyRoom');
const btnLeaveRoom = document.getElementById('btnLeaveRoom');
const btnReady = document.getElementById('btnReady');
const btnStartMatch = document.getElementById('btnStartMatch');
const btnSurrender = document.getElementById('btnSurrender');
const btnNextRound = document.getElementById('btnNextRound');
const hostTools = document.getElementById('hostTools');
const hostDifficulty = document.getElementById('hostDifficulty');
const btnApplyDifficulty = document.getElementById('btnApplyDifficulty');
const roomCodeInput = document.getElementById('roomCodeInput');
const formatBtns = document.querySelectorAll('.format-btn');
const toastContainer = document.getElementById('toastContainer');

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupSinglePlayer();
    setupMultiplayer();
    restoreGame();
});

// ===== TABS =====
function setupTabs() {
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const tab = btn.dataset.tab;
            tabPanels.forEach(p => p.classList.remove('active'));
            document.getElementById('panel-' + tab).classList.add('active');
        });
    });
}

// ===== TOAST =====
function showToast(msg, type = '') {
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = msg;
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== SINGLE PLAYER =====
function setupSinglePlayer() {
    searchInput.addEventListener('input', debounce(handleSearch, 200));
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim().length >= 1) handleSearch();
    });
    
    searchInput.addEventListener('keydown', (e) => {
        const items = suggestions.querySelectorAll('.suggestion-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            state.selectedSuggestionIndex = Math.min(state.selectedSuggestionIndex + 1, items.length - 1);
            updateSuggestionHighlight(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            state.selectedSuggestionIndex = Math.max(state.selectedSuggestionIndex - 1, -1);
            updateSuggestionHighlight(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (state.selectedSuggestionIndex >= 0 && items.length > 0) {
                const selected = items[state.selectedSuggestionIndex];
                if (selected) {
                    const songId = parseInt(selected.dataset.id);
                    if (songId) selectSong(songId);
                }
            }
        } else if (e.key === 'Escape') {
            suggestions.classList.remove('show');
            state.selectedSuggestionIndex = -1;
        }
    });
    
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-wrapper')) {
            suggestions.classList.remove('show');
            state.selectedSuggestionIndex = -1;
        }
    });
    
    diffBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            diffBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.difficulty = btn.dataset.difficulty;
            startNewGame();
        });
    });
    
    btnNewGame.addEventListener('click', startNewGame);
    btnModalNewGame.addEventListener('click', () => {
        resultModal.classList.remove('show');
        startNewGame();
    });
    btnHint.addEventListener('click', getHint);
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            suggestions.classList.remove('show');
            resultModal.classList.remove('show');
            state.selectedSuggestionIndex = -1;
        }
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            startNewGame();
        }
    });
}

function updateSuggestionHighlight(items) {
    items.forEach((item, i) => {
        item.classList.toggle('highlighted', i === state.selectedSuggestionIndex);
    });
}

async function apiCall(url) {
    const resp = await fetch(url);
    if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Request failed');
    }
    return await resp.json();
}

async function handleSearch() {
    const q = searchInput.value.trim();
    if (q.length < 1) { suggestions.classList.remove('show'); return; }
    try {
        const results = await apiCall('/api/search?q=' + encodeURIComponent(q));
        renderSuggestions(results, suggestions);
    } catch (err) {
        suggestions.innerHTML = '<div class="suggestion-item" style="color: var(--gray)">搜索失败，请重试</div>';
        suggestions.classList.add('show');
    }
}

function renderSuggestions(results, container) {
    if (!results || results.length === 0) {
        container.innerHTML = '<div class="suggestion-item" style="color: var(--gray)">没有找到匹配的歌曲</div>';
        container.classList.add('show');
        return;
    }
    container.innerHTML = results.map(song => `
        <div class="suggestion-item" data-id="${song.id}" onclick="selectSong(${song.id})">
            <div>
                <div class="song-title">${escapeHtml(song.title)} ${song.title_jp ? '/ ' + escapeHtml(song.title_jp) : ''}</div>
                <div class="song-meta">${song.title_cn ? escapeHtml(song.title_cn) + ' · ' : ''}${escapeHtml(song.release_year)}</div>
            </div>
            <div class="song-meta">
                <span class="song-producer">${escapeHtml(song.producer)}</span> feat. ${escapeHtml(song.vocaloid)}
            </div>
        </div>
    `).join('');
    container.classList.add('show');
}

async function selectSong(songId) {
    if (state.gameStatus !== 'playing') {
        await startNewGame();
        if (state.gameStatus !== 'playing') return;
    }
    if (state.guessedSongIds.has(songId)) {
        showToast('这首歌已经猜过了！', 'error');
        searchInput.value = '';
        suggestions.classList.remove('show');
        state.selectedSuggestionIndex = -1;
        return;
    }
    searchInput.value = '';
    suggestions.classList.remove('show');
    state.selectedSuggestionIndex = -1;
    try {
        const result = await apiCall('/api/guess?song_id=' + songId);
        state.guessedSongIds.add(songId);
        handleGuessResult(result);
    } catch (err) {
        showToast('猜测失败: ' + err.message, 'error');
    }
}

function handleGuessResult(result) {
    state.guessesUsed = result.guesses_used;
    state.gameStatus = result.status;
    state.maxGuesses = result.max_guesses;
    addGuessRow(result, guessesBody, guessesContainer, emptyState);
    updateGameInfo();
    if (result.status === 'won') {
        const stats = updateStats(true);
        showResultModal(true, result, stats);
    } else if (result.status === 'lost') {
        const stats = updateStats(false);
        showResultModal(false, result, stats);
    }
    saveGameState();
}

function addGuessRow(result, body, container, empty) {
    if (container) container.style.display = '';
    if (empty) empty.style.display = 'none';
    const row = document.createElement('tr');
    row.innerHTML = '<td>' + result.guesses_used + '</td>';
    const songTitle = result.guess_song.title_cn
        ? result.guess_song.title + ' / ' + result.guess_song.title_cn
        : result.guess_song.title + ' / ' + result.guess_song.title_jp;
    row.innerHTML += '<td><strong>' + escapeHtml(songTitle) + '</strong></td>';
    result.attributes.forEach(attr => {
        let cls = 'attr-cell ';
        if (attr.color === 'green') cls += 'attr-green';
        else if (attr.color === 'yellow') cls += 'attr-yellow';
        else cls += 'attr-gray';
        if (attr.arrow === 'up') cls += ' arrow-up';
        else if (attr.arrow === 'down') cls += ' arrow-down';
        let extra = '';
        if (attr.name === '级别' && attr.views !== undefined) {
            const vw = formatViews(attr.views);
            extra = '<div class="views-sub">' + (vw ? vw : '—') + '</div>';
        }
        row.innerHTML += '<td><span class="' + cls + '">' + escapeHtml(attr.value) + extra + '</span></td>';
    });
    body.insertBefore(row, body.firstChild);
    state.guesses.unshift(result);
}

function updateGameInfo() {
    if (state.gameStatus === 'idle') {
        guessCount.textContent = '请先开始新游戏';
        gameStatus.textContent = '';
        return;
    }
    guessCount.textContent = '已猜: ' + state.guessesUsed + ' / ' + state.maxGuesses;
    if (state.gameStatus === 'playing') {
        gameStatus.textContent = '剩余 ' + (state.maxGuesses - state.guessesUsed) + ' 次机会';
        gameStatus.style.color = 'var(--accent)';
    } else if (state.gameStatus === 'won') {
        gameStatus.textContent = '猜对了！';
        gameStatus.style.color = 'var(--green)';
    } else if (state.gameStatus === 'lost') {
        gameStatus.textContent = '机会用完了';
        gameStatus.style.color = 'var(--red)';
    }
}

function showResultModal(won, result, stats) {
    if (won) {
        modalIcon.textContent = 'WIN';
        modalTitle.textContent = '恭喜你猜对了！(用' + result.guesses_used + '次)';
        modalTitle.style.color = 'var(--green)';
    } else {
        modalIcon.textContent = 'LOSE';
        modalTitle.textContent = '很遗憾，机会用完了';
        modalTitle.style.color = 'var(--red)';
    }
    const target = result.target_song;
    const min = Math.floor(target.length_sec / 60);
    const sec = target.length_sec % 60;
    let statsHtml = '';
    if (stats) {
        statsHtml = '<div class="stats-bar">' +
            '<span>总场次: ' + stats.played + '</span>' +
            '<span>胜率: ' + Math.round(stats.won / stats.played * 100) + '%</span>' +
            '<span>当前连胜: ' + stats.streak + '</span>' +
            '<span>最佳连胜: ' + stats.bestStreak + '</span>' +
            '</div>';
    }
    modalDetails.innerHTML = '<p>目标歌曲是：<strong>' + escapeHtml(target.title) + ' / ' + escapeHtml(target.title_jp) + '</strong></p>' +
        (target.title_cn ? '<p>中文名：' + escapeHtml(target.title_cn) + '</p>' : '') +
        '<div class="target-info">' +
        '<span class="tag">' + escapeHtml(target.producer) + '</span>' +
        '<span class="tag">' + escapeHtml(target.vocaloid) + '</span>' +
        '<span class="tag">' + target.release_year + '</span>' +
        '<span class="tag">' + escapeHtml(target.language) + '</span>' +
        '<span class="tag">⏱ BPM ' + target.bpm + '</span>' +
        '<span class="tag">' + escapeHtml(target.genre) + '</span>' +
        '<span class="tag">⏱ ' + min + ':' + String(sec).padStart(2, '0') + '</span>' +
        '</div>' + statsHtml;
    resultModal.classList.add('show');
}

async function startNewGame() {
    state.guesses = [];
    state.guessesUsed = 0;
    state.gameStatus = 'idle';
    state.targetSong = null;
    state.guessedSongIds = new Set();
    guessesBody.innerHTML = '';
    if (emptyState) emptyState.style.display = '';
    if (guessesContainer) guessesContainer.style.display = 'none';
    try {
        const result = await apiCall('/api/new_game?difficulty=' + state.difficulty);
        state.gameStatus = 'playing';
        state.maxGuesses = result.max_guesses;
        state.guessesUsed = 0;
        updateGameInfo();
        searchInput.value = '';
        searchInput.focus();
        saveGameState();
    } catch (err) {
        showToast('开始游戏失败: ' + err.message, 'error');
    }
}

async function restoreGame() {
    try {
        const result = await apiCall('/api/game_state');
        if (result.status === 'playing' || result.status === 'won' || result.status === 'lost') {
            state.gameStatus = result.status;
            state.maxGuesses = result.max_guesses;
            state.guessesUsed = result.guesses_used;
            state.difficulty = result.difficulty;
            diffBtns.forEach(b => {
                b.classList.toggle('active', b.dataset.difficulty === result.difficulty);
            });
            if (result.guesses && result.guesses.length > 0) {
                result.guesses.forEach(g => {
                    state.guessedSongIds.add(g.song_id);
                    addGuessRow({
                        guesses_used: g.guess_number,
                        is_correct: g.is_correct || false,
                        guess_song: g.guess_song,
                        attributes: g.attributes,
                    }, guessesBody, guessesContainer, emptyState);
                });
            }
            updateGameInfo();
            searchInput.focus();
        }
    } catch (err) {
        state.gameStatus = 'idle';
        updateGameInfo();
    }
}

function saveGameState() {
    localStorage.setItem('vc_game_difficulty', state.difficulty);
}

function updateStats(won) {
    const stats = JSON.parse(localStorage.getItem('vc_stats') || '{"played":0,"won":0,"streak":0,"bestStreak":0}');
    stats.played++;
    if (won) { stats.won++; stats.streak++; if (stats.streak > stats.bestStreak) stats.bestStreak = stats.streak; }
    else { stats.streak = 0; }
    localStorage.setItem('vc_stats', JSON.stringify(stats));
    return stats;
}

async function getHint() {
    if (state.gameStatus !== 'playing') { showToast('请先开始新游戏', 'error'); return; }
    try {
        const hint = await apiCall('/api/hint');
        showToast('' + hint.name + ' = ' + hint.value, 'success');
    } catch (err) {
        showToast('获取提示失败', 'error');
    }
}

// ===== MULTIPLAYER =====
function setupMultiplayer() {
    // Format selector (BO1/3/5/7)
    formatBtns.forEach(btn => {
        if (!btn.dataset.format) return;
        btn.addEventListener('click', () => {
            formatBtns.forEach(b => { if (b.dataset.format) b.classList.remove('active'); });
            btn.classList.add('active');
            state.mp.matchFormat = parseInt(btn.dataset.format);
        });
    });
    
    // Difficulty selector (multiplayer)
    document.querySelectorAll('[data-mp-diff]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('[data-mp-diff]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.mp.difficulty = btn.dataset.mpDiff;
        });
    });
    
    // Create room
    btnCreateRoom.addEventListener('click', createRoom);
    
    // Join room
    btnJoinRoom.addEventListener('click', joinRoom);
    roomCodeInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') joinRoom();
    });
    
    // Leave room
    btnLeaveRoom.addEventListener('click', leaveRoom);
    
    // Copy room code
    btnCopyRoom.addEventListener('click', () => {
        navigator.clipboard.writeText(state.mp.roomCode).then(() => {
            showToast('房间码已复制', 'success');
        });
    });
    
    // Ready
    btnReady.addEventListener('click', () => {
        if (state.mp.ws && state.mp.ws.readyState === WebSocket.OPEN) {
            state.mp.ws.send(JSON.stringify({ type: 'ready' }));
            btnReady.disabled = true;
            btnReady.textContent = '已准备';
        }
    });
    
    // Host starts match
    btnStartMatch.addEventListener('click', () => {
        if (state.mp.ws && state.mp.ws.readyState === WebSocket.OPEN) {
            state.mp.ws.send(JSON.stringify({ type: 'start_match' }));
        }
    });
    
    // Surrender
    btnSurrender.addEventListener('click', () => {
        if (state.mp.ws && state.mp.ws.readyState === WebSocket.OPEN) {
            state.mp.ws.send(JSON.stringify({ type: 'surrender' }));
        }
    });
    
    // Next round (host in lobby)
    btnNextRound.addEventListener('click', () => {
        if (state.mp.ws && state.mp.ws.readyState === WebSocket.OPEN) {
            state.mp.ws.send(JSON.stringify({ type: 'next_round' }));
        }
    });
    
    // Host apply difficulty
    btnApplyDifficulty.addEventListener('click', () => {
        if (state.mp.ws && state.mp.ws.readyState === WebSocket.OPEN) {
            state.mp.ws.send(JSON.stringify({ type: 'change_difficulty', difficulty: hostDifficulty.value }));
        }
    });
    
    // MP Search
    mpSearchInput.addEventListener('input', debounce(handleMpSearch, 200));
    mpSearchInput.addEventListener('keydown', (e) => {
        const items = mpSuggestions.querySelectorAll('.suggestion-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            state.mp.mpSelectedIndex = Math.min(state.mp.mpSelectedIndex + 1, items.length - 1);
            updateSuggestionHighlightMp(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            state.mp.mpSelectedIndex = Math.max(state.mp.mpSelectedIndex - 1, -1);
            updateSuggestionHighlightMp(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (state.mp.mpSelectedIndex >= 0 && items.length > 0) {
                const selected = items[state.mp.mpSelectedIndex];
                if (selected) {
                    const songId = parseInt(selected.dataset.id);
                    if (songId) mpSelectSong(songId);
                }
            }
        } else if (e.key === 'Escape') {
            mpSuggestions.classList.remove('show');
            state.mp.mpSelectedIndex = -1;
        }
    });
    
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#panel-multi .search-wrapper')) {
            mpSuggestions.classList.remove('show');
            state.mp.mpSelectedIndex = -1;
        }
    });
}

function updateSuggestionHighlightMp(items) {
    items.forEach((item, i) => {
        item.classList.toggle('highlighted', i === state.mp.mpSelectedIndex);
    });
}

async function handleMpSearch() {
    const q = mpSearchInput.value.trim();
    if (q.length < 1) { mpSuggestions.classList.remove('show'); return; }
    try {
        const results = await apiCall('/api/search?q=' + encodeURIComponent(q));
        renderSuggestionsMp(results);
    } catch (err) {
        mpSuggestions.innerHTML = '<div class="suggestion-item" style="color: var(--gray)">搜索失败</div>';
        mpSuggestions.classList.add('show');
    }
}

function renderSuggestionsMp(results) {
    if (!results || results.length === 0) {
        mpSuggestions.innerHTML = '<div class="suggestion-item" style="color: var(--gray)">没有找到匹配的歌曲</div>';
        mpSuggestions.classList.add('show');
        return;
    }
    mpSuggestions.innerHTML = results.map(song => `
        <div class="suggestion-item" data-id="${song.id}" onclick="mpSelectSong(${song.id})">
            <div>
                <div class="song-title">${escapeHtml(song.title)} ${song.title_jp ? '/ ' + escapeHtml(song.title_jp) : ''}</div>
                <div class="song-meta">${song.title_cn ? escapeHtml(song.title_cn) + ' · ' : ''}${escapeHtml(song.release_year)}</div>
            </div>
            <div class="song-meta">
                <span class="song-producer">${escapeHtml(song.producer)}</span> feat. ${escapeHtml(song.vocaloid)}
            </div>
        </div>
    `).join('');
    mpSuggestions.classList.add('show');
}

function mpSelectSong(songId) {
    if (state.mp.roundStatus !== 'playing') {
        showToast('当前不在对局中', 'error');
        return;
    }
    if (state.mp.guessedMpSongIds.has(songId)) {
        showToast('这首歌已经猜过了！', 'error');
        mpSearchInput.value = '';
        mpSuggestions.classList.remove('show');
        return;
    }
    mpSearchInput.value = '';
    mpSuggestions.classList.remove('show');
    state.mp.mpSelectedIndex = -1;
    state.mp.guessedMpSongIds.add(songId);
    
    if (state.mp.ws && state.mp.ws.readyState === WebSocket.OPEN) {
        state.mp.ws.send(JSON.stringify({ type: 'guess', song_id: songId }));
    }
}

async function createRoom() {
    try {
        const result = await apiCall('/api/mp/create_room?match_format=' + state.mp.matchFormat + '&difficulty=' + state.mp.difficulty);
        state.mp.roomCode = result.room_code;
        state.mp.matchFormat = result.match_format;
        state.mp.totalRounds = result.match_format;
        state.mp.difficulty = result.difficulty || state.mp.difficulty;
        state.mp.playerId = 'host_' + Math.random().toString(36).substr(2, 6);
        connectWebSocket();
    } catch (err) {
        showToast('创建房间失败: ' + err.message, 'error');
    }
}

async function joinRoom() {
    const code = roomCodeInput.value.trim();
    if (!code || code.length !== 5) {
        showToast('请输入5位房间码', 'error');
        return;
    }
    try {
        const result = await apiCall('/api/mp/room_info?code=' + code);
        state.mp.roomCode = code;
        state.mp.matchFormat = result.match_format;
        state.mp.totalRounds = result.total_rounds;
        state.mp.difficulty = result.difficulty || state.mp.difficulty;
        state.mp.playerId = 'guest_' + Math.random().toString(36).substr(2, 6);
        connectWebSocket();
    } catch (err) {
        showToast('房间不存在或已关闭', 'error');
    }
}

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + location.host + '/ws/' + state.mp.roomCode + '/' + state.mp.playerId;
    
    const ws = new WebSocket(wsUrl);
    state.mp.ws = ws;
    
    ws.onopen = () => {
        showToast('已连接到房间', 'success');
        mpLobby.style.display = 'none';
        mpRoom.style.display = '';
        mpRoomCode.textContent = state.mp.roomCode;
        const diffNames = {'ja_legend':'日文传说','all_legend':'所有传说','zh_legend':'中文传说','zh_hall':'中文殿堂','all_myth':'所有神话'};
        mpFormatLabel.textContent = (diffNames[state.mp.difficulty] || state.mp.difficulty) + ' · BO' + state.mp.matchFormat;
        statusSelf.textContent = '未准备';
        btnReady.disabled = false;
        btnReady.textContent = '准备';
        btnNextRound.style.display = 'none';
        const diffs = [
            ['ja_legend', '日文传说'],
            ['all_legend', '所有传说'],
            ['zh_legend', '中文传说'],
            ['zh_hall', '中文殿堂'],
            ['all_myth', '所有神话'],
        ];
        hostDifficulty.innerHTML = diffs.map(([v, n]) => '<option value="' + v + '"' + (v === state.mp.difficulty ? ' selected' : '') + '>' + n + '</option>').join('');
    };
    
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMpMessage(msg);
    };
    
    ws.onclose = () => {
        showToast('连接断开', 'error');
        state.mp.ws = null;
        if (state.mp.timerInterval) {
            clearInterval(state.mp.timerInterval);
            state.mp.timerInterval = null;
        }
    };
    
    ws.onerror = () => {
        showToast('连接错误', 'error');
    };
}

function handleMpMessage(msg) {
    switch (msg.type) {
        case 'room_state':
            updateMpRoomState(msg);
            break;
        case 'round_start':
            handleMpRoundStart(msg);
            break;
        case 'guess_result':
            handleMpGuessResult(msg);
            break;
        case 'opponent_guess':
            showToast('对手已猜 ' + msg.guess_count + ' 次', 'info');
            break;
        case 'round_end':
            handleMpRoundEnd(msg);
            break;
        case 'surrender_notice':
            if (msg.round_over === false) {
                showMpNotification('有玩家投降了本局');
            } else {
                clearMpTimer();
                if (msg.winner_id === state.mp.playerId) {
                    showToast('对手投降，你赢得本局', 'success');
                }
            }
            break;
        case 'player_disconnect_forfeit':
            showToast('对手断线超时，你赢了', 'success');
            break;
        case 'error':
            showToast(msg.message, 'error');
            break;
    }
}

function updateMpRoomState(msg) {
    state.mp.matchStatus = msg.match_status;
    state.mp.roundStatus = msg.round_status;
    state.mp.currentRound = msg.current_round;
    state.mp.scores = {};
    if (msg.difficulty) state.mp.difficulty = msg.difficulty;
    if (msg.host_id) state.mp.hostId = msg.host_id;
    
    const players = Object.entries(msg.players || {});
    let self = null;
    let others = [];
    for (const [pid, p] of players) {
        state.mp.scores[pid] = p.score;
        if (pid === state.mp.playerId) self = p;
        else others.push([pid, p]);
    }
    
    if (self) {
        scoreSelf.textContent = self.score;
        statusSelf.textContent = self.connected
            ? (msg.round_status === 'playing' ? '对战中' : (self.ready ? '已准备' : '未准备'))
            : '断线';
        cardSelf.querySelector('.player-name').textContent = '你';
    }
    
    if (others.length > 0) {
        const [, opp] = others[0];
        scoreOpp.textContent = opp.score;
        statusOpp.textContent = opp.connected
            ? (msg.round_status === 'playing' ? '对战中' : (opp.ready ? '已准备' : '未准备'))
            : '断线';
        cardOpponent.querySelector('.player-name').textContent = opp.name || '玩家';
        if (others.length > 1) {
            cardOpponent.querySelector('.player-name').textContent += ' 等 ' + others.length + ' 人';
        }
    }
    
    const isHost = msg.host_id === state.mp.playerId;
    if (isHost) {
        hostTools.style.display = '';
    } else {
        hostTools.style.display = 'none';
    }
    
    if (msg.match_status === 'waiting') {
        btnReady.style.display = '';
        btnReady.disabled = self && self.ready;
        btnReady.textContent = (self && self.ready) ? '已准备' : '准备';
        btnSurrender.style.display = 'none';
        btnNextRound.style.display = 'none';
        
        const allReady = players.length >= 2 && players.every(([pid, p]) => p.connected && p.ready);
        btnStartMatch.style.display = (isHost && allReady) ? '' : 'none';
    } else if (msg.match_status === 'playing') {
        btnReady.style.display = 'none';
        btnStartMatch.style.display = 'none';
        btnSurrender.style.display = (msg.round_status === 'playing') ? '' : 'none';
        btnNextRound.style.display = 'none';
    } else if (msg.match_status === 'finished') {
        btnReady.style.display = 'none';
        btnStartMatch.style.display = 'none';
        btnSurrender.style.display = 'none';
        btnNextRound.style.display = isHost ? '' : 'none';
    }
    
    if (msg.winner) {
        if (msg.winner === state.mp.playerId) {
            showToast('你赢得了比赛', 'success');
        } else {
            showToast('比赛结束', 'error');
        }
    }
    
    if (msg.timer_remaining !== undefined && msg.round_status === 'playing') {
        updateMpTimer(msg.timer_remaining);
    } else if (msg.round_status !== 'playing') {
        clearMpTimer();
    }
}

function handleMpRoundStart(msg) {
    state.mp.roundStatus = 'playing';
    state.mp.currentRound = msg.round;
    state.mp.guessedMpSongIds = new Set();
    state.mp.roundGuesses = [];
    mpGuessesBody.innerHTML = '';
    mpGuessesContainer.style.display = 'none';
    mpSearchInput.disabled = false;
    mpSearchInput.value = '';
    mpSearchInput.focus();
    mpGuessCount.textContent = '回合 ' + msg.round + ' / ' + msg.total_rounds + ' | 已猜: 0';
    mpNotification.style.display = 'none';
    btnSurrender.style.display = '';
    updateMpTimer(msg.timer);
}

function clearMpTimer() {
    if (state.mp.timerInterval) {
        clearInterval(state.mp.timerInterval);
        state.mp.timerInterval = null;
    }
    mpTimer.style.display = 'none';
}

function updateMpTimer(seconds) {
    state.mp.timerRemaining = seconds;
    mpTimer.style.display = '';
    mpTimer.textContent = seconds;
    mpTimer.classList.toggle('warning', seconds <= 30);
    
    if (state.mp.timerInterval) clearInterval(state.mp.timerInterval);
    state.mp.timerInterval = setInterval(() => {
        state.mp.timerRemaining--;
        if (state.mp.timerRemaining <= 0) {
            clearInterval(state.mp.timerInterval);
            state.mp.timerInterval = null;
            mpTimer.textContent = '0';
            mpTimer.classList.add('warning');
        } else {
            mpTimer.textContent = state.mp.timerRemaining;
            mpTimer.classList.toggle('warning', state.mp.timerRemaining <= 30);
        }
    }, 1000);
}

function handleMpGuessResult(msg) {
    state.mp.roundGuesses.push(msg);
    mpGuessCount.textContent = '回合 ' + state.mp.currentRound + ' / ' + state.mp.totalRounds + ' | 已猜: ' + msg.guess_number;
    
    // Show table
    mpGuessesContainer.style.display = '';
    
    const row = document.createElement('tr');
    row.innerHTML = '<td>' + msg.guess_number + '</td>';
    const songTitle = msg.guess_song.title_cn
        ? msg.guess_song.title + ' / ' + msg.guess_song.title_cn
        : msg.guess_song.title + ' / ' + msg.guess_song.title_jp;
    row.innerHTML += '<td><strong>' + escapeHtml(songTitle) + '</strong></td>';
    msg.attributes.forEach(attr => {
        let cls = 'attr-cell ';
        if (attr.color === 'green') cls += 'attr-green';
        else if (attr.color === 'yellow') cls += 'attr-yellow';
        else cls += 'attr-gray';
        if (attr.arrow === 'up') cls += ' arrow-up';
        else if (attr.arrow === 'down') cls += ' arrow-down';
        let extra = '';
        if (attr.name === '级别' && attr.views !== undefined) {
            const vw = formatViews(attr.views);
            extra = '<div class="views-sub">' + (vw ? vw : '—') + '</div>';
        }
        row.innerHTML += '<td><span class="' + cls + '">' + escapeHtml(attr.value) + extra + '</span></td>';
    });
    mpGuessesBody.insertBefore(row, mpGuessesBody.firstChild);
    
    if (msg.is_correct) {
        showToast('你猜对了！', 'success');
        mpSearchInput.disabled = true;
        if (state.mp.timerInterval) {
            clearInterval(state.mp.timerInterval);
            state.mp.timerInterval = null;
        }
    }
}

function handleMpRoundEnd(msg) {
    state.mp.roundStatus = 'finished';
    mpSearchInput.disabled = true;
    clearMpTimer();
    
    // Update scores
    if (msg.scores) {
        for (const [pid, score] of Object.entries(msg.scores)) {
            if (pid === state.mp.playerId) scoreSelf.textContent = score;
            else scoreOpp.textContent = score;
        }
    }
    
    if (msg.target_song) {
        const t = msg.target_song;
        const min = Math.floor(t.length_sec / 60);
        const sec = t.length_sec % 60;
        const reason = msg.reason === 'surrender' ? '（对手投降）' : (msg.reason === 'timeout' ? '（超时）' : '');
        showMpNotification('目标歌曲: ' + t.title + ' / ' + t.title_jp + ' | ' + t.producer + ' feat. ' + t.vocaloid + reason);
    }
    
    if (msg.match_over) {
        if (msg.match_winner === state.mp.playerId) {
            showToast('你赢得了比赛', 'success');
        } else {
            showToast('比赛结束', 'error');
        }
    }
}

function showMpNotification(text) {
    mpNotification.textContent = text;
    mpNotification.className = 'mp-notification info';
    mpNotification.style.display = '';
    setTimeout(() => { mpNotification.style.display = 'none'; }, 5000);
}

function leaveRoom() {
    if (state.mp.ws) {
        state.mp.ws.send(JSON.stringify({ type: 'leave' }));
        state.mp.ws.close();
        state.mp.ws = null;
    }
    if (state.mp.timerInterval) {
        clearInterval(state.mp.timerInterval);
        state.mp.timerInterval = null;
    }
    state.mp.roomCode = null;
    state.mp.roundStatus = 'waiting';
    state.mp.matchStatus = 'waiting';
    state.mp.guessedMpSongIds = new Set();
    mpGuessesBody.innerHTML = '';
    mpGuessesContainer.style.display = 'none';
    mpTimer.style.display = 'none';
    mpNotification.style.display = 'none';
    mpSearchInput.disabled = true;
    mpRoom.style.display = 'none';
    mpLobby.style.display = '';
    showToast('已离开房间');
}

// ===== UTILITIES =====
function formatViews(v) {
    if (!v || v <= 0) return '';
    if (v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '亿';
    if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(v);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
