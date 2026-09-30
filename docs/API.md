# 本机 API 与集成

运行 `python3 -m shilu`。监听仅限 127.0.0.1，不是公网托管 API。

先 `GET /api/session` 获得本机进程令牌；其余接口需请求头 `X-Shilu-Token`。写操作 Content-Type 为 `application/json`。不允许跨站 Origin；令牌在服务重启后更新。

| 方法 / 路径 | 输入 | 结果 |
|---|---|---|
| GET `/api/projects` | 无 | 场次元数据列表 |
| POST `/api/projects` | `config, transcript` | 新项目 |
| GET `/api/projects/{id}` | 无 | 项目全文、检查提示 |
| POST `/api/projects/{id}/generate` | `revision, mode: verbatim / live` | 单独的 engine 初稿 |
| POST `/api/projects/{id}/save` | `revision, config, sections` | 人工稿，旧版本入 history，复核失效 |
| POST `/api/projects/{id}/review` | `revision, reviewer, confirmed: true` | 绑定当前正文摘要的复核 |
| POST `/api/projects/{id}/preview` | `revision` | 已保存人工稿的 HTML |
| POST `/api/projects/{id}/export` | `revision` | 经复核的文章 ZIP，不含原稿 |
| POST `/api/projects/{id}/backup` | `revision` | 私人迁移 JSON，含原稿与历史 |
| POST `/api/import` | `project` | 新 ID、原稿与最新人工稿，复核重置 |

冲突返回 409；输入校验失败返回 400。数据结构及限制见 README。`preview` 只用于阅读检查，允许未复核稿；只有 `export` 是受复核闸门约束的正式文章包。

Python 集成：

```python
from shilu.core import Store
store = Store('/private/path/shilu.sqlite3')
project = store.create({'title': '一场分享', 'author': '讲者'}, '足够完整的现场逐字稿……' * 10)
project = store.draft(project['id'], project['revision'], 'verbatim')
```

模型适配在 `shilu.core.generate`。首版调用兼容 Chat Completions 的 JSON 接口，返回结构化章节；不能把本机令牌当作多人身份系统。
