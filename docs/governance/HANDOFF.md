# 项目交接兼容入口

版本 handoff-1.9，2026-10-19，北京时间。适用于本地和定向交接，不自动发布。

接手顺序：

1. 阅读 [产品说明](../PRODUCT.md)、[产品架构](../ARCHITECTURE.md)、[当前进展与卡点](../PROGRESS.md)。
2. 阅读 [文件制度](FILE_MANAGEMENT.md)和根目录 [AGENTS](../../AGENTS.md)，核对用户最新授权。
3. 查看本地 Git 分支、提交与改动，保护用户 Notebook 输出和实际运行证据。
4. 只处理当前指定任务；完成后更新主进展、相关产品/架构及版本清单，再停止。

本机工作区为 `F:\Codex\CS_YouOweMe`，本地分支 `planning/uu-research-reset`；冻结核心0.3.5保持原版，独立研究组件分别版本化。用户本轮已授权公开代码/文档的分支推送和迭代PR；接手时读取该分支的最新Git和主文档，main可能仍是旧基线。本地数据库/实验不随Git克隆取得，不自动合并或打release标签。

```powershell
git status --short
git branch --show-current
git log -5 --oneline
```

查看库需明确只读连接，不启动旧采集或恢复队列。凭证不展示/复制；原始响应、截图、库与冻结源码保持私有。旧完整交接可从 Git `babb125` 恢复，见 [清理记录](ORGANIZATION.md)。本页不重复维护阶段状态。
