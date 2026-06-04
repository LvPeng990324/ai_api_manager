# AI API MANAGER

AI 开放 API 代理过滤器，解决团队协作中员工私用公司 AI 资源的问题。

## 核心功能

- **假密钥代理**：给用户发放假密钥，真实密钥由服务端保管并转发请求
- **多厂商兼容**：支持 OpenAI、DeepSeek、SiliconFlow、Moonshot 等所有 OpenAI-compatible API
- **多密钥映射**：一个假密钥可绑定多个真实密钥，自动按优先级轮询
- **请求监控**：次数统计、Token 消耗、请求内容预览、耗时记录
- **管理后台**：免登录 Web 页面，管理密钥与查看统计

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少设置 `MASTER_KEY`：

```bash
# 生成加密密钥
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成的密钥填入 `.env` 的 `MASTER_KEY`。

### 3. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. 访问管理后台

打开浏览器访问 `http://localhost:8000/admin/`

- 先创建**真密钥**（厂商的真实 API Key）
- 再创建**假密钥**（分配给用户的代理 Key）
- 最后创建**映射关系**，将假密钥与真密钥绑定

## 用户接入方式

以 OpenAI SDK 为例，用户只需修改 `base_url` 和 `api_key`：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-proxy:8000/v1/deepseek",  # 代理地址 + 厂商标识
    api_key="fk-xxxxxxxxx"                           # 假密钥
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello"}]
)
```

Cursor、Claude Code、 Windsurf 等工具同理，在设置中替换 API Base URL 和 API Key 即可。

### 支持的厂商标识

| 厂商 | base_url 路径 |
|------|--------------|
| OpenAI | `/v1/openai/...` |
| DeepSeek | `/v1/deepseek/...` |
| SiliconFlow | `/v1/siliconflow/...` |
| Moonshot | `/v1/moonshot/...` |

所有厂商均走 OpenAI-compatible 协议透传。

## 项目结构

```
.
├── main.py              # FastAPI 入口
├── config.py            # 配置
├── requirements.txt
├── .env
├── models/              # SQLAlchemy ORM 模型
├── schemas/             # Pydantic 数据校验
├── services/            # 业务逻辑
├── routers/             # API 路由
│   ├── proxy.py         # 代理转发
│   └── admin.py         # 管理后台 API
├── static/admin/        # 管理后台前端页面
└── utils/               # 工具函数
```

## 安全提示

- 管理后台默认**免登录**，建议通过内网部署、Nginx Basic Auth 或 IP 白名单保护
- 真实 API Key 通过 Fernet 对称加密存储，加密密钥由 `MASTER_KEY` 环境变量提供
- 生产环境请妥善保管 `.env` 文件，不要提交到代码仓库

## License

MIT
