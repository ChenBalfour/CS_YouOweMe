# 既有资产登记

登记日期：2026-10-12。此表只登记已有资产的已知位置与当前准入状态，**不是逐项审查完成报告**。本轮不重新查询市场数据库，不验证历史数据是否适合训练。

| 资产 | 位置 / 版本 | 状态 | 已知用途与问题 | 后续处理部分 |
| --- | --- | --- | --- | --- |
| 当前方向与制度 | PLAN、FILE_MANAGEMENT、STATE、AGENTS | current-plan | 当前工作的依据，不是模型或数据成果 | P01 |
| 旧采集与历史实现 | src、scripts，代码基线 v0.3.0 | legacy / unreviewed | 接口、分页和存储曾试跑；UU 新口径适配尚未审查 | P03 |
| 旧合成测试 | tests/ | legacy / unreviewed-for-new-scope | 可辅助机制回归；通过不证明真实交易有效性 | P03–P05 |
| 已公开快照样本 | data/samples/pilot_20261011/ | legacy / unreviewed | SteamDT 快照、挂牌、关联规格；不作 UU 正式训练集 | P04，P06 |
| 旧历史库与归档响应 | data/local/database/ | legacy / unreviewed | SteamDT 总览及平台代码；UU 成交身份与完整性未确认 | P03–P04 |
| 旧主力与候补名单 | data/local/universes/*.json、docs/research/UNIVERSE.md | legacy / unreviewed | 旧来源热度、旧权重和容量规则；不作为新正式名单 | P02 |
| 旧种子与观察名单 | config/seeds.json、config/watchlist.json | legacy / unreviewed | 流金王朝、燃料喷射器可作调查线索，不等于入选 | P02 |
| SQL 与 VS Code 工作区 | sql/、config/vscode.code-workspace | legacy / diagnostic | 旧库查询工具；不据此宣称新研究数据就绪 | P03–P04 |
| 接口与事件发现资料 | data/local/recon/、data/local/archive/ | legacy / reference | 契约、历史探测和原网页证据；具体用途待核验 | P03–P05 |
| 旧字段与使用文档 | docs/data/、docs/usage/ | legacy-documentation | 解释旧实现与来源，不覆盖当前主计划 | 对应部分 |
| 已有公开仓库及版本 | GitHub CS_YouOweMe，v0.1.0–v0.3.0 | already-public / frozen | 当前不新增发布，也不删除或改可见性 | P06 |
| 私有凭证 | config/.env 与既有私有归档配置 | private / protected | 只供相应授权操作读取；不记录值，不公开 | 持续保护 |

旧试采曾报告 44,502 个目录规格、119,520 条小时行情和 1,420 条成交。这里仅引用已有记录，不把数量当作质量验收，也不宣称所有这些资料无用。是否保留、适配、拒绝或删除，后续按明确用途逐项判断。

**当前正式资产计数**：新 UU 主力名单 0、已验收 UU 数据集 0、已验收交易模型 0。旧 11 个入选规格不计入正式名单，旧库不计入正式数据集。

后续每次资产处理补充：精确路径／ID、状态前后、审查用途、证据、限制、日期与修改记录。保持来源资料可追溯，禁止无记录把旧产物升级为 validated。
