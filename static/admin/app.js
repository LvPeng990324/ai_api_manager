const API_BASE = '/admin/api';
let currentModalType = null;
let logOffset = 0;
const logLimit = 50;
let currentUser = null;
let currentRole = null;

// ========== Auth & Init ==========

function getToken() {
    return localStorage.getItem('admin_token') || '';
}

function setToken(token) {
    localStorage.setItem('admin_token', token);
}

function clearToken() {
    localStorage.removeItem('admin_token');
}

async function apiFetch(url, options = {}) {
    const token = getToken();
    options.headers = options.headers || {};
    if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
    }
    options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
    const res = await fetch(url, options);
    if (res.status === 401) {
        clearToken();
        showLoginPage();
        throw new Error('Unauthorized');
    }
    return res;
}

function showLoginPage(isInit = false) {
    document.getElementById('login-page').style.display = 'flex';
    document.getElementById('app-page').style.display = 'none';
    document.getElementById('login-subtitle').textContent = isInit ? '创建超级管理员' : '管理员登录';
    document.getElementById('login-btn').textContent = isInit ? '创建并登录' : '登录';
    document.getElementById('login-btn').onclick = isInit ? handleInit : handleLogin;
}

function showAppPage() {
    document.getElementById('login-page').style.display = 'none';
    document.getElementById('app-page').style.display = 'block';
}

async function checkAuth() {
    const token = getToken();
    if (!token) {
        // 检查是否需要初始化
        const statusRes = await fetch(`${API_BASE}/init-status`);
        const statusData = await statusRes.json();
        showLoginPage(statusData.need_init);
        return;
    }
    try {
        const res = await apiFetch(`${API_BASE}/me`);
        if (!res.ok) {
            const statusRes = await fetch(`${API_BASE}/init-status`);
            const statusData = await statusRes.json();
            showLoginPage(statusData.need_init);
            return;
        }
        currentUser = await res.json();
        currentRole = currentUser.role;
        document.getElementById('current-user').textContent = `${currentUser.username} (${currentRole === 'super_admin' ? '超级管理员' : '管理员'})`;
        if (currentRole === 'super_admin') {
            document.getElementById('nav-users').style.display = '';
        }
        showAppPage();
        loadDashboard();
    } catch (e) {
        const statusRes = await fetch(`${API_BASE}/init-status`);
        const statusData = await statusRes.json();
        showLoginPage(statusData.need_init);
    }
}

async function handleLogin() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';
    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
            const data = await res.json();
            errorEl.textContent = data.detail || '登录失败';
            return;
        }
        const data = await res.json();
        setToken(data.access_token);
        await checkAuth();
    } catch (e) {
        errorEl.textContent = '网络错误';
    }
}

async function handleInit() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';
    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
            const data = await res.json();
            errorEl.textContent = data.detail || '创建失败';
            return;
        }
        // 创建成功后自动登录
        const loginRes = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const loginData = await loginRes.json();
        setToken(loginData.access_token);
        await checkAuth();
    } catch (e) {
        errorEl.textContent = '网络错误';
    }
}

function logout() {
    clearToken();
    location.reload();
}

// ========== Navigation ==========
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        if (btn.dataset.tab === 'dashboard') loadDashboard();
        if (btn.dataset.tab === 'keys') loadKeys();
        if (btn.dataset.tab === 'mappings') loadMappings();
        if (btn.dataset.tab === 'logs') { loadFakeKeyOptions(); loadLogs(); }
        if (btn.dataset.tab === 'users') loadUsers();
    });
});

document.querySelectorAll('.sub-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('sub-' + btn.dataset.sub).classList.add('active');
    });
});

// ========== Dashboard ==========
async function loadDashboard() {
    const res = await apiFetch(`${API_BASE}/stats/dashboard`);
    const data = await res.json();
    document.getElementById('today-requests').textContent = data.today_requests;
    document.getElementById('today-input').textContent = data.today_tokens_input;
    document.getElementById('today-output').textContent = data.today_tokens_output;
    document.getElementById('week-requests').textContent = data.total_requests_7d;
    document.getElementById('week-input').textContent = data.total_tokens_input_7d;
    document.getElementById('week-output').textContent = data.total_tokens_output_7d;

    const tbody = document.getElementById('top-keys');
    tbody.innerHTML = data.top_keys.map(k => `
        <tr>
            <td>${k.fake_key_id}</td>
            <td>${k.name || '-'}</td>
            <td><span class="code">${k.key}</span></td>
            <td>${k.total_requests}</td>
        </tr>
    `).join('');
}

