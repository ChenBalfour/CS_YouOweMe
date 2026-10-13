# VS Code：24 小时 UU 来源报价观察

版本 observe-usage-1.0；2026-10-13，北京时间。对应 [notebook](../../scripts/notebooks/uu_observe_24h.ipynb)，用于 P03 连续采集工程验收。当前交付准备了运行入口，尚未替用户执行一天的采集。

## 观察范围

| 规格 | 精确英文名称 | 本轮用途 |
| --- | --- | --- |
| AK-47 流金王朝，久经沙场 | AK-47 \| The Oligarch (Field-Tested) | 百元规格来源价格与汇总报价观察 |
| M4A1-S 印花集，崭新出厂 | M4A1-S \| Printstream (Factory New) | 千元规格观察及交叉报价记录 |

使用 SteamDT 公开只读接口的明确 UU 行，采集当前 ITEM 商品报价和 market-comparsion 汇总报价、数量及更新时间。默认运行 24 小时、每 60 分钟采一轮，共 24 个采样时点，从创建时到第 23 小时，随后等待第 24 小时截止；截止时不再采样。数据保存在独立的私有 SQLite 与压缩原始响应中，运行数据目录存储停止预算 64 MiB。起止时刻在创建时固定；恢复旧运行不会重新计满一天。

64 MiB 是软停止预算，计算 SQLite、raw、清单和报告；最后一个响应或数据库记账可能略超后才停止，单次响应另有 2 MiB 限制。精确运行源码另存于私有 `scripts/local/pilot_sources/<运行 ID>/`，不计入这 64 MiB。预算用于控制有限试跑，不能当作预计实际占用量或硬性磁盘配额。

当前只有 **L0 来源观察**资格：记录每小时采样快照之间的变化。本轮不抓历史 K 线；汇总数量不是单件盘口深度。求购高于在售必须保留并标异常，不据差值判断套利。未采集已受限的 UU 直接接口、账户订单、真实成交或结算数据。范围和未知项见 [字段契约](../data/UU_FIELD_CONTRACT.md)。

## 首次运行

1. 用 VS Code 打开 `F:\Codex\CS_YouOweMe` 文件夹，打开 `scripts/notebooks/uu_observe_24h.ipynb`。
2. 安装或启用 Microsoft 的 **Python** 与 **Jupyter** 扩展，右上角 **Select Kernel** 选择本机 Python 3.11 或以上。若选定环境没有 kernel，按提示安装 `ipykernel`；本项目采集代码只用标准库，不需要安装 pandas 或数据库服务器。VS Code 的 Python notebook kernel 只需要该环境中的 IPyKernel。[官方 kernel 说明](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management)
3. 运行“加载项目与 Python 环境”单元，核对输出的项目与解释器路径。这个单元不请求市场接口。
4. 在配置单元把 `START_NEW_RUN = False` 改为 `True`，保留默认的 24 小时、60 分钟、64 MiB，再运行配置单元。
5. 运行“创建一次运行，或恢复原运行”，记下打印的 `run_dir`。**把配置单元中的 `START_NEW_RUN` 改回 `False`，保存 notebook**，避免下次重启误创建新运行。
6. 运行“连续采集”单元，第一轮后确认有进度输出。此单元会保持运行，到原定截止时间或提前停止条件出现时返回；无需守着逐轮操作。
7. 完成或中断后运行“查看报告”，核对摘要并保留运行目录。数据独立保存，关闭 notebook 后不靠单元输出恢复。

仅打开 notebook 或执行预检查不会开始市场采集。逐个运行单元便于核对配置；不要在未确认新建/恢复选择时直接点击 Run All。

## 电脑与停止、恢复

这次是**前台 kernel 任务**。运行期间电脑应保持联网、接电和唤醒，保留 VS Code 及 kernel；可以关闭屏幕。睡眠、关机、退出 VS Code 或 kernel 崩溃都会打断执行。请自行在 Windows 电源设置中避免本轮运行期间睡眠；程序不会修改系统电源选项，也不是后台服务。

