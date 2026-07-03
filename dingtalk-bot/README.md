# 钉钉智能对话机器人 🤖

基于 **Python + FastAPI + Claude API** 的钉钉企业内部应用机器人，支持智能对话/客服功能。

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI (async) |
| 运行时 | Python 3.10+ / Uvicorn |
| LLM | Anthropic Claude API |
| 加密 | PyCryptodome (AES-256-CBC) |
| 配置 | pydantic-settings / 环境变量 |
| HTTP | httpx (async) |
| 会话存储 | Memory（开发）/ Redis（生产） |
| 容器化 | Docker + docker-compose |

## 快速开始

### 1. 配置钉钉开放平台

1. 登录 [钉钉开放平台](https://open-dev.dingtalk.com/)
2. 创建企业内部应用 → 获取 **AppKey** 和 **AppSecret**
3. 在应用配置 → 消息接收模式 → 配置回调 URL：`https://your-domain.com/webhook/callback`
4. 配置 **AES 密钥**（43字符）和 **回调 Token**

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入真实的钉钉和 LLM 配置
```

必要配置项：

```ini
DINGTALK__APP_KEY=your_app_key
DINGTALK__APP_SECRET=your_app_secret
DINGTALK__BOT_CODE=your_bot_code
DINGTALK__AES_KEY=your_43_char_aes_key
DINGTALK__CALLBACK_TOKEN=your_callback_token

LLM__ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

### 3. 运行

**本地开发：**

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Docker：**

```bash
docker compose -f docker/docker-compose.yml up
```

**使用 Redis（生产推荐）：**

```bash
docker compose -f docker/docker-compose.yml --profile redis up
```

## API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/health` | 存活检查 |
| GET | `/health/ready` | 就绪检查 |
| POST | `/webhook/callback` | 钉钉回调入口 |
| GET | `/admin/sessions` | 列出活跃会话 |
| GET | `/admin/sessions/{id}` | 查看会话详情 |
| DELETE | `/admin/sessions/{id}` | 清理会话 |
| DELETE | `/admin/sessions` | 清理所有会话 |
| GET | `/admin/plugins` | 列出已注册插件 |
| GET | `/admin/stats` | 运行时统计 |

## 项目结构

```
dingtalk-bot/
├── app/
│   ├── main.py                    # FastAPI 入口 + 生命周期
│   ├── config.py                  # 配置管理（pydantic-settings）
│   ├── dependencies.py            # 依赖注入工厂
│   ├── api/
│   │   ├── webhook.py             # 钉钉回调端点
│   │   ├── health.py              # 健康检查
│   │   └── admin.py               # 管理端点
│   ├── core/
│   │   ├── dingtalk/
│   │   │   ├── client.py          # 钉钉 API 客户端
│   │   │   ├── crypto.py          # AES 加解密
│   │   │   └── constants.py       # 常量定义
│   │   ├── llm/
│   │   │   ├── base.py            # LLM 抽象基类
│   │   │   ├── claude.py          # Claude API 实现
│   │   │   └── factory.py         # 提供者工厂
│   │   ├── session/
│   │   │   ├── manager.py         # 会话管理器
│   │   │   ├── store.py           # 存储抽象 + MemoryStore
│   │   │   └── store_redis.py     # RedisStore
│   │   └── message/
│   │       ├── handler.py         # 消息分发管道
│   │       ├── parser.py          # 消息解析器
│   │       ├── builder.py         # 响应构建器
│   │       └── plugins/           # 插件系统
│   │           ├── base.py        # 插件基类
│   │           ├── register.py    # 插件注册器
│   │           ├── echo.py        # 调试回显
│   │           ├── help.py        # 帮助命令
│   │           └── llm_chat.py    # LLM 对话
│   ├── models/
│   │   ├── dingtalk.py            # 钉钉 API 数据模型
│   │   ├── message.py             # 内部消息模型
│   │   └── session.py             # 会话模型
│   └── utils/
│       └── logger.py              # 日志配置
├── tests/                         # 测试（61+ 个测试用例）
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
└── requirements.txt
```

## 架构设计

### 数据流

```
钉钉用户 → 加密 POST /webhook/callback
  → DingTalkCrypto 验证签名 + 解密
  → MessageParser 解析为 IncomingMessage
  → asyncio.create_task (fire-and-forget, 不阻塞 HTTP)
      → MessageHandler 遍历插件责任链
      → EchoPlugin | HelpPlugin | LLMChatPlugin
      → LLMProvider (Claude API)
      → SessionManager (上下文管理)
      → DingTalkClient.send_text() 异步回复
  → 立即返回签名响应 (满足 5s 超时)
```

### 插件架构

采用**责任链模式**。消息到来时，按注册顺序遍历插件，第一个 `can_handle()` 返回 True 的插件处理该消息。

- **EchoPlugin** — 调试工具，响应 `/echo` 命令
- **HelpPlugin** — 帮助信息，响应 `/help` 或 `/start`
- **LLMChatPlugin** — 兜底处理，调用 Claude API 智能回复

### 会话管理

- 每 `ConversationId` 一个会话，30 分钟 TTL 自动过期
- 滑动窗口上下文裁剪：超出 Token 预算时自动丢弃最早消息
- 开发用 MemoryStore，生产用 RedisStore

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_crypto.py -v
pytest tests/test_handlers.py -v

# 查看覆盖率
pytest tests/ --cov=app -v
```

## 部署注意事项

1. **HTTPS 必需**：钉钉回调要求 HTTPS，推荐使用 Nginx + Certbot 或云厂商 LB
2. **外网可达**：回调 URL 需要钉钉服务器可访问
3. **5 秒超时**：webhook 端点的 fire-and-forget 模式确保在 5 秒内返回
4. **多 Worker**：使用 RedisStore 会话存储，多个 Uvicorn worker 共享会话状态
