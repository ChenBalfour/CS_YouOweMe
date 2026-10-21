"""Generate or verify file/folder version catalogs without running collectors."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = "layout-1.0"
PUBLIC = "docs/governance/FILE_CATALOG.json"
PRIVATE = "data/local/manifests/workspace-layout-1.0.json"
INDEX = "docs/governance/FILE_INDEX.md"
CATALOGS = {PUBLIC, PRIVATE, INDEX}

PURPOSES = {
    "scripts/train_seven_models.py": "七品训练准备、显式拟合和仅重载评估的薄CLI，默认不自动启动训练",
    "scripts/config/seven_training_spec.json": "七品研究训练1.0固定模型、预算、标签和验证选择规范",
    "scripts/notebooks/seven_model_training.ipynb": "保留用户原1.0训练入口及既有运行；修复后推荐seven_model_training_v1_1.ipynb",
    "scripts/notebooks/seven_model_training_v1_1.ipynb": "修复版1.1：默认CUDA float32、独立v2预处理/新实验ID，保留旧用户Notebook和参数",
    "scripts/research/data/training_data.py": "冻结七品/父清洗哈希与只读验证、过去672h序列和预测字段白名单",
    "scripts/research/data/model_preprocessing.py": "只在训练段拟合的中位数/mask/缩放与商品编码JSON",
    "scripts/research/models/classical.py": "持平、Ridge、有界ARIMA及LightGBM CPU适配与保存/无拟合重载",
    "scripts/research/models/neural.py": "四种小神经网络、CUDA全精度/显式AMP、早停、最佳state_dict与无拟合重载",
    "scripts/research/models/foundation.py": "仅本地权重的可选Chronos-2零样本适配；无自动下载，真实权重待验",
    "scripts/research/evaluation/seven_training.py": "七品不可变预处理/实验、验证选型、仅重载评分和图表",
    "scripts/tests/test_training_data.py": "冻结输入、train-only缩放、mask、未知品和因果序列合成测试",
    "scripts/tests/test_classical_models.py": "CPU四模型保存重载、无fit推断、purge与篡改合成测试",
    "scripts/tests/test_neural_models.py": "神经网络和本地基础模型stub的保存、早停与隔离合成测试",
    "scripts/tests/test_seven_training.py": "七品训练入口的合成端到端、默认安全边界和仅重载评估检查",
    "docs/usage/SEVEN_MODEL_TRAINING.md": "七品训练评估Notebook操作、CPU/CUDA、参数存储与结果解释",
    "README.md": "项目入口、当前状态与三类目录索引",
    "AGENTS.md": "协作者的执行、阶段、凭证及发布约束",
    "LICENSE": "原创代码与文档的 MIT 授权",
    "pyproject.toml": "Python 打包配置及单一源码版本入口",
    ".gitignore": "私有数据、文档、凭证与生成缓存的 Git 排除规则",
    ".gitattributes": "跨平台文本换行规则",
    ".github/workflows/ci.yml": "既有远程离线检查工作流，根目录位置由 GitHub 约定",
    "scripts/README.md": "代码、配置、测试、SQL 和检查入口说明",
    "scripts/collect.py": "旧采集 CLI 的薄入口，当前不恢复采集",
    "scripts/check_secrets.py": "暂存区及 Git 历史的凭证隔离检查，不打印真实值",
    "scripts/manage_assets.py": "生成及校验逐文件、逐目录版本和用途清单",
    "scripts/pilot_uu_day.py": "单品单日 YOUPIN 小时行情与混合成交的独立有限试跑、离线核验及导出",
    "scripts/select_uu_research.py": "有预算的 P02 候选调查、正确商品身份补查和版本化验证名单选择",
    "scripts/steamdt_research.py": "SteamDT显式悠悠小时研究库：商品登记、有限回补、分页续采、增量复核、修订追溯及报告，独立组件1.0",
    "scripts/build_research_samples.py": "日级样本构建的兼容CLI/API薄入口，实际实现委托research/data；不联网或训练",
    "scripts/evaluate_research_baselines.py": "离线固定规则基准评估薄入口：验证集选规则、锁定测试和七日来源参考预测，不执行交易",
    "scripts/clean_steamdt_data.py": "七品小时清洗CLI/API薄入口，只读来源、缺失感知网格、事件标记与独立SQLite版本，不训练",
    "scripts/build_seven_samples.py": "七品特征/标签薄CLI与Notebook API：显式父清洗ID、离线新建版本和只读status，不训练",
    "scripts/research/data/seven_samples.py": "seven-daily-samples-1.0：过去21特征、独立七日点/路径标签、同日跨品与时间隔离、不可变产物",
    "scripts/config/seven_daily_spec.json": "七品日级输入/点目标/路径风险、缺失门槛、共同日期分组及七日purge的冻结1.0规范",
    "scripts/notebooks/seven_daily_samples.ipynb": "VS Code七品特征/标签检查，默认只读既有结果；显式开关才新建版本，交付空输出",
    "docs/data/SEVEN_DAILY_SAMPLES.md": "七品21输入特征、独立点/路径标签、样本资格、版本与Notebook操作说明",
    "scripts/config/steamdt_cleaning_spec.json": "七品清洗的缺失、价格/量额校验、因果波动诊断与输入质量门槛固定规范",
    "scripts/notebooks/steamdt_cleaning.ipynb": "VS Code七品清洗与质量检查入口，默认只读已有结果；显式开关新建版本，不采集或训练",
    "docs/data/STEAMDT_CLEANING.md": "七品清洗SQLite表、mask/缺失/极端事件与Notebook使用及特征工程边界",
    "docs/research/DATA_METHODS_20261019.md": "2025至2026年一手论文与官方实现调研：缺失感知、异常、特征和概率预测的采用理由与候选对照",
    "scripts/config/cyrex_baseline_spec.json": "评分前固定的基准规则、验证选择准则、测试与研究边界，不按测试结果调参",
    "scripts/notebooks/cyrex_forecast_dashboard.ipynb": "VS Code离线预测评估与可视化入口，默认读取已有结果，显式开关才新建评估版本",
    "docs/usage/FORECAST_DASHBOARD.md": "预测图表Notebook、固定基准、评价指标、保存位置与成本/执行边界说明",
    "scripts/config/cyrex_daily_spec.json": "次时代日级研究的决策时间、输入窗口、目标、特征、时间划分与研究限制固定规范",
    "scripts/notebooks/cyrex_daily_samples.ipynb": "VS Code离线日级样本构建与检查入口，默认不构建、交付空输出；不联网或训练",
    "docs/data/CYREX_DAILY_SAMPLES.md": "次时代日级候选字段、28天序列、七日价格目标、缺失/隔离规则和Notebook操作说明",
    "scripts/config/steamdt_research_items.json": "七个普通百元候选的精确名称、SteamDT编号与历史起点种子；新工作区复制后另行维护",
    "scripts/notebooks/steamdt_research.ipynb": "VS Code有限采集入口：商品清单、默认关闭联网、手动续采与本地报告；交付空输出",
    "scripts/verify_public_evidence.py": "有预算的公开网页/规则证据和已发现 UU 只读入口抓取，访问受限主机持久停止",
    "scripts/verify_uu_fields.py": "两个精确规格的 SteamDT UU 汇总盘口字段有限补查，独立库与准确源码留存",
    "scripts/review_uu_verification.py": "离线核对 P03 原始哈希、全页逐笔、只读库与字段准入，导出私有规范观察",
    "scripts/review_uu_chart.py": "离线核验用户导出的 UU 图表响应，按请求指标分离价格和数量，保存独立 SQLite/CSV 与真实时间间隔",
    "scripts/collect_uu_charts.js": "用户正常登录UU页面的有限历史批次采集，价格四窗口/数量三窗口、内存会话、限流停止与下载检查点；真实稳定性待验收",
    "scripts/collect_uu_direct.py": "用户本地纯HTTP单请求试采与有限队列继续；私有认证配置、串行间隔、全局配额、继承访问停止及独立SQLite/CSV，真实直连待验收",
    "scripts/import_uu_chart_batch.py": "用户浏览器下载批次的纯离线校验与独立SQLite/CSV入库，保留窗口、状态和历史可得时间未知",
    "scripts/notebooks/uu_history_collect.ipynb": "用户本地历史采集指引、选择下载批次、离线入库与覆盖检查；无训练代码、交付空输出",
    "scripts/observe_uu_24h.py": "用户显式启动的新建/恢复连续观察 CLI，status 只读，不默认运行",
    "scripts/notebooks/uu_observe_24h.ipynb": "VS Code 用户本地 24 小时连续观察 Notebook，交付时输出清空且未执行",
    "scripts/config/seeds.json": "旧试采精确英文规格种子，不是正式 UU 名单",
    "scripts/config/watchlist.json": "流金王朝、燃料喷射器等旧调查线索",
    "scripts/config/.env.example": "公开的空白凭证配置模板",
    "scripts/config/uu_direct_auth.example.json": "UU纯脚本入口的公开空白认证字段模板，不含真实凭证",
    "scripts/config/uu_direct_items.example.json": "UU纯脚本单品有限试采的模板和窗口参数样例，44828身份尚未核验",
    "scripts/config/vscode.code-workspace": "旧库可选 SQLTools 工作区配置",
    "scripts/hooks/pre-commit": "本地提交前的暂存凭证检查",
    "scripts/hooks/pre-push": "推送前历史凭证检查；本轮公开分支迭代已获授权",
    "docs/README.md": "三大主文档与专项字段、运行、管理附件索引",
    "docs/PRODUCT.md": "产品主文档：目标、范围、用户流程、策略、建议输出和验收要求",
    "docs/ARCHITECTURE.md": "架构主文档：真实实现、数据流、存储恢复与待建模型和执行层",
    "docs/PROGRESS.md": "进展主文档：每次操作成果、验证、实际运行、当前卡点和下一步",
    "data/README.md": "私有数据与已公开冻结样本的生命周期说明",
    "docs/research/PLAN.md": "旧研究计划路径的兼容入口，当前方案统一到三大主文档",
    "docs/research/SELECTION_PLAN.md": "P02 选品计划、事先固定的范围预算及身份纠正修订依据",
    "docs/research/SELECTION_REVISION_20261014.md": "首批百元范围、用户求购截图的属性条件证据与待核验候选及复核顺序",
    "docs/research/SELECTION_REPORT.md": "P02 主力、候补、排除与观察结果、来源快照和未知项",
    "docs/research/P03_VERIFICATION_PLAN.md": "P03 两规格来源、盘口、属性与规则核验范围、预算和验收问题",
    "docs/research/P03_VERIFICATION_REPORT.md": "P03 有限试跑结果、证据、报价异常、未知项和 L0 准入边界",
    "docs/research/P03_OBSERVATION_PLAN.md": "用户本地连续观察的固定窗口、预算、恢复、用途与未启动状态",
    "docs/usage/OBSERVE_24H.md": "VS Code Notebook 的内核、启动、停止、恢复、输出和采样边界说明",
    "docs/usage/STEAMDT_RESEARCH.md": "SteamDT本地小时研究库、商品清单扩展、分页恢复、去重修订、请求预算、跨周期与日常更新说明",
    "docs/usage/UU_CHART_EXPORT.md": "Edge 复制图表响应正文及用户本地离线核验命令，不复制请求头或启动采集",
    "docs/usage/UU_HISTORY_COLLECT.md": "用户登录页面历史采集、下载入库、恢复限制、当前报价用途与UU/SteamDT结合方案",
    "docs/usage/UU_BROWSER_AUTOMATION.md": "待实现的专用Edge商品队列、页面自动操作与保存入库方案，明确登录边界和分阶段真实验收",
    "docs/usage/UU_DIRECT_COLLECT.md": "本地纯脚本凭证配置、单请求试采、间隔配额、停止恢复和独立输出说明；不保证Cookie单独可用",
    "docs/data/UU_FIELD_CONTRACT.md": "已核验 UU 来源行情、汇总快照及混合逐笔字段定义与执行准入限制",
    "docs/data/UU_HISTORY_CHART.md": "UU 历史图表指标映射、两份用户响应的字段与实际间隔核验、统计及决策时间边界",
    "docs/data/SOURCE_ALIGNMENT_PLAN.md": "SteamDT研究主序列与UU供给/执行补充方案，分字段聚合、过去值对齐、可得时间及登录与换品规则；尚未构建特征或训练",
    "docs/data/UU_EXECUTION_RULES.md": "Steam 和 UU 公开规则、旧版适用限制、资金时间字段及访问限制处理",
    "docs/governance/STATE.md": "旧状态路径的兼容入口，当前进展统一到 PROGRESS",
    "docs/governance/HANDOFF.md": "精简交接入口：三大主文档、接手顺序与版本保护",
    "docs/governance/FILE_MANAGEMENT.md": "文件布局、资产生命周期、版本、迁移及发布制度",
    "docs/governance/ASSET_REGISTER.md": "旧资产保留依据及按用途准入状态",
    "docs/governance/ORGANIZATION.md": "layout-1.0 整理结果、迁移、清理及恢复方法",
    "docs/governance/CONTRIBUTING.md": "本地工程修改与检查方法",
    "docs/governance/SECURITY.md": "凭证隔离与安全问题处理说明",
    PUBLIC: "公开文件及目录的用途、版本和内容哈希索引",
    INDEX: "逐文件与逐目录用途和内容版本的可读索引，由 manage_assets 生成",
    "docs/data/DATA_DICTIONARY.md": "旧公开快照表的字段字典",
    "docs/data/DATA_SOURCES.md": "旧来源、采集证据及口径限制",
    "docs/data/HISTORY_SCHEMA.md": "旧历史库 schema v2、时间与字段口径",
    "docs/usage/COLLECTION.md": "旧采集器的接口、配置和输出说明",
    "docs/usage/HISTORY.md": "旧目录、候选、历史任务及查询命令参考",
    "docs/usage/DATABASE.md": "旧库的可选查询、时间精度与备份方法",
    "docs/releases/WORK_LOG_20261014_20261019.md": "10月14至19日既往操作记录的冻结归档，不维护当前路线",
    "docs/releases/CHANGELOG.md": "代码历史变更及未打发布标签的迭代说明",
}

SOURCE_PURPOSES = {
    "__init__.py": "模块身份及包版本或职责说明",
    "__main__.py": "Python 模块形式的 CLI 入口",
    "cleaning.py": "规格、价格、数量、币种与时间标准化",
    "cli.py": "命令注册、参数与工作流调度",
    "config.py": "旧种子与受保护本地凭证读取",
    "errors.py": "安全可展示的采集异常类型",
    "parsing.py": "Nuxt 响应解析及精确商品匹配",
    "paths.py": "独立于工作目录的项目、配置与数据路径",
    "storage.py": "原始证据、快照表、报告与本地 SQLite 存储",
    "transport.py": "HTTP 传输及凭证重定向限制",
    "official.py": "旧官方 API 客户端、缓存与配额节奏",
    "public.py": "旧公开页面采集流程",
    "website.py": "旧匿名网页接口客户端、时钟同步与访问停止",
    "aggregate.py": "行情聚合，保留缺失和覆盖语义",
    "catalog.py": "目录身份、来源平台编号及搜索映射",
    "jobs.py": "有预算的分页任务、恢复与原子检查点",
    "normalize.py": "逐笔及行情精度、时间和空值验证",
    "query.py": "旧库覆盖、状态、参数化查询和导出",
    "store.py": "旧库 schema、事务、压缩归档和 worker 锁",
    "universe.py": "旧候选筛选实现，仅机制参考，不沿用为新选品规则",
    "verification.py": "核验后来源平台分类、可空 Decimal 属性和 UU 汇总报价异常及执行准入标记",
    "observe.py": "固定截止、逐时点检查点、预算、访问停止和只读状态的用户本地前向观察机制",
    "schema.sql": "旧历史库表、索引与任务结构 schema v2",
}

FOLDERS = {
    "data/local/artifacts/seven_training": "七品训练私有预处理与模型实验；版本不可覆盖，模型参数不上传",
    "data/local/artifacts/seven_training/prepared": "训练段拟合预处理参数、固定协议、父数据哈希与准确源码",
    "data/local/artifacts/seven_training/experiments": "各轮模型参数、环境、训练历史、验证选择和完整哈希",
    "data/local/reports/seven_training": "七品仅重载评估的逐行预测、误差、PNG及本轮工程验证证据",
    ".": "项目根及 Git/Python 所需入口元数据",
    ".github": "GitHub 工具约定的根目录配置",
    ".github/workflows": "既有自动检查配置",
    "scripts": "所有可执行代码及其工程配套",
    "scripts/research": "当前离线研究包，按数据、模型、评估、可视化分工；独立于冻结采集核心",
    "scripts/research/data": "冻结来源快照、七品清洗、缺失感知质量与日级样本/标签",
    "scripts/research/models": "固定价格预测基准及以后经批准的模型实现",
    "scripts/research/evaluation": "候选校验、验证集选择、锁定测试、成本情景和不可变评估产物",
    "scripts/research/visualization": "历史、测试期真实/预测价格及七日路径图表，不联网或训练",
    "scripts/src": "Python 包源码",
    "scripts/src/cs_youoweme": "旧技术实现，可按对应用途审查复用",
    "scripts/src/cs_youoweme/collectors": "旧公开页面、官方和匿名接口采集机制",
    "scripts/src/cs_youoweme/history": "旧目录、分页任务、SQLite、查询和候选机制",
    "scripts/tests": "离线与合成回归测试",
    "scripts/notebooks": "用户手动运行的 Notebook 入口，Git 中清空执行输出",
    "scripts/sql": "旧历史库只读诊断查询",
    "scripts/config": "脚本配置、空白模板与受保护本地凭证",
    "scripts/hooks": "本地 Git 凭证检查 hooks",
    "scripts/local": "私有的实际运行源码快照，不加入 Git",
    "scripts/local/pilot_sources": "按试跑保存准确采集和核验源码，匹配 manifest 哈希",
    "scripts/local/selection_sources": "按调查运行保存准确选品采集源码，匹配 manifest 哈希",
    "data": "来源数据及其伴随元数据",
    "data/samples": "已公开、冻结待复审的旧匿名样本",
    "data/local": "私有历史证据与本地运行产物，不加入 Git",
    "data/local/manifests": "私有文件清单、整理前基线及逐项迁移删除记录",
    "data/local/artifacts": "离线研究实验和评估的独立版本，不存原始市场凭证",
    "data/local/artifacts/baseline_evaluations": "固定基准的不可变评估、规则选择、预测表、准确源码与哈希清单",
    "data/local/reports": "由冻结研究产物生成的可复核报告与图表",
    "data/local/reports/baseline_charts": "每次评估的图表输出、绘图配置及独立版本清单",
    "data/local/reports/cleaning_reviews": "清洗冻结产物的只读独立复核、Notebook默认行为检查与数据保留证据",
    "data/local/datasets": "按明确用途冻结的研究数据版本；不自动批准正式训练或交易",
    "data/local/datasets/steamdt_clean": "七品小时清洗研究版：全部来源修订、规则网格、缺失/事件标记、质量报告及准确代码规范",
    "data/local/datasets/seven_daily": "从明确清洗版派生的七品日级特征/标签候选；按用途冻结，不自动批准训练",
    "data/local/reports/seven_samples": "七品样本真实值独立重算、旧资产保留和Notebook默认只读验收",
    "data/local/database": "旧 SteamDT 试采库及其伴随原始证据",
    "data/local/database/raw": "旧来源内容寻址压缩响应",
    "data/local/api_cache": "旧官方目录与配额状态缓存，不自动刷新",
    "data/local/archive": "最初试采历史证据与受保护旧配置",
    "data/local/recon": "按日期保存的接口与事件探测证据",
    "data/local/universes": "旧候选快照与有明确批准用途的版本化研究验证名单",
    "data/local/progress": "旧进度 JSON 记录，当前文字交接迁入 docs/local/progress",
    "data/local/staging": "未验收候选试跑资产，不能直接训练",
    "data/local/staging/steamdt": "SteamDT 来源的独立候选试跑与原始追溯",
    "data/local/staging/research_samples": "离线日级研究候选、输入快照、特征标签、序列、质量报告与源码；非正式训练集",
    "data/local/staging/uu_charts": "私有用户导出图表响应与聊天投影的独立离线核验，非正式数据集",
    "docs": "计划、制度、使用说明和交接记录",
    "docs/governance": "管理、阶段、资产登记与版本索引",
    "docs/research": "专项选品、核验计划和有限调查证据，三大主文档的附件",
    "docs/data": "来源、schema 与字段说明",
    "docs/usage": "用户本地观察、图表导出与旧实现参考，不构成采集或发布授权",
    "docs/releases": "历史发布与本地版本变更说明",
    "docs/local": "私有交接文档，不加入 Git",
    "docs/local/progress": "当前本地交接与旧历史交接文档",
    "docs/local/pilots": "私有单品试跑和质量核验报告",
    "docs/local/selections": "私有选品计划版本快照与原始审查记录",
}

def protected(path):
    name = path.name.lower()
    return ((name.startswith(".env") and name != ".env.example")
            or name.endswith((".key", ".pem")) or name.startswith("credentials"))

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def code_version():
    tree = ast.parse((ROOT / "scripts/src/cs_youoweme/__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Missing source package version")

def git_public_paths():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True)
    paths = {name.decode("utf-8") for name in result.stdout.split(b"\0") if name}
    return {p for p in paths if (ROOT / p).is_file() and not p.startswith(("data/local/", "docs/local/", "scripts/local/")) and not protected(ROOT / p)} | {PUBLIC, INDEX}

def purpose(path):
    if path in PURPOSES:
        return PURPOSES[path]
    name = Path(path).name
    if path.startswith("data/local/artifacts/seven_training/"):
        return "七品训练私有版本的预处理、协议、准确源码、模型参数、运行状态与哈希"
    if path.startswith("data/local/reports/seven_training/"):
        return "七品模型仅重载评估、图表或本轮工程/保留核验的私有证据；非交易收益证明"
    if path.startswith("data/local/datasets/seven_daily/"):
        return "本版准确执行的源码、规范、schema或父清洗manifest快照" if "/source/" in path else {"samples.sqlite": "七品日级21输入、独立七日点/路径标签、分组/缺失/资格和追溯元数据", "features.csv": "按明确FEATURE_FIELDS白名单输出的过去输入，含商品和同日split键，不含y或未来资格", "labels.csv": "同键关联的七日真实点/路径标签、成熟/缺口/隔离与样本资格", "quality_report.json": "逐品/分组候选计数、点/路径标签独立状态和特征NULL数量", "report.md": "七品样本真实构建结果、缺失/标签/分组规则及未训练限制", "protocol_locked.json": "构建前锁定父清洗版本、规范和21x白名单", "manifest.json": "父清洗/源码/规范/schema/产物哈希、时间截止与研究用途", "latest.json": "仅指向具体成功冻结样本版本的入口"}.get(name, "七品日级特征/标签的不可变追溯附件")
    if path.startswith("data/local/reports/seven_samples/"):
        return "七品样本来源值/特征/标签/资格独立复算、保留基线、Notebook只读和离线构建核验附件"
    if path.startswith("scripts/research/"):
        return {"__init__.py": "研究功能包的职责与公共接口", "clean_hourly.py": "steamdt-hourly-cleaning-1.0：只读七品源版本、NULL/mask、原值保留、因果事件诊断与质量窗口", "daily_samples.py": "cyrex-daily-samples-1.1：只读冻结小时来源、28天样本、七日标签与准确依赖快照", "baselines.py": "仅使用过去价格特征的持平/固定对数趋势规则与七日路径", "baseline_report.py": "候选完整性校验、验证选择及锁定测试、预测与实验清单", "costs.py": "已知买价与费用的保本情景计算；未知输入保留为不足", "forecast_charts.py": "来源历史、真实七日目标与固定规则预测路径的Matplotlib图表及版本报告"}.get(name, "离线研究的功能实现与公共接口")
    if path.startswith("data/local/datasets/steamdt_clean/"):
        return "本版准确执行的源码、规范、方法或来源报告/registry快照" if "/source/" in path else {"clean.sqlite": "全部来源版本与请求、七品小时网格、真实价格/NULL及事件和输入质量标记的研究SQLite", "latest.json": "指向具体冻结清洗版本的本地入口", "manifest.json": "只读来源前后哈希、上限、规范、源码与清洗产物哈希清单", "protocol_locked.json": "清洗前先冻结规范和来源上限，确认真实极端走势保留", "quality_report.json": "逐品真实观察、缺口、量额未知、事件与质量窗口候选计数", "gaps.csv": "首次观察前、内部及尾部未观察小时的分段清单", "flagged_hours.csv": "版本、时刻和市场波动诊断，不是操盘或错误判定", "quarantine.csv": "不合法价格/量额字段的原始版本链接，原值仍保留", "report.md": "七品清洗摘要、缺失策略、未训练边界和下一步"}.get(name, "冻结清洗研究版的追溯附件")
    if path.startswith("data/local/reports/cleaning_reviews/"):
        return "清洗来源/输出原值、质量窗口、保留核对与Notebook默认只读行为的独立复核"
    if path.startswith("data/local/artifacts/baseline_evaluations/"):
        return "基准评估实际执行的源码或固定规范快照" if "/source/" in path else {"latest.json": "指向一个具体基准评估版本的本地便捷入口", "manifest.json": "候选/源码/规范/产物哈希与规则选择、非执行研究限制", "metrics.json": "验证集及锁定测试价格误差、基准对照与有效样本数量", "forecast.csv": "固定来源时点的day0至day7参考预测路径，不是未来真实行情", "history.csv": "用于图表的最近28天来源小时价格", "report.md": "固定基准的评估结果、用途和限制说明"}.get(name, "固定规则基准的离线评估、预测或复核附件")
    if path.startswith("data/local/reports/baseline_charts/"):
        return "冻结评估对应的价格图、输入/绘图版本清单或复核附件"
    if path.startswith("data/local/staging/research_samples/"):
        return "该候选构建器或规范的准确源码快照" if "/source/" in path else {"source_hourly.csv": "按已保存运行请求上限固定的次时代小时输入快照", "samples.csv": "单品日级过去特征、未来七日来源标签、缺失/成熟度和时间划分候选", "sequence.csv": "每个候选时点的28个历史日段，完整性与可空来源量额保留", "quality_report.json": "候选数量、缺口、未成熟、时间隔离和分组可用计数", "manifest.json": "候选输入、来源/源码/规范哈希、输出清单与未批准训练的版本记录", "report.md": "单品日级候选构建结果、范围、质量和研究用途限制", "latest_cyrex.json": "指向一个具体单品日级候选版本的本地入口"}.get(name, "单品日级研究候选的私有构建、验收或追溯附件")
    if protected(Path(path)):
        return "受保护本地凭证，仅登记配置版本，不读取、复制或记录内容及哈希"
    if path.startswith("data/local/staging/uu_charts/"):
        return {"quality_review.json": "完整七组真实输入的行数、重叠、时效、只读SQLite与既有资产保留核验", "review.md": "用户单轮历史采集的可读覆盖表与质量、时效和验收限制", "recovery_checkpoint_v1_1.json": "旧批次639点成功数据迁移至正确7任务计划的恢复检查点，未新增市场请求", "recovery_verification.json": "旧三组成功响应哈希与恢复计划一致性核对", "repair_verification.json": "本次窗口修复、原资产保留、离线检查及零请求记录", "price_windows.png": "用户成交价格7/30/90天/半年菜单截图证据", "listing_count_windows.png": "用户在售数量7/15/30天菜单截图证据", "batch_input.json": "用户浏览器下载批次准确输入，含窗口/响应/状态，不含登录头", "chart_batch.sqlite": "指标各自窗口独立批次SQLite，保留成功失败和待采及精确点", "collect_uu_charts.js": "批次对应浏览器采集代码的私有准确版本", "import_uu_chart_batch.py": "本次纯离线批次导入器准确源码", "review_uu_chart.py": "本次复用的图表字段核验准确源码", "request_body_price_7d_44828.json": "用户提供44828七天价格的安全请求正文，不含请求头", "price_response.json": "用户价格响应附件的准确字节副本，无请求头", "listing_count_projection.json": "用户聊天数量响应的 time/price 人工投影，不是完整原始响应", "provenance.json": "安全请求正文、接收日期、输入来源与投影省略字段说明", "preservation_baseline.json": "本次旧数据、Notebook 与冻结源码的非凭证保留哈希基线", "preservation_verification.json": "旧资产保留核对结果及零市场请求说明", "response_input.json": "本次离线核验输入字节；是否原始用户文件或人工投影由 manifest 说明", "report.json": "字段、指标、真实间隔、覆盖、质量与 L0 限制的离线核验报告", "points.csv": "价格与在售数量分列的图表点便览", "chart_review.sqlite": "独立离线图表核验 SQLite，价格为精确文本、在售数量为整数", "review_source.py": "本次离线核验脚本的准确私有源码版本", "manifest.json": "离线输入及源码哈希、请求上下文、输入类型和零市场请求清单"}.get(name, "用户图表离线核验的私有追溯附件")
    if path.startswith("scripts/local/pilot_sources/"):
        if name.endswith(".md"):
            return "该有限核验采集时的计划准确内容版本快照"
        return "该试跑实际执行源码的私有版本快照，校验值匹配来源清单"
    if path.startswith("scripts/local/selection_sources/"):
        return "该 P02 调查实际执行源码的私有版本快照，校验值匹配运行清单"
    if path.startswith("docs/local/selections/"):
        return "选品调查或规则修订前的计划准确版本快照，保留历次依据"
    if path.startswith("data/local/universes/uu_research_selection_"):
        return {"selection.json": "当前或原版验证名单、候选证据、批准用途和角色；仅限 P03 验证", "candidates.csv": "全部候选的身份、UU 报价时间、数据覆盖、角色、理由和未知项", "manifest.json": "名单来源运行、版本、批准用途与内容哈希", "verification.json": "名单独立核对：原始哈希、UU 报价与小时摘要、角色及预算一致性"}.get(name, "P02 版本化名单的伴随追溯元数据")
    if path.startswith("docs/local/pilots/"):
        return "单品单日有限试跑或离线质量核验报告，非正式研究结论"
    if path.startswith("data/local/staging/steamdt/"):
        if "/research_" in path:
            return "SteamDT小时研究库的压缩来源响应与哈希追溯" if "/raw/" in path else "该有限研究运行实际源码快照" if "/source/" in path else "SteamDT小时研究库、商品清单、逐品游标、共享访问控制、覆盖报告或导出；L0私有"
        if "/p03_steamdt_observe_" in path:
            return "连续观察的压缩原始响应，保持私有和哈希追溯" if "/raw/" in path else "用户本地连续观察的独立 SQLite 与采样/恢复/请求检查点" if name == "observations.sqlite" else "连续观察的固定清单、运行摘要、状态报告、互斥锁或快照导出"
        if "/p03_steamdt_fields_" in path:
            return "P03 比较字段补查的压缩原始响应，保持哈希追溯" if "/raw/" in path else "P03 独立汇总字段补查 SQLite，不是正式数据集" if name == "verification.sqlite" else "P03 字段补查、规范来源观察、全页逐笔和独立离线核验的版本化证据"
        if "/p02_steamdt_selection_" in path:
            return "有限选品调查的压缩原始响应，保持私有与哈希追溯" if "/raw/" in path else "独立选品调查 SQLite 库" if name == "survey.sqlite" else "P02 来源请求、计划/脚本版本、预算、结果与输入输出清单"
        if "/raw/" in path:
            return "该有限试跑的压缩原始响应，用于请求哈希追溯，保持私有"
        if name == "pilot.sqlite":
            return "独立单品单日试跑库，不追加旧库、不作为正式训练集"
        if name.endswith(".worker.lock"):
            return "独立试跑库的 worker 锁状态"
        return {"uu_hourly.csv": "指定日的来源标称 UU 小时 OHLC、量额和追溯编号，L0 候选", "source_trades_unmapped.csv": "单日去重后的混合成交，venue unknown，不认定为 UU", "manifest.json": "原始采集范围、代码、预算、覆盖、状态与输入输出哈希", "platform_evidence.json": "采集时的平台键证据，原始大小写提取由独立核验补充", "requests.json": "请求端点、采集时间、HTTP 状态、原始路径与 SHA-256", "quality_review_v1.json": "离线核验：原始哈希、CSV 一致性、UU 键映射、空值与重复", "source_versions.json": "实际采集与核验脚本的私有快照和内容版本"}.get(name, "单品单日候选试跑的伴随元数据")
    if path.startswith("scripts/src/"):
        return SOURCE_PURPOSES[name]
    if path.startswith("scripts/tests/"):
        return "离线测试辅助与共享样本路径" if name == "_support.py" else f"{name[5:-3]} 模块的离线行为回归测试"
    if path.startswith("scripts/sql/"):
        return {"01_catalog.sql": "旧库目录搜索与身份查询", "02_universe.sql": "旧候选名单查询", "03_market.sql": "旧逐笔与行情查询", "04_coverage.sql": "旧覆盖和分页进度诊断"}[name]
    if path.startswith("docs/releases/v"):
        return f"{Path(name).stem} 已发布版本的历史说明"
    if path.startswith("data/samples/"):
        return "旧匿名公开样本的" + ({".csv": "派生表", ".md": "质量说明"}.get(Path(name).suffix, "来源响应或来源清单")) + "，冻结待 UU 用途复审"
    if path.startswith("data/local/database/raw/"):
        return "旧来源的内容寻址压缩响应，保留数据库请求追溯"
    if path.startswith("data/local/database/"):
        return "旧 SteamDT 试采库，非正式 UU 数据集" if name.endswith(".sqlite") else "旧库 worker 锁状态文件，保留原状"
    if path.startswith("data/local/api_cache/"):
        return "旧官方目录缓存，重复 recon 目录文件的保留副本" if name == "base.json" else "旧来源配额时间状态，不自动刷新"
    if path.startswith("data/local/recon/"):
        if "/user_uu_history_chart_20261014/" in path:
            return "用户 UU 历史图表截图原始证据，保持私有" if name.endswith(".png") else "用户历史图表接收日期、原始哈希、可见指标、分窗口频率与未改动文件哈希"
        if "/user_attribute_scope_20261014/" in path:
            return "用户求购截图原始证据，保持私有，不公开买家信息" if name.endswith(".png") else "用户截图接收日期、原始哈希、可见行范围与规则修订及未改动文件哈希"
        if "/p03_20261013_evidence/" in path:
            return "P03 已发现公开网页/脚本/官方规则的压缩证据" if name.endswith(".body.gz") else "P03 公开核验请求、响应哈希、实际代码和访问受限主机的持久清单"
        return f"{Path(name).stem} 接口或事件探测的原始历史证据，保留待核验"
    if path.startswith("data/local/universes/"):
        return f"{Path(name).stem} 旧候选快照，不是正式 UU 名单"
    if path.startswith("data/local/archive/"):
        return "最初试采的原始响应、表、报告或配置证据，保留来源追溯"
    if path.startswith("data/local/manifests/"):
        return {"layout-1.0-before.json": "整理前逐文件大小与哈希基线，凭证不记录哈希", "layout-1.0-changes.json": "逐项迁移、删除依据与 Git/保留副本恢复路径", "layout-1.0-verification.json": "迁移后保留数据哈希核对与检查结果", Path(PRIVATE).name: "私有文件和目录的版本及用途清单"}.get(name, "本地版本及检查元数据")
    if path.startswith(("data/local/progress/", "docs/local/progress/")):
        return "当前本地交接入口" if name == "CURRENT.md" else "旧进度历史记录，不能据此恢复采集"
    if path == "data/local/README.md":
        return "私有历史数据的本地用途与管理索引"
    raise ValueError(f"Missing purpose for {path}")

def folder_purpose(path):
    if path in FOLDERS:
        return FOLDERS[path]
    if path.startswith("scripts/research/"):
        return "当前离线研究的功能包与公共接口"
    if path.startswith("data/local/artifacts/seven_training/"):
        return "明确版本的七品训练准备/实验及准确源码，私有且旧版不覆盖"
    if path.startswith("data/local/reports/seven_training/"):
        return "明确版本的七品重载评估或工程验证证据，私有留存"
    if path.startswith("data/local/datasets/seven_daily/"):
        return "一次七品特征与独立七日标签研究候选、准确实现/规范/schema及父清洗追溯"
    if path.startswith("data/local/reports/seven_samples/"):
        return "七品特征标签的独立复核、旧资产保留和Notebook默认行为记录"
    if path.startswith("data/local/datasets/steamdt_clean/"):
        return "一次冻结的七品小时清洗研究版本、质量输出与准确来源/实现快照"
    if path.startswith("data/local/reports/cleaning_reviews/"):
        return "一次清洗研究版本的独立只读复核与默认Notebook执行验证"
    if path.startswith("data/local/artifacts/baseline_evaluations/"):
        return "一次不可变基准评估的预测、分组误差、输入与源码快照"
    if path.startswith("data/local/reports/baseline_charts/"):
        return "一次冻结评估对应的价格图及绘图输入/版本清单"
    if path.startswith("data/local/staging/research_samples/"):
        return "离线日级样本候选的独立版本、准确源码/规范、冻结输入、特征/标签、序列与验收报告"
    if path.startswith("data/local/staging/uu_charts/"):
        return "用户指标不同时间范围的私有菜单截图证据" if path.endswith("/window_evidence") else "用户图表输入、请求正文与人工投影来源说明" if "/inputs_" in path else "一次独立图表离线核验的 SQLite、CSV、报告、输入和准确源码"
    if path.startswith("scripts/local/pilot_sources/"):
        return "该运行实际采集及核验源码快照"
    if path.startswith("scripts/local/selection_sources/"):
        return "该有限选品调查的实际源码版本"
    if path.startswith("docs/local/selections/"):
        return "该选品调查或规则修订前的计划准确版本"
    if path.startswith("data/local/universes/uu_research_selection_"):
        return "该版本的研究验证名单、候选表及准入用途清单"
    if path.startswith("data/local/staging/steamdt/"):
        if "/research_" in path:
            return "用户本地SteamDT小时研究工作区或共享控制：原始证据、SQLite、清单、分页进度、源码、报告及导出"
        if "/p03_steamdt_observe_" in path:
            return "用户本地有预算连续观察的独立数据、原始响应、状态和导出"
        if "/p03_steamdt_fields_" in path:
            return "独立 P03 汇总字段补查的原始响应、规范观察、报告或哈希分桶"
        return "独立单品单日试跑的原始响应、表、报告或哈希分桶"
    if path.startswith("data/local/recon/user_attribute_scope_20261014"):
        return "用户求购条件截图及范围修订的私有版本证据"
    if path.startswith("data/local/recon/user_uu_history_chart_20261014"):
        return "用户历史图表截图及分窗口采样频率的私有证据"
    for prefix, label in (("data/local/database/raw/", "旧压缩响应的哈希分桶"), ("data/local/archive/", "最初试采历史证据的分组"), ("data/local/recon/", "按日期保存的来源探测证据"), ("data/local/api_cache/", "按本地凭证标识隔离的旧缓存，不公开标识"), ("data/samples/", "旧匿名样本批次及原始/表/报告分组")):
        if path.startswith(prefix):
            return label
    if path.startswith("data/local/"):
        return purpose(path + "/_directory.json").replace("_directory 接口或事件探测", "接口或事件探测")
    raise ValueError(f"Missing folder purpose for {path}")

def catalog(paths, private=False):
    rows = []
    for path in sorted(paths):
        item = ROOT / path
        hidden = protected(item)
        checksum = None if hidden or path in CATALOGS else digest(item)
        rows.append({"path": path, "purpose": purpose(path), "status": "private-protected" if hidden else "private-legacy-or-metadata" if private else "legacy-unreviewed" if path.startswith(("scripts/src/", "scripts/tests/", "data/samples/")) else "current-or-reference", "version": "protected-local-1" if hidden else LAYOUT + ".catalog" if path in CATALOGS else "sha256:" + checksum, "sha256": checksum, "bytes": None if path in CATALOGS or hidden else item.stat().st_size})
    folders = {"."}
    for row in rows:
        folders.update(p.as_posix() for p in Path(row["path"]).parents if p.as_posix() != ".")
    if private:
        folders.update(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_dir() and ".git" not in p.relative_to(ROOT).parts and p.relative_to(ROOT).as_posix().startswith(("data/local", "docs/local", "scripts/local")))
    directories = []
    for folder in sorted(folders):
        members = [(r["path"], r["version"]) for r in rows if folder == "." or r["path"].startswith(folder + "/")]
        version = hashlib.sha256(json.dumps(members, ensure_ascii=False).encode()).hexdigest()
        directories.append({"path": folder, "purpose": folder_purpose(folder), "layout_version": LAYOUT, "version": "sha256:" + version})
    return {"schema_version": 1, "layout_version": LAYOUT, "code_version": code_version() + "-untagged", "scope": "private-ignored-files" if private else "git-managed-files", "hash_policy": "SHA-256; generated catalogs exclude their own bytes to avoid circular hashes; protected credentials have no content/hash snapshot", "directories": directories, "files": rows}

def serialize(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

def readable_index(public):
    lines = ["# 文件与目录说明", "", f"自动生成，目录版本 {LAYOUT}，冻结核心 {code_version()}（未打发布标签）。完整 SHA-256 见 [机器清单](FILE_CATALOG.json)。私有逐项清单只在 data/local/manifests/workspace-layout-1.0.json；Git 内部对象由 Git 管理。生成清单使用固定目录版本，不计算自身哈希以避免循环。", "", "## 目录", "", "| 路径 | 用途 | 内容版本（摘要） |", "| --- | --- | --- |"]
    for row in public["directories"]:
        link = "../.." if row["path"] == "." else "../../" + row["path"]
        lines.append(f"| [{row['path']}]({link}) | {row['purpose']} | {row['version'][:19]} |")
    lines += ["", "## 文件", "", "| 路径 | 用途 | 内容版本（摘要） |", "| --- | --- | --- |"]
    for row in public["files"]:
        lines.append(f"| [{row['path']}](../../{row['path']}) | {row['purpose']} | {row['version'][:19]} |")
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    public_paths = git_public_paths()
    all_paths = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.relative_to(ROOT).parts}
    private_paths = (all_paths - public_paths) | {PRIVATE}
    # Generated cache files are not research assets and must not enter catalogs.
    private_paths = {p for p in private_paths if not p.endswith(".pyc") and "__pycache__" not in Path(p).parts}
    public_catalog = catalog(public_paths)
    expected = {PUBLIC: serialize(public_catalog), PRIVATE: serialize(catalog(private_paths, private=True)), INDEX: readable_index(public_catalog)}
    for path, content in expected.items():
        destination = ROOT / path
        if args.write:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
        elif not destination.exists() or destination.read_text(encoding="utf-8") != content:
            print("Catalog differs; regenerate with --write after reviewing the change.")
            return 1
    print(f"Catalog {'written' if args.write else 'verified'}: {len(public_paths)} public files, {len(private_paths)} private files; no private paths or values printed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
