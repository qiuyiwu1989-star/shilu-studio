# MCP 与跨场专题

本地 stdio MCP 与浏览器工作台使用同一个 SQLite 文件，不启动公网监听。Python 3.9+、无额外运行依赖。

    python3 -m shilu.mcp --data-dir /your/private/workspace
    python3 -m shilu --port 8765 --data-dir /your/private/workspace

两条命令的 data-dir 必须一致。显式指定私人目录；不要将运行数据库提交到公开仓库。打包安装后也可运行 shilu-mcp。

客户端配置示意（路径由使用者替换）：

    {"mcpServers":{"shilu":{"command":"python3","args":["-m","shilu.mcp","--data-dir","/your/private/workspace"]}}}

先安装本包或设置客户端工作目录为仓库根目录。重新连接客户端后发现工具。

## 生产流程
1. get_module_context 读取完整写作 skill。
2. register_source 登记原始章节快照；list_sources/search_sources/get_source 检索和阅读。
3. create_curation(config, source_ids) 锁定来源版本和规则快照。
4. submit_curation(project_id, revision, blocks) 只写 Agent 候选，不覆盖人工稿。revision 为整数，冲突后重新读取，不能盲重试覆盖。
5. validate_curation(project_id, candidate=true) 检查候选；省略 candidate 则检查人工正文。
6. 人在浏览器打开同一项目，载入候选、保存人工正文、对照原稿、确认复核、导出。

MCP 没有代签复核、导出或发布工具。新候选不会改变已经审过的人工稿；采纳或修改人工稿会使复核失效。

来源输入：

    {"id":"example-talk","url":"https://example.org/talk/","title":"虚构分享","date":"2026-01-01","occasion":"虚构教学","sections":[{"anchor":"one","text":"先确认真实问题，再用实际反馈检验。"}]}

服务返回 version。original block 包含 id/type/text/source_id/anchor/source_version/citation；editorial 和 heading 仅含 id/type/text。同一 URL+锚点复用编号，从1按首次出现递增。出处由系统生成，不重复提交文末列表。

## 数据与检查边界
- source_versions 保存历史快照，source_heads 指向当前登记版本；更新来源能定位受影响段落，并阻止旧稿复核/导出。
- projects 同时保存来源快照、规则快照、候选历史、人工稿历史及复核。旧单场项目保持兼容。
- 原话匹配忽略空白，仍不证明语义保真；登记来源来自调用方，不是服务器联网核验。
- 来源或规则改变时先复核，按新快照创建新项目，旧项目保留。没有自动重写或迁移审批。
- 公开 JSON 只含展示正文与出处，不含未引用原文、规则或复核人。私人迁移包则包含原始材料。
- 本版没有多人权限、共享远程服务、网络抓取和语义向量检索。个人站抓取/生产模板/发布适配在外部项目维护。

## 旧 workshop 数据迁移
独立实现的只读数据迁移器，不复制旧仓库代码：

    python3 -m shilu.migrate_workshop --source-db /private/old/drafts.sqlite3 --data-dir /private/new --author "讲者"

保留原稿、候选和人工正文；旧复核只作内部历史标记，迁入后一律重新复核。相同记录重复导入不会重复创建。旧 Markdown 原样保留，但本版通用 HTML 仍按纯文本章节显示，不承诺还原 Markdown 富文本排版。只能关联整份原稿，不伪造逐段来源映射。超过本应用长度/段落限制的记录明确返回 not_imported；迁移前保留备份，核对报告后再切换。

## 个人规范 profile
服务和工作台进程设置 SHILU_PROFILE_PATH 指向同一份私有 UTF-8 Markdown。get_module_context 返回合并后的 text、version 和 profile_version；create_curation 将规则快照保存到项目，既有版本校验会阻止规则变化后沿用旧稿导出。未配置时仍使用通用规范；已配置但缺失或为空时明确失败，不静默降级。路径本身不向 Agent 返回。部署时把个人文件作为私有配置提供，不提交真实个人材料到通用仓库。

## 单场 Agent 候选

`get_module_context.recap` 提供单场 skill。`create_recap(config, transcript)` 保存原始逐字稿和规则快照；`get_project` 可接手；`submit_recap(project_id, revision, sections)` 只写候选，保留旧候选及人工稿；`validate_recap` 检查来源编号。sections 含 title、body、source_ids。创建后使用返回 revision，不猜测固定初始值。单场规则快照缺失或过期时，验证、生成、复核和导出均阻断；跨场稿另有来源变化阻断。

## 公开来源更新

`python3 -m shilu.sync_public --bundle /private/speaking-sources.json --data-dir /private/workspace` 事务同步公开快照。它只管理此前由该同步器登记的来源，移除时保留历史版本，其他手工来源不删除。变化会使引用旧版本的跨场稿待复核。模块上下文返回 public_sync，可检查最近同步时间、内容hash和受影响项目。

共享部署、人工审稿入口及备份见 [REMOTE-SSH.md](REMOTE-SSH.md)，审核后导出见 [RELEASE.md](RELEASE.md)。

`list_projects(offset=0, limit=20, include_archived=false)` 提供分页任务发现，不返回全文；历史任务用 include_archived=true 查找，仍可 get_project。显式 superseded_by 仅标记迁移关系，不删除旧稿或沿用旧审批。

个人单场规范可由 `SHILU_RECAP_PROFILE_PATH` 加载；模块上下文 recap 含 skill、version、profile_version，创建单场任务时持久保存。缺失或空配置会阻止创建任务。此配置与跨场 profile 独立，单场规则变化后保留历史复核记录，但禁止继续复核或沿用旧复核导出；恢复方式见下文。

### Single-event rule freshness

All newly created single-event projects, including workbench projects, retain the current generic skill and configured private profile snapshot. Review, export, and `validate_recap` reject a missing snapshot or a version different from the current rules. An unreadable configured profile also fails closed. Existing human text and review history are retained; rejection does not modify the project.

Legacy single-event projects without a snapshot cannot be grandfathered into approval. Read the current module context, create a new recap using the original transcript and configuration, submit a candidate under those rules, then adopt/save and complete human review again. Rule changes use the same recovery path. Do not replace the old snapshot or copy its review record to bypass this check. Cross-event review behavior is unchanged.
