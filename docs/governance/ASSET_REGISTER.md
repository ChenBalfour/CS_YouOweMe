# 既有资产登记

登记版本 asset-register-1.8，2026-10-14。首批百元与属性可比性规则已修订；用户本地观察首轮成功后中断，24 小时稳定性未验收，当前仅准入 L0。

| 资产/位置 | 状态 | 用途与保留依据 | 后续部分 |
| --- | --- | --- | --- |
| UU_HISTORY_CHART、data/local/recon/user_uu_history_chart_20261014 | current / user-evidence-pending-verification | UU历史在售数量/成交价格与BUFF辅助入口可见；登录前提与频率待核验，截图私有，尚无图表响应 | P03 |
| docs/research/PLAN、governance/ 制度与状态 | current-plan | 当前方向、管理与停止点 | P01 |
| docs/research/PROGRESS_20261013 | current / progress-snapshot | 今晚收尾总结、早期改动与整体路线；后续状态以 STATE 为准 | 持续 |
| P03_VERIFICATION_PLAN、P03_VERIFICATION_REPORT、UU_FIELD_CONTRACT、UU_EXECUTION_RULES | current / P03-delivered | 范围预算、字段口径、规则时效、有限结果与执行缺口 | P03 |
| scripts/notebooks/uu_observe_24h.ipynb、observe_uu_24h.py、history/observe.py | current / user-first-round-checked | 用户本地显式运行、固定截止与恢复入口；首轮已保存，用户输出保留，24 小时未验收 | P03 |
| SELECTION_REVISION_20261014、SELECTION_PLAN 1.2 | current / selection-rule-revision | 首批 [100,1000) 元、同档属性可比性及通用求购匹配，7 个旧百元主力待复核 | P02–P03 |
| data/local/recon/user_attribute_scope_20261014 | private / user-evidence | 用户两张求购截图及哈希，拍摄时间未知；仅可见行证据，不公开买家信息 | P02–P03 |
| data/local/staging/steamdt/p03_steamdt_observe_20261014T101536+0800_4f3ccd | private / L0-first-round-checked | 用户运行后中断，2/48 样本成功、5 次请求成功；保留独立库、原始响应与恢复窗口 | P03 |
| P03_OBSERVATION_PLAN、usage/OBSERVE_24H | current / user-run-guide | 连续观察预算、启动停止恢复、Notebook 输出和真实验收限制 | P03 |
| verify_public_evidence、verify_uu_fields、review_uu_verification、history/verification | retained / bounded-verification | 只读证据、来源比较、离线核对和保守解析；不自动重试受限入口 | P03 |
| data/local/staging/steamdt/p03_steamdt_uu_20261013* | validated / L0-scope-only | 两规格小时表和已核对的来源混合逐笔；UU 执行用途未通过 | P03 |
| data/local/staging/steamdt/p03_steamdt_fields_* | validated / L0-scope-only | 来源 UU 汇总价格与数量；单件深度未核验、交叉报价标异常 | P03 |
| data/local/recon/p03_20261013_evidence | private / traceable | 15 份完整公开脚本/规则响应和 UU 429 状态；不是订单数据 | P03 |
| scripts/src、collect.py | legacy / unreviewed-market | 解析、精度、分页、恢复和存储机制可复用 | P03 |
| scripts/tests | legacy / offline-regression | 机制回归；通过不代表市场数据合格 | P03–P05 |
| scripts/check_secrets.py、hooks | retained / engineering | 本地凭证隔离检查，仍暂停远程发布 | 持续 |
| scripts/select_uu_research.py、SELECTION_REPORT | retained / P02-historical | 原有限选品调查和名单；未实现新属性门槛，不据旧脚本自动重选 | P02 |
| data/local/universes/uu_research_selection_20261012T235228+0800_v1_1_b74608 | validated / original-P03-scope-only | 原 10 主力、6 候补不覆盖；百元/属性新规则待复核，训练及买入用途未批准 | P03 |
| data/local/staging/steamdt/p02_*、scripts/local/selection_sources | candidate / private-traceable | 两个调查运行、48 请求、精确源码和原始证据，旧版本保留 | P02–P03 |
| scripts/pilot_uu_day.py | retained / engineering-pilot | 单品单日有预算试跑和离线核验，未完成完整爬虫验收 | P03 |
| data/local/staging/steamdt 单日试跑 | candidate / L0 | 24 个 UU 小时价格桶；量额有缺失、逐笔平台未确认，不用于训练 | P03 |
| docs/local/pilots、scripts/local/pilot_sources | private / traceable | 试跑质量报告与实际执行源码的准确内容版本 | 持续 |
| scripts/manage_assets.py、FILE_CATALOG | current-management | 每个文件及目录的版本、用途与完整性检查 | 持续 |
| scripts/config/seeds、watchlist | legacy / research-clue | 旧精确种子及用户举例线索，非正式名单 | P02 |
| scripts/sql、config/vscode.code-workspace | legacy / diagnostic | 旧库只读诊断参考 | P03–P04 |
| data/local/database、raw | legacy / unreviewed | 旧行情、成交与来源证据；保留原路径与内容 | P03–P04 |
| data/local/universes 根层旧 JSON | legacy / unreviewed | 旧候选快照，不沿用旧数量或权重；新版本目录按其明确批准用途管理 | P02 |
| data/local/recon、archive、api_cache | legacy / reference | 接口、事件、初始采集与目录证据；已去除两份相同副本 | P03–P05 |
| data/samples/pilot_20261011 | already-public / frozen | 旧匿名快照与离线解析样本，非 UU 正式训练集 | P04、P06 |
| docs/data、usage、research/UNIVERSE、releases | legacy / documentation | 字段、接口限制、历史方法与公开版本追溯 | 对应部分 |
| docs/local/progress、data/local/progress | private / historical | 当前文字交接和冻结 JSON 历史；不能自动恢复旧任务 | 持续 |
| data/local/manifests | private / current-management | 整理前基线、迁移删除明细与私有版本清单 | 持续 |
| scripts/config/.env、旧归档凭证 | private / protected | 仅供授权操作，未展示、转发或加入 Git | 持续 |
| GitHub v0.1–v0.3 | already-public / frozen | 既有事实；未变更远程历史或可见性 | P06 |

本次 11 项删除均列入私有 layout-1.0-changes.json，说明依据、哈希与 Git blob 或保留副本。重复 DESIGN/ROADMAP 索引由 PLAN/STATE 取代；旧单文件代码、旧测试及 VERSION 已有完全一致的 Git 历史，无需保留第二份。文件内容版本和各子目录说明详见 FILE_CATALOG 与私有清单。

旧记录曾报告 44,502 个目录规格、119,520 条小时行情、1,420 条成交；本次未查询旧库重新验证。原验证名单 **10**、候补 **6**，当前百元待复核主力线索 **7**，新版名单未冻结；已验收正式数据集与模型仍为 **0**。
