const API_BASE = '/admin/api';
let currentModalType = null;
let logOffset = 0;
const logLimit = 50;

// ========== 导航 ==========
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
    const res = await fetch(`${API_BASE}/stats/dashboard`);
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
        fetch(`${API_BASE}/fake-keys`),
        fetch(`${API_BASE}/real-keys`),
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
            <td>${k.provider}</td>
            <td>${k.name || '-'}</td>
            <td>${k.enabled ? '✅' : '❌'}</td>
            <td>${new Date(k.created_at).toLocaleString()}</td>
            <td>
                <button class="btn" onclick="editRealKey(${k.id}, '${k.provider}', '${(k.name||'').replace(/'/g,'\\\'')}', ${k.enabled})">编辑</button>
                <button class="btn btn-danger" onclick="deleteRealKey(${k.id})">删除</button>
            </td>
        </tr>
    `).join('');
}

async function deleteFakeKey(id) {
    if (!confirm('确定删除该假密钥？')) return;
    await fetch(`${API_BASE}/fake-keys/${id}`, { method: 'DELETE' });
    loadKeys(); loadMappings();
}
async function deleteRealKey(id) {
    if (!confirm('确定删除该真密钥？')) return;
    await fetch(`${API_BASE}/real-keys/${id}`, { method: 'DELETE' });
    loadKeys(); loadMappings();
}

// ========== Mappings ==========
async function loadMappings() {
    const res = await fetch(`${API_BASE}/mappings`);
    const mappings = await res.json();
    document.getElementById('mappings-list').innerHTML = mappings.map(m => `
        <tr>
            <td>${m.id}</td>
            <td>${m.fake_key?.name || m.fake_key?.key || m.fake_key_id}</td>
            <td>${m.real_key?.name || m.real_key_id}</td>
            <td>${m.real_key?.provider || '-'}</td>
            <td>${m.priority}</td>
            <td>
                <button class="btn btn-danger" onclick="deleteMapping(${m.id})">删除</button>
            </td>
        </tr>
    `).join('');
}
async function deleteMapping(id) {
    if (!confirm('确定删除该映射？')) return;
    await fetch(`${API_BASE}/mappings/${id}`, { method: 'DELETE' });
    loadMappings();
}

// ========== Logs ==========
async function loadFakeKeyOptions() {
    const res = await fetch(`${API_BASE}/fake-keys`);
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

    const res = await fetch(`${API_BASE}/logs?${params}`);
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
            <div class="form-group"><label>厂商</label>
                <select id="m-real-provider">
                    <option value="openai">OpenAI</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="siliconflow">SiliconFlow</option>
                    <option value="moonshot">Moonshot</option>
                </select>
            </div>
            <div class="form-group"><label>密钥</label><input id="m-real-key" placeholder="输入厂商提供的真实 API Key"></div>
            <div class="form-group"><label>名称</label><input id="m-real-name" placeholder="例如: OpenAI-主账号"></div>
            <div class="form-group"><label>启用</label><select id="m-real-enabled"><option value="1">是</option><option value="0">否</option></select></div>
        `;
    } else if (type === 'mapping') {
        title.textContent = '新建映射';
        Promise.all([
            fetch(`${API_BASE}/fake-keys`).then(r => r.json()),
            fetch(`${API_BASE}/real-keys`).then(r => r.json()),
        ]).then(([fakeKeys, realKeys]) => {
            body.innerHTML = `
                <div class="form-group"><label>假密钥</label>
                    <select id="m-map-fake">
                        ${fakeKeys.map(k => `<option value="${k.id}">${k.name || k.key}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>真密钥</label>
                    <select id="m-map-real">
                        ${realKeys.map(k => `<option value="${k.id}">${k.name || k.provider} - ${k.provider}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>优先级</label><input id="m-map-priority" type="number" value="0"></div>
            `;
        });
    } else if (type === 'edit-fake') {
        title.textContent = '编辑假密钥';
    } else if (type === 'edit-real') {
        title.textContent = '编辑真密钥';
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

function editRealKey(id, provider, name, enabled) {
    currentModalType = 'edit-real';
    currentModalType.id = id;
    const modal = document.getElementById('modal');
    document.getElementById('modal-title').textContent = '编辑真密钥';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group"><label>厂商</label>
            <select id="m-real-provider">
                <option value="openai" ${provider==='openai'?'selected':''}>OpenAI</option>
                <option value="deepseek" ${provider==='deepseek'?'selected':''}>DeepSeek</option>
                <option value="siliconflow" ${provider==='siliconflow'?'selected':''}>SiliconFlow</option>
                <option value="moonshot" ${provider==='moonshot'?'selected':''}>Moonshot</option>
            </select>
        </div>
        <div class="form-group"><label>密钥 (留空则不变)</label><input id="m-real-key" placeholder="留空表示不修改"></div>
        <div class="form-group"><label>名称</label><input id="m-real-name" value="${name}"></div>
        <div class="form-group"><label>启用</label><select id="m-real-enabled"><option value="1" ${enabled?'selected':''}>是</option><option value="0" ${!enabled?'selected':''}>否</option></select></div>
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
        await fetch(`${API_BASE}/fake-keys`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, enabled }),
        });
    } else if (currentModalType === 'real') {
        const provider = document.getElementById('m-real-provider').value;
        const key = document.getElementById('m-real-key').value;
        const name = document.getElementById('m-real-name').value;
        const enabled = document.getElementById('m-real-enabled').value === '1';
        await fetch(`${API_BASE}/real-keys`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, key, name, enabled }),
        });
    } else if (currentModalType === 'mapping') {
        const fake_key_id = parseInt(document.getElementById('m-map-fake').value);
        const real_key_id = parseInt(document.getElementById('m-map-real').value);
        const priority = parseInt(document.getElementById('m-map-priority').value || 0);
        await fetch(`${API_BASE}/mappings`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fake_key_id, real_key_id, priority }),
        });
    } else if (currentModalType === 'edit-fake') {
        const name = document.getElementById('m-fake-name').value;
        const enabled = document.getElementById('m-fake-enabled').value === '1';
        await fetch(`${API_BASE}/fake-keys/${currentModalType.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, enabled }),
        });
    } else if (currentModalType === 'edit-real') {
        const provider = document.getElementById('m-real-provider').value;
        const key = document.getElementById('m-real-key').value;
        const name = document.getElementById('m-real-name').value;
        const enabled = document.getElementById('m-real-enabled').value === '1';
        const body = { provider, name, enabled };
        if (key) body.key = key;
        await fetch(`${API_BASE}/real-keys/${currentModalType.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    }

    closeModal();
    loadKeys();
    loadMappings();
}

// ========== Log Detail Modal ==========
function showLogDetail(log) {
    const modal = document.getElementById('detail-modal');
    const body = document.getElementById('detail-modal-body');
    body.innerHTML = `
        <div class="detail-row"><span class="detail-label">ID</span><span class="detail-value">${log.id}</span></div>
        <div class="detail-row"><span class="detail-label">假密钥 ID</span><span class="detail-value">${log.fake_key_id}</span></div>
        <div class="detail-row"><span class="detail-label">真密钥 ID</span><span class="detail-value">${log.real_key_id || '-'}</span></div>
        <div class="detail-row"><span class="detail-label">厂商</span><span class="detail-value">${log.provider}</span></div>
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

// 初始加载
loadDashboard();