主动停止时，点击 notebook 顶部工具栏的 **Interrupt Kernel（中断内核）**，等单元停止后查看报告。VS Code 官方支持从 notebook 工具栏中断或重启 kernel。[官方 notebook 说明](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)

若只是正常中断且 kernel 还在，可重跑采集单元继续原运行。若 kernel 已重启，依次运行加载、配置、恢复与采集单元，保持 `START_NEW_RUN=False`。恢复指针在私有 `data/local/manifests/uu_observe_last_run.json`，不要手动把它改成别的项目路径；需要核对哪个运行被选择时，查看恢复单元输出。

恢复跳过已错过的采样时点，继续剩余窗口，超过原截止时间只查看报告，不延长该运行。睡眠或停机期间没有取得的历史汇总快照无法补回，必须在报告中保留缺口。不要同时用两个 notebook、kernel 或终端进程写同一运行；如果采集代码版本已经改变，旧运行会拒绝恢复，先核对原运行记录。

HTTP 401、403、429 或认证/风控阻止会记录停止状态，恢复同一运行不会自动重试受限入口。不要用创建新运行来绕过限制；已有数据仍可只读查看，后续依据正常可访问条件另行核验。

## 数据位置与终端入口

创建单元打印的 `run_dir` 为准确位置，默认位于 `data/local/staging/steamdt/p03_steamdt_observe_<时间>_<标识>/`。各文件职责如下：

| 文件 | 内容 |
| --- | --- |
| observations.sqlite | 结构化来源快照、采样与请求状态 |
| raw/*.json.gz | 按哈希保留的压缩原始响应 |
| manifest.json | 本次固定窗口、预算、规格、代码与来源版本 |
| reports/summary.json、summary.md | 采集摘要和可读验收报告 |
| tables/source_snapshots.csv | 查看用的快照导出，SQLite 为主要存储 |

若后续希望在 VS Code 终端运行相同采集器，可从项目根目录使用下面入口；终端任务也需要电脑保持唤醒，且不能和 notebook 同时运行同一任务。

```powershell
python -B scripts/observe_uu_24h.py --new
python -B scripts/observe_uu_24h.py --resume "实际运行目录的绝对路径"
python -B scripts/observe_uu_24h.py --status "实际运行目录的绝对路径"
```

三行是替代选择，不应顺序一起执行。`--new` 创建后立即前台采集，`--resume` 继续指定运行，`--status` 只读查看；替换后两行的路径再使用。

## 一天后如何判断

先检查运行是否自然结束，或因访问限制、预算、断网和中断提前结束。再核对成功轮次、错过时点、更新时间、重复/过期快照、交叉报价和磁盘使用。金额与缺失沿字段契约保留；null 不填零，原始异常价格不覆盖。

`quality_flags` 对应比较接口在售/求购快照，`item_quote_quality_flags` 单独标记 ITEM 报价的时效和缺失。CSV 同时保留两类更新时间、运行 ID 和请求编号，不能将来自两个请求的价格当作同一时刻的报价。成功记录仅指解析和保存成功，即使过期或交叉报价也保留记录并标记；实际市场变化仍需结合更新时间解释。

这一天主要回答“能否按小时稳定保存来源观察”。每小时快照能比较相邻观察价格，无法还原采样之间的高低价、分钟跳价、挂单与撤单；来源若未更新，重复快照也不能当作市场没有波动。一天稳定运行不足以证明真实成交覆盖、可执行净收益或长期预测能力。验收后再决定是否扩到其余主力，当前不自动开始 P04 正式数据集。

将打印的运行目录及报告摘要交给下一轮复核即可。原始市场响应继续保持私有，notebook 准备进入 Git 时应清空执行输出；脚本、notebook 与说明文件的内容版本由项目文件清单维护。

相关：[P03 前置核验报告](../research/P03_VERIFICATION_REPORT.md)、[执行规则与访问限制](../data/UU_EXECUTION_RULES.md)、[当前状态](../governance/STATE.md)。
