# 实录工坊 · Shilu Studio

**把现场逐字稿整理成有出处、可复核、可迁移的实录文章。**

从 [qiuyiwu.com](https://qiuyiwu.com/) 的实录制作流程提炼而来。适用于演讲、课程、访谈和分享会。保留讲者原意与真实细节，整理口语、章节和阅读结构；所有 AI 初稿均需人工复核。

这是 **v0.1 单人、本机应用**，不是多人公网服务。Python 3.9+，标准库即可运行，无需安装第三方依赖。

```sh
git clone https://github.com/qiuyiwu1989-star/shilu-studio.git
cd shilu-studio
python3 -m shilu
```

打开 `http://127.0.0.1:8765`。数据默认保存在当前目录的 `workspace/shilu.sqlite3`。

## 使用流程

1. 新建实录：填写标题、讲者、场合、日期、受众、取材范围和脱敏要求。
2. 粘贴或导入 TXT / Markdown 逐字稿；空行划分来源段落，保留已有时间码。
3. 选择“按原文分段”离线整理，或使用配置好的模型生成初稿。
4. 在章节编辑区修改标题、正文和来源编号，对照原稿复核。
5. 保存人工正文，检查脱敏疑点，填写复核人并确认当前版本。
6. 导出文章包（自包含 HTML、Markdown、公开 JSON），上传到任意静态站或 CMS。

“按原文分段”不调用 AI，也不模拟生成。它完整保留原文，供手工整理。可用 `examples/demo-transcript.txt` 体验全流程，该文件是虚构教学素材。

## 已实现能力

- 稿件列表、逐字稿导入、场次配置、章节编辑、来源段落关联。
- AI 初稿与人工正文分开存储；重新生成不覆盖人工正文。
- OpenAI 兼容 Chat Completions 接口适配（服务地址、模型和密钥可替换）。
- 正则疑点扫描、人工复核记录；正文或配置修改后，原复核自动失效。
- SQLite 持久化、并发版本检查、人工稿历史快照。
- 自包含阅读页、目录、响应式排版、Article JSON-LD；不依赖主站 CSS / JS。
- 文章包与私人迁移包分开导出；迁移包可导入另一台安装，生成新的项目 ID。
- 仅监听 127.0.0.1；Host / Origin 检查、本机会话令牌、纯文本转义输出。

## 可选 AI 配置

火山方舟已内置供应商配置，默认主力模型为 `deepseek-v4-1-flash-260910`：

```sh
cp .env.example .env
# 在本机 .env 填写 SHILU_API_KEY，然后启动
python3 -m shilu
```

`.env` 已被 Git 忽略，建议限制文件权限为仅自己可读。应用启动时读取，环境变量优先；也可通过 `--env-file /private/path/config.env` 指定私有配置。默认低思考强度，可通过 `SHILU_REASONING_EFFORT` / `SHILU_THINKING` 调整。浏览器只显示供应商和模型名称，密钥不返回前端。

可选真实样稿测试：`python3 scripts/eval_recap.py --live`，会消耗模型 token，只发送仓库中的虚构评测稿，结果保存在被忽略的 `workspace/evaluation/`。检查关注来源覆盖、限定条件、数字和脱敏，仍需人工阅读成稿。短样稿测试不代表长课程完整质量。

从所选模型服务获取兼容接口配置，在启动前设置环境变量。BASE_URL 指向接口根路径（通常以 `/v1` 结尾），程序追加 `/chat/completions`。

```sh
export SHILU_BASE_URL='https://your-provider.example/v1'
export SHILU_MODEL='your-model-id'
export SHILU_API_KEY='your-api-key'
export SHILU_MAX_TOKENS='8192'
python3 -m shilu
```

示例地址不可直接调用。密钥从私有配置加载到启动进程环境中，不进入浏览器、数据库、文章包或迁移包。点击“AI 整理初稿”会把本稿原文及场次配置发送给你配置的服务。模型输出必须为完整 JSON 且引用有效原稿编号，截断或格式错误不保存。接口兼容不等于所有模型已验证；真实短样稿评测也不等于长课程和课件全流程验收。

## 迁移与集成

- **换电脑 / 换安装**：导出私人迁移包 JSON，另一安装点击“导入迁移包”。恢复原稿、场次配置、最新人工稿；目标安装重新复核。包中保留的历史仅供查看，本版不重新导入历史、AI 初稿或审核记录。
- **完整备份恢复**：停止应用后复制整个 `workspace/`，在新电脑以 `--data-dir` 指向该目录启动，保留全部项目历史与审核记录。
- **嵌入其他产品**：复用 `shilu.core.Store` 和渲染函数，或参考 [API 说明](docs/API.md) 调用本机接口。
- **换发布目标**：文章包中的 `index.html` 自包含、可直接打开；上传至任意静态服务。首版不自动部署，不写入 qiuyiwu.com。

```sh
python3 -m shilu --port 8766 --data-dir /path/to/private-workspace
python3 -m unittest discover -s tests -v
```

## 首版边界

输入限 TXT / Markdown，20–80000 字、最多 200 段。暂未提供录音转写、说话人识别、PDF / PPT 渲染、课件自动对齐、配图编辑、语义检索、批量任务、多人权限和自动部署。既有时间码作为原文保留，没有自动音频定位。

当前 AI 请求为同步调用（120 秒超时），不提供跨进程任务恢复；不能通过反向代理直接当公网后台使用。来源编号校验不证明事实正确，扫描也不能替代人工脱敏。

完整的既有工作流、源码依据、独立化架构与后续计划见 [工作流与能力梳理](docs/WORKFLOW.md)。

## 许可

代码采用 [MIT License](LICENSE)。仓库只包含通用实现与虚构示例，不包含 qiuyiwu.com 的私人逐字稿、客户信息、课件、站点数据和生产凭据。原站文章与第三方素材不因本代码开源而改变许可。
