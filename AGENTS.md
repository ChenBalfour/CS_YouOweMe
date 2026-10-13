# 项目执行约束

先阅读 README.md、docs/research/PLAN.md、docs/governance/STATE.md 和 docs/governance/FILE_MANAGEMENT.md。用户最新明确指示优先；不要只依据旧进度或旧使用文档恢复采集。

- 一次对话只处理用户指定的一个 part，完成后停止。不要自动选品、采集、生成数据集、训练或发布下一部分。
- 用户在后续消息明确指定下一部分，即确定新的授权范围，不重复索取同一授权；正常实施选择在该部分内自行完成。
- 流金王朝对应 The Oligarch，Gold Arabesque 是黄金藤蔓，不能沿用旧 watchlist 的误映射。
- 当前目标执行场所为悠悠有品，研究板块为千百战普通枪皮。辅助平台观察不能直接当作 UU 执行数据。
- 旧名单、数据库、代码和公开样本是待审查历史试验；未经对应用途验收不得作为正式研究资产。
- 当前冻结新增 GitHub push、PR、远程合并及 release；本地分支和提交可记录工作。开源属于最后的 P06，不根据旧授权自动发布。
- 真实密钥只在本地忽略配置，公开模板保持空白；不得打印、复制到文档、日志、截图或提交中。
- 不无记录删除或移动旧数据。所有文件管理遵循 FILE_MANAGEMENT，资产状态遵循 ASSET_REGISTER。
- 当前部分的代码或文档修改同步必要的 STATE 和本地交接记录；检查与变更相适应，不为纯文档更新启动市场采集或模型实验。

- 当前目录 layout-1.0：代码与工程配套集中在 scripts/，数据在 data/，文档在 docs/；根目录工具元数据保留。P02 初选及 P03 两规格有限核验交付完成，L0 来源观察通过、L1/L2 执行准入未通过。当前停止点见 STATE，不自动扩大采集、重试受限 UU 主机或开始 P04/P05。
- SteamDT 逐笔代码 1 仅核验为 Steam 来源显示，0/2/3 为三方未知，不映射 UU；market-comparsion 的 UU 汇总报价及数量不是单件深度。交叉报价必须保留并标异常，不能形成套利或执行标签。
- 文件与目录用途、内容版本见 docs/governance/FILE_CATALOG.json；私有清单在 data/local/manifests/。修改后运行 python -B scripts/manage_assets.py --write，再 --check；离线测试入口为 scripts/tests。
