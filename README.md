# CS_YouOweMe

面向**悠悠有品（UU）**的 CS2 千百战枪皮决策研究。以 UU 为目标交易场所，以 SteamDT、BUFF、Steam 等平台作为辅助信息来源，研究实际交易时间、成本和退出能力约束下的购买判断。

当前完成 **P01：研究方向、完整计划与文件管理制度**。后续按“选热门皮肤 → 对应爬虫 → 数据集 → 因子与模型 → 审查后开源”逐步推进，一次对话完成一个部分。

## 当前入口

- [项目交接文档](docs/governance/HANDOFF.md)：供后续负责人和 agent 接手，含本地／远程差异、旧资产及接手提示。

- [完整主计划](docs/research/PLAN.md)：目标、执行机制、标签、因子、验证与六部分顺序。
- [文件管理规范](docs/governance/FILE_MANAGEMENT.md)：位置、命名、版本、资产准入和发布制度。
- [阶段状态](docs/governance/STATE.md)：完成项与当前停止点。
- [既有资产登记](docs/governance/ASSET_REGISTER.md)：旧代码、名单、数据和公开内容的待审查状态。

## 既有工作如何处理

v0.1–v0.3 属于早期技术试验。保留代码、试采、来源证据和版本记录供后续审查；旧 11 个规格不视作新正式主力名单，旧 SteamDT 库不视作已验收的 UU 训练集。当前没有正式 UU 数据集或通过验收的交易模型。

本阶段不运行旧采集入口，不启动训练，也不新增 GitHub 推送、PR 或 release。已经公开的内容仍是既有事实，最终 P06 再按明确允许清单筛选和调整；本轮不改远程仓库可见性或删除历史。

## 文件位置

```text
src/cs_youoweme/     现有实现；后续按职责审查和适配
scripts/            命令入口与维护检查
config/             配置、空白模板及忽略的私有配置
sql/                旧库诊断查询
docs/
├── research/       唯一主计划及研究索引
├── governance/     文件管理、状态与资产登记
├── data/           旧来源和字段说明
├── usage/          旧实现使用说明
└── releases/       既有发布历史
data/
├── local/          私有原始资料、旧库及后续运行产物
└── samples/        冻结待审查的已公开早期样本
tests/              现有合成与离线验证
```

不要将真实值填入 `config/.env.example`。密钥仅留在忽略的本地配置或环境变量；数据库、完整响应和模型产物也留在私有目录。

原有 [数据库使用说明](docs/usage/DATABASE.md)、[历史采集说明](docs/usage/HISTORY.md)与[字段口径](docs/data/HISTORY_SCHEMA.md)仅说明旧试验，不能替代当前计划或授权后续执行。

原创代码与文档采用 [MIT](LICENSE)。第三方数据及商标权利归各自权利人。
