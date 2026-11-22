# 本地架构与流程

## 架构

React :5173 → FastAPI :8000 → 模型工具循环 → 知识检索 / Mock API :8001 / 时间工具。

数据全部存放 data/xiaosu.sqlite3，文件位于 data/uploads，日志位于 logs/。SQLite 来自 Python 标准库，不安装数据库服务。SQLAlchemy 管理数据，Alembic 自动迁移。

## 文档处理

上传 → 校验格式大小 → SHA-256 内容摘要 → SQLite BEGIN IMMEDIATE 短事务 → 同名去重或新版本 → 持久化索引任务 → worker 解析 MD/TXT/PDF/DOCX → Embedding 模型生成语义向量 → 再检查最新版本/删除标记 → 原子切换活动版本。

失败保留旧版；删除后检索过滤，旧引用返回 410。版本更新后旧引用失效。索引进程启动恢复未完成任务；文件锁避免重复 worker。文件物理清理后置，当前为逻辑删除。

## 检索

文档分段后批量请求 Embedding API，语义向量存放 SQLite JSON 列。问题使用同一模型向量化，在应用内对活动版本计算余弦相似度。按接口基础地址和模型名标识索引，防止旧哈希向量或不同模型向量混用；维度异常会拒绝处理。

无 Embedding 配置时明确失败，不降级到哈希或关键词向量。接口响应需满足数量、索引顺序、有限数值、非零和一致维度要求。旧索引在后台标为需要重建，重建创建新版本，成功后原子切换。

初始相似度阈值 0.45 待真实语义评测校准；测试里的确定性向量仅为隔离外部依赖的 Mock，不在产品路径中使用。

## 问答

会话按平台、组织、会话和用户隔离；文件锁跨进程串行化同会话；数据库不在远程模型请求期间持有写锁。模型通过 tool calling 自主选择工具，参数由 Pydantic 校验。

流式事件 status/tool/delta/done/error；delta 是生成草稿，done 是引用校验后结果。该策略不保证草稿绝无幻觉，最终有效引用和无证据拒答须通过评测检验。

## 界面及配置

默认口令来自 .env.example 的本地开发示例，服务只监听 loopback。管理员 API 使用 Bearer 认证，引用页使用限时签名。上传、设置和日志均通过主后端。

## 钉钉接入

钉钉适配器接收并落库，独立 worker 调用相同对话服务后发送 Markdown。已支持 AI 卡片流式更新，失败回退普通消息；当前环境效果经用户确认。平台已收消息但本地未标记成功时崩溃可能重复回复，不能承诺跨平台 exactly-once。

SDK 参考：[钉钉官方示例](https://open-dingtalk.github.io/developerpedia/docs/explore/tutorials/stream/bot/python/send-markdown/) 与 [官方 Python SDK](https://github.com/open-dingtalk/dingtalk-stream-sdk-python)。