// ========== Keys ==========
async function loadKeys() {
    const [fakeRes, realRes] = await Promise.all([
        apiFetch(`${API_BASE}/fake-keys`),
        apiFetch(`${API_BASE}/real-keys`),
    ]);
    const fakeKeys = await fakeRes.json();
    const realKeys = await realRes.json();

    document.getElementById('fake-keys-list').innerHTML = fakeKeys.map(k => `
        <tr>
            <td>${k.id}</td>
            <td><span class="code">${k.key}</span></td>
            <td>${k.name || '-'}</td>
            <td>${k.enabled ? '✅' : '❌'}</td>
            <td>${new Date(k.created_at).toLocaleString()}</td>
            <td>
                <button class="btn" onclick="editFakeKey(${k.id}, '${(k.name||'').replace(/'/g,'\\\'')}', ${k.enabled})">编辑</button>
                <button class="btn btn-danger" onclick="deleteFakeKey(${k.id})">删除</button>
            </td>
        </tr>
    `).join('');

    document.getElementById('real-keys-list').innerHTML = realKeys.map(k => `
        <tr>
            <td>${k.id}</td>
            <td>${k.provider === 'anthropic' ? 'Anthropic 风格' : 'OpenAI 风格'}</td>
            <td><span class="code" title="${k.base_url}">${k.base_url || '-'}</span></td>
            <td>${k.name || '-'}</td>
            <td>${k.enabled ? '✅' : '❌'}</td>
            <td>${new Date(k.created_at).toLocaleString()}</td>
            <td>
                <button class="btn" onclick="editRealKey(${k.id}, '${k.provider}', '${(k.base_url||'').replace(/'/g,'\\\'')}', '${(k.name||'').replace(/'/g,'\\\'')}', ${k.enabled})">编辑</button>
                <button class="btn btn-danger" onclick="deleteRealKey(${k.id})">删除</button>
            </td>
        </tr>
    `).join('');
}

async function deleteFakeKey(id) {
    if (!confirm('确定删除该假密钥？')) return;
    await apiFetch(`${API_BASE}/fake-keys/${id}`, { method: 'DELETE' });
    loadKeys(); loadMappings();
}
async function deleteRealKey(id) {
    if (!confirm('确定删除该真密钥？')) return;
    await apiFetch(`${API_BASE}/real-keys/${id}`, { method: 'DELETE' });
    loadKeys(); loadMappings();
}

// ========== Mappings ==========
async function loadMappings() {
    const res = await apiFetch(`${API_BASE}/mappings`);
    const mappings = await res.json();
    document.getElementById('mappings-list').innerHTML = mappings.map(m => `
        <tr>
            <td>${m.id}</td>
            <td>${m.fake_key?.name || m.fake_key?.key || m.fake_key_id}</td>
            <td>${m.real_key?.name || m.real_key_id}</td>
            <td>${m.real_key ? (m.real_key.provider === 'anthropic' ? 'Anthropic 风格' : 'OpenAI 风格') : '-'}</td>
            <td>${m.priority}</td>
            <td>
                <button class="btn btn-danger" onclick="deleteMapping(${m.id})">删除</button>
            </td>
        </tr>
    `).join('');
}
async function deleteMapping(id) {
    if (!confirm('确定删除该映射？')) return;
    await apiFetch(`${API_BASE}/mappings/${id}`, { method: 'DELETE' });
    loadMappings();
}

// ========== Logs ==========
async function loadFakeKeyOptions() {
    const res = await apiFetch(`${API_BASE}/fake-keys`);
    const keys = await res.json();
    const select = document.getElementById('log-filter-key');
    const current = select.value;
    select.innerHTML = '<option value="">全部假密钥</option>' +
        keys.map(k => `<option value="${k.id}">${k.name || k.key}</option>`).join('');
    select.value = current;
}

