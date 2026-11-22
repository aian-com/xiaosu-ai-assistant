# 历史阶段记录（非当前验收清单）

最新状态见 ../README.md，真实评测见 evaluation/README.md。下文保留早期记录。

# 当前实施状态

当前路线：FastAPI + React + 自动创建的 SQLite。本地存储取代 PostgreSQL/pgvector，不做加分项，不再要求用户安装数据库。

| 基础需求 | 当前实现 | 验证 |
|---|---|---|
| MD/TXT/PDF/DOCX 文档管理 | 解析、上传、列表、索引任务、更新、删除 | 自动化通过 MD/TXT/DOCX；PDF 解析待样例补测 |
| 增量一致性 | 内容摘要去重、活动版本切换、SQLite 短写事务 | 版本、删除、失败旧版保留测试通过 |
| RAG 与引用 | 真实 Embedding 语义向量、模型生成、引用签名定位 | 真实模型待配置 |
| 多轮、流式、拒答 | 统一对话、SSE、引用有效性检查 | Mock LLM 测试通过；真实模型待配置 |
| 模型自主工具 | JSON Schema 工具循环、独立内部 HTTP API、时间工具 | Mock LLM 测试通过；真实模型待配置 |
| 管理后台 | 文档、对话记录、模型设置、助手对话 | TypeScript 检查与 Vite 构建通过 |
| 本地启动 | 自动配置模板、SQLite 迁移、API/worker/前端 | 已启动，SQLite 迁移、API 和索引 worker 验证通过 |
| IM（必做） | 适配代码保留，可选依赖，默认不启动 | 未配置/未真实验证，不算已完成 |
| 工程与文档 | uv/pnpm、日志、迁移、脚本、真实 AI 记录 | 持续更新 |

真实问答需配置 LLM_*，知识检索另外需要 EMBEDDING_API_KEY、EMBEDDING_BASE_URL、EMBEDDING_MODEL。已移除本地哈希向量分支，未配置时明确失败。SQLite 保留，无外部数据库安装要求。

原题 IM 是基本要求而非加分项；当前先完成本地闭环，IM 后置但不能从最终验收中删除。

## 本轮实际结果

- 后端 10 条自动化测试通过，包括 Mock LLM、流式事件、工具回填、日志、用户会话键隔离、三格式索引、同名去重/替换、删除、引用失效、中文 MIME 文件名。
- 前端 TypeScript 与 Vite 构建通过。约 1MB 的主 JS 包有体积提示，不影响本地启动；暂不做加分型优化。
- scripts/setup.sh 通过，uv.lock 和 pnpm-lock.yaml 已生成并使用锁定安装。
- scripts/start.sh 已实际启动；5173 页面、8000 API、8001 Mock API 返回正常。
- scripts/test.sh --smoke 通过实际服务验证：中文员工手册上传、独立 worker 索引、重复上传去重、无模型时错误兜底和日志。
- 未执行真实模型或 IM 联调；未进行浏览器自动化交互验收。Starlette TestClient 有一条 httpx 弃用提示，测试仍通过。

## 当前切换结果（Embedding）

14 条后端测试与前端构建通过；新增批量顺序恢复、异常响应拒绝、缺配置禁止回退、旧向量排除与重建测试。真实 Embedding 凭据尚未填写，未运行真实向量生成或语义质量评测。前面的本地索引 smoke 记录属于切换前版本，不能当作当前模型联调结论。

服务已按 Embedding 版本重启，5173 页面正常，设置接口确认 Embedding 尚未配置；已有示例文档标记需要重建。旧的 8765 关键词体验服务已停止。开发启动改用统一进程管理，停止时清理子进程树。

旧方案清理：删除 local/server.py、local/index.html、local/README.md，移除使用说明中的旧体验入口。生产代码无哈希向量生成、关键词检索或模式切换分支；保留旧索引隔离回归用例。14 条后端测试再次通过。