async function loadLogs() {
    const keyId = document.getElementById('log-filter-key').value;
    const provider = document.getElementById('log-filter-provider').value;
    const params = new URLSearchParams({ limit: logLimit, offset: logOffset });
    if (keyId) params.set('fake_key_id', keyId);
    if (provider) params.set('provider', provider);

    const res = await apiFetch(`${API_BASE}/logs?${params}`);
    const data = await res.json();
    const tbody = document.getElementById('logs-list');
    tbody.innerHTML = data.items.map(log => `
        <tr>
            <td>${log.id}</td>
            <td><span class="code">${log.fake_key_id}</span></td>
            <td>${log.provider}</td>
            <td>${log.model || '-'}</td>
            <td>${log.status_code}</td>
            <td>${log.latency_ms}</td>
            <td>${log.tokens_input}</td>
            <td>${log.tokens_output}</td>
            <td>${new Date(log.created_at).toLocaleString()}</td>
            <td><span class="log-preview" title="点击查看详情">${log.request_preview.substring(0, 40)}${log.request_preview.length>40?'...':''}</span></td>
        </tr>
    `).join('');

    tbody.querySelectorAll('.log-preview').forEach((el, i) => {
        el.addEventListener('click', () => showLogDetail(data.items[i]));
    });

    const totalPages = Math.ceil(data.total / logLimit) || 1;
    const currentPage = Math.floor(logOffset / logLimit) + 1;
    document.getElementById('page-info').textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页 (${data.total} 条)`;
}

function changePage(delta) {
    logOffset = Math.max(0, logOffset + delta * logLimit);
    loadLogs();
}

// ========== Users ==========
async function loadUsers() {
    const res = await apiFetch(`${API_BASE}/users`);
    const users = await res.json();
    document.getElementById('users-list').innerHTML = users.map(u => `
        <tr>
            <td>${u.id}</td>
            <td>${u.username}</td>
            <td>${u.role === 'super_admin' ? '超级管理员' : '管理员'}</td>
            <td>${new Date(u.created_at).toLocaleString()}</td>
            <td>
                <button class="btn" onclick="editUser(${u.id}, '${u.username.replace(/'/g,'\\\'')}')">编辑</button>
                ${u.role !== 'super_admin' ? `<button class="btn btn-danger" onclick="deleteUser(${u.id})">删除</button>` : ''}
            </td>
        </tr>
    `).join('');
}

async function deleteUser(id) {
    if (!confirm('确定删除该管理员？')) return;
    await apiFetch(`${API_BASE}/users/${id}`, { method: 'DELETE' });
    loadUsers();
}

// ========== Modal ==========
function showModal(type) {
    currentModalType = type;
    const modal = document.getElementById('modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    modal.classList.add('active');

    if (type === 'fake') {
        title.textContent = '新建假密钥';
        body.innerHTML = `
            <div class="form-group"><label>名称</label><input id="m-fake-name" placeholder="例如: 研发团队"></div>
            <div class="form-group"><label>启用</label><select id="m-fake-enabled"><option value="1">是</option><option value="0">否</option></select></div>
        `;
    } else if (type === 'real') {
        title.textContent = '新建真密钥';
        body.innerHTML = `
            <div class="form-group"><label>接口规范</label>
                <select id="m-real-provider">
                    <option value="openai">OpenAI 风格</option>
                    <option value="anthropic">Anthropic 风格</option>
                </select>
            </div>
            <div class="form-group"><label>Base URL</label><input id="m-real-base-url" placeholder="例如: https://api.openai.com/v1"></div>
            <div class="form-group"><label>密钥</label><input id="m-real-key" placeholder="输入上游提供的真实 API Key"></div>
            <div class="form-group"><label>名称</label><input id="m-real-name" placeholder="例如: OpenAI-主账号"></div>
            <div class="form-group"><label>启用</label><select id="m-real-enabled"><option value="1">是</option><option value="0">否</option></select></div>
        `;
    } else if (type === 'mapping') {
        title.textContent = '新建映射';
        Promise.all([
            apiFetch(`${API_BASE}/fake-keys`).then(r => r.json()),
            apiFetch(`${API_BASE}/real-keys`).then(r => r.json()),
        ]).then(([fakeKeys, realKeys]) => {
            body.innerHTML = `
                <div class="form-group"><label>假密钥</label>
                    <select id="m-map-fake">
                        ${fakeKeys.map(k => `<option value="${k.id}">${k.name || k.key}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>真密钥</label>
                    <select id="m-map-real">
                        ${realKeys.map(k => `<option value="${k.id}">${k.name || k.base_url} - ${k.provider === 'anthropic' ? 'Anthropic 风格' : 'OpenAI 风格'}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>优先级</label><input id="m-map-priority" type="number" value="0"></div>
            `;
        });
    } else if (type === 'user') {
        title.textContent = '新建管理员';
        body.innerHTML = `
            <div class="form-group"><label>用户名</label><input id="m-user-name" placeholder="输入用户名"></div>
            <div class="form-group"><label>密码</label><input id="m-user-pwd" type="password" placeholder="输入密码"></div>
        `;
    } else if (type === 'edit-fake') {
        title.textContent = '编辑假密钥';
    } else if (type === 'edit-real') {
        title.textContent = '编辑真密钥';
    } else if (type === 'edit-user') {
        title.textContent = '编辑用户';
    }
}

function editFakeKey(id, name, enabled) {
    currentModalType = 'edit-fake';
    currentModalType.id = id;
    const modal = document.getElementById('modal');
    document.getElementById('modal-title').textContent = '编辑假密钥';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>名称</label><input id="m-fake-name" value="${name}"></div>
        <div class="form-group"><label>启用</label><select id="m-fake-enabled"><option value="1" ${enabled?'selected':''}>是</option><option value="0" ${!enabled?'selected':''}>否</option></select></div>
    `;
    modal.classList.add('active');
}

function editRealKey(id, provider, baseUrl, name, enabled) {
    currentModalType = 'edit-real';
    currentModalType.id = id;
    const modal = document.getElementById('modal');
    document.getElementById('modal-title').textContent = '编辑真密钥';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>接口规范</label>
            <select id="m-real-provider">
                <option value="openai" ${provider==='openai'?'selected':''}>OpenAI 风格</option>
                <option value="anthropic" ${provider==='anthropic'?'selected':''}>Anthropic 风格</option>
            </select>
        </div>
        <div class="form-group"><label>Base URL</label><input id="m-real-base-url" value="${baseUrl}" placeholder="例如: https://api.openai.com/v1"></div>
        <div class="form-group"><label>密钥 (留空则不变)</label><input id="m-real-key" placeholder="留空表示不修改"></div>
        <div class="form-group"><label>名称</label><input id="m-real-name" value="${name}"></div>
        <div class="form-group"><label>启用</label><select id="m-real-enabled"><option value="1" ${enabled?'selected':''}>是</option><option value="0" ${!enabled?'selected':''}>否</option></select></div>
    `;
    modal.classList.add('active');
}

function editUser(id, username) {
    currentModalType = 'edit-user';
    currentModalType.id = id;
    const modal = document.getElementById('modal');
    document.getElementById('modal-title').textContent = '编辑用户';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>用户名 (留空则不变)</label><input id="m-user-name" value="${username}" placeholder="留空表示不修改"></div>
        <div class="form-group"><label>密码 (留空则不变)</label><input id="m-user-pwd" type="password" placeholder="留空表示不修改"></div>
    `;
    modal.classList.add('active');
}

function closeModal() {
    document.getElementById('modal').classList.remove('active');
    currentModalType = null;
}

async function submitModal() {
    if (!currentModalType) return;

    if (currentModalType === 'fake') {
        const name = document.getElementById('m-fake-name').value;
        const enabled = document.getElementById('m-fake-enabled').value === '1';
        await apiFetch(`${API_BASE}/fake-keys`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, enabled }),
        });
    } else if (currentModalType === 'real') {
        const provider = document.getElementById('m-real-provider').value;
        const base_url = document.getElementById('m-real-base-url').value.trim();
        const key = document.getElementById('m-real-key').value;
        const name = document.getElementById('m-real-name').value;
        const enabled = document.getElementById('m-real-enabled').value === '1';
        await apiFetch(`${API_BASE}/real-keys`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, base_url, key, name, enabled }),
        });
    } else if (currentModalType === 'mapping') {
        const fake_key_id = parseInt(document.getElementById('m-map-fake').value);
        const real_key_id = parseInt(document.getElementById('m-map-real').value);
        const priority = parseInt(document.getElementById('m-map-priority').value || 0);
        await apiFetch(`${API_BASE}/mappings`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fake_key_id, real_key_id, priority }),
        });
    } else if (currentModalType === 'user') {
        const username = document.getElementById('m-user-name').value;
        const password = document.getElementById('m-user-pwd').value;
        await apiFetch(`${API_BASE}/users`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
    } else if (currentModalType === 'edit-fake') {
        const name = document.getElementById('m-fake-name').value;
        const enabled = document.getElementById('m-fake-enabled').value === '1';
        await apiFetch(`${API_BASE}/fake-keys/${currentModalType.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, enabled }),
        });
    } else if (currentModalType === 'edit-real') {
        const provider = document.getElementById('m-real-provider').value;
        const base_url = document.getElementById('m-real-base-url').value.trim();
        const key = document.getElementById('m-real-key').value;
        const name = document.getElementById('m-real-name').value;
        const enabled = document.getElementById('m-real-enabled').value === '1';
        const body = { provider, base_url, name, enabled };
        if (key) body.key = key;
        await apiFetch(`${API_BASE}/real-keys/${currentModalType.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    } else if (currentModalType === 'edit-user') {
        const username = document.getElementById('m-user-name').value;
        const password = document.getElementById('m-user-pwd').value;
        const body = {};
        if (username) body.username = username;
        if (password) body.password = password;
        await apiFetch(`${API_BASE}/users/${currentModalType.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    }

    closeModal();
    loadKeys();
    loadMappings();
    if (document.getElementById('tab-users').classList.contains('active')) {
        loadUsers();
    }
}

// ========== Log Detail Modal ==========
function showLogDetail(log) {
    const modal = document.getElementById('detail-modal');
    const body = document.getElementById('detail-modal-body');
    body.innerHTML = `
        <div class="detail-row"><span class="detail-label">ID</span><span class="detail-value">${log.id}</span></div>
        <div class="detail-row"><span class="detail-label">假密钥 ID</span><span class="detail-value">${log.fake_key_id}</span></div>
        <div class="detail-row"><span class="detail-label">真密钥 ID</span><span class="detail-value">${log.real_key_id || '-'}</span></div>
        <div class="detail-row"><span class="detail-label">接口规范</span><span class="detail-value">${log.provider === 'anthropic' ? 'Anthropic 风格' : 'OpenAI 风格'}</span></div>
        <div class="detail-row"><span class="detail-label">模型</span><span class="detail-value">${log.model || '-'}</span></div>
        <div class="detail-row"><span class="detail-label">接口</span><span class="detail-value">${log.endpoint || '-'}</span></div>
        <div class="detail-row"><span class="detail-label">状态码</span><span class="detail-value">${log.status_code}</span></div>
        <div class="detail-row"><span class="detail-label">耗时 (ms)</span><span class="detail-value">${log.latency_ms}</span></div>
        <div class="detail-row"><span class="detail-label">Input Tokens</span><span class="detail-value">${log.tokens_input}</span></div>
        <div class="detail-row"><span class="detail-label">Output Tokens</span><span class="detail-value">${log.tokens_output}</span></div>
        <div class="detail-row"><span class="detail-label">时间</span><span class="detail-value">${new Date(log.created_at).toLocaleString()}</span></div>
        <div class="detail-row"><span class="detail-label">请求预览</span></div>
        <pre class="detail-preview"></pre>
    `;
    const previewEl = body.querySelector('.detail-preview');
    let previewText = log.request_preview || '';
    try {
        previewText = JSON.stringify(JSON.parse(previewText), null, 2);
    } catch (e) {
        // 不是合法 JSON，保持原样
    }
    previewEl.textContent = previewText;
    modal.classList.add('active');
}

function closeDetailModal() {
    document.getElementById('detail-modal').classList.remove('active');
}

// ========== Connection Test ==========
async function sendTestRequest() {
    const key = document.getElementById('test-key').value.trim();
    const url = document.getElementById('test-url').value.trim();
    const message = document.getElementById('test-message').value.trim();
    const model = document.getElementById('test-model').value.trim() || 'gpt-4o-mini';

    const resultBox = document.getElementById('test-result');
    const resultBody = document.getElementById('test-result-body');

    if (!key) {
        resultBody.textContent = '请填写假密钥';
        resultBox.style.display = 'block';
        return;
    }
    if (!url) {
        resultBody.textContent = '请填写请求 URL';
        resultBox.style.display = 'block';
        return;
    }
    if (!message) {
        resultBody.textContent = '请填写聊天内容';
        resultBox.style.display = 'block';
        return;
    }

    resultBody.textContent = '请求发送中...';
    resultBox.style.display = 'block';

    const body = {
        model: model,
        messages: [{ role: 'user', content: message }],
        stream: false,
    };

    const startTime = Date.now();
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${key}`,
            },
            body: JSON.stringify(body),
        });
        const latency = Date.now() - startTime;
        let text = '';
        try {
            const data = await res.json();
            text = JSON.stringify(data, null, 2);
        } catch (e) {
            text = await res.text();
        }
        resultBody.textContent = `HTTP ${res.status} (${latency}ms)\n\n${text}`;
    } catch (err) {
        resultBody.textContent = `请求失败: ${err.message}`;
    }
}

// 初始加载
checkAuth();
