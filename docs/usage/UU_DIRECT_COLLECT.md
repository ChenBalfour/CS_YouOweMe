# UU 纯脚本历史采集试用

版本 **uu-direct-collect-1.2**；2026-10-15，北京时间。程序 **uu-direct-chart-pilot-1.0**，只使用 Python 3.11+ 标准库。**无需采集时打开浏览器；44828已完成一次真实直连，完整七组和多轮仍待验收。**

## 当前能做什么

[collect_uu_direct.py](../../scripts/collect_uu_direct.py) 按本地商品清单直接 POST 已知图表读取接口，串行采集并保存原响应、SQLite、CSV、状态和准确源码。窗口仍为价格7/30/90天/半年、在售数量7/15/30天，共七组。与浏览器批次的来源标签、时间字段和库分开，不伪装成已验证的浏览器采集。

Cookie 可以作为本机登录配置的一部分，但不能保证 Cookie 单独足够。用户此前提供的正常请求还含 Authorization、设备标识等字段；哪些字段必需、会话是否绑定设备、是否有动态校验尚未核验。本工具不会生成或破解签名，也不会自动登录、刷新凭证或切换账号。首次取得及过期更新登录信息仍需用户正常登录；已有小号不意味着没有访问限制。

## 本地准备

在项目根目录的 VS Code 终端运行。首次配置可执行：

```powershell
python -B scripts/collect_uu_direct.py init-auth
```

它只创建空白的 `scripts/config/credentials_uu_chart.json`，不会联网，也不会覆盖已有文件。该文件已由 Git 忽略和资产制度保护，不读取内容制作文件清单、不计算凭证哈希。**Cookie、Authorization 等值只填进本地此文件，不贴到聊天、Notebook 单元格、命令参数或日志。**

配置文件中的 headers 对应正常成功请求的同名字段。可先使用自己正常登录会话的 cookie/authorization；如确实需要设备字段，仍只在本地填写从同一正常请求得到的原值。不要把完整“复制为fetch”、浏览器存储导出或账号个人信息放进文件。空白字段不会发送；程序不打印配置值，失败只输出固定原因分类。

商品清单模板是 [uu_direct_items.example.json](../../scripts/config/uu_direct_items.example.json)。44828只是已有真实图表响应的技术样例，完整名称、磨损和版本仍需核对，不能自动加入正式百元名单。可将模板另存为 `data/local/staging/uu_charts/direct_items_v1.json` 后修改；每轮暂限1至3个商品，半年 day 填正常页面已确认的实际参数，44828已实证180。

## Edge 中逐项取得本地配置

这一步由用户自己操作；不向聊天粘贴请求头、截图中的登录值或配置文件。

1. 用自己的账号正常登录 UU，打开上次采集的44828商品页，确认价格走势能正常加载。
2. 按F12（笔记本也可能是Fn+F12），选“网络 / Network”。网络面板要先打开，才能记录接下来的请求。
3. 在筛选框输入 `price/trend/data`，回到网页切换一次“成交价格”的时间范围，例如从半年切到近7天。不运行旧采集面板，避免同时发送批次请求。
4. 在新出现的 `data` 请求中，选择POST且状态200的那一条。点开后在“常规 / General”核对Request URL是 `https://pc-api.youpin898.com/api/youpin/price/trend/data`；在“载荷 / Payload”核对orderType为1、templateId为44828。这里不需要复制载荷。
5. 选择“标头 / Headers”，展开“请求标头 / Request Headers”，向下找下表字段。不要从“响应标头 / Response Headers”或Set-Cookie取值；Authorization和Cookie可能需要展开后才能看到。Headers中的Request Headers位置见[微软Edge官方说明](https://learn.microsoft.com/en-us/microsoft-edge/devtools/network/reference#display-http-headers)。
6. 逐项复制冒号右侧的完整值（可右键值选择“复制值 / Copy value”，若菜单没有就选中值复制），直接粘贴到本机VS Code对应的JSON双引号中。只复制值，不带字段名，不复制整段fetch，也不改变值；若Authorization带Bearer前缀则原样保留，没有则不额外添加。

| Edge请求标头字段 | 本地JSON字段 | 填写方法 |
| --- | --- | --- |
| authorization / Authorization | authorization | 复制同一正常成功请求的原值 |
| cookie / Cookie | cookie | 该请求显示才复制整段值；没有则保留空字符串，不必额外导出浏览器全部Cookie |
| deviceid、deviceuk、uk | 各自同名字段 | 有则复制各自原值，全部来自同一账号会话和同一请求 |
| app-version、appversion、apptype、platform、secret-v | 各自同名字段 | 按当前请求填写，不沿用文档中的旧版本号；缺少的字段留空 |

如果目标请求根本没有Cookie，这不代表操作错了；接口可能使用Authorization，是否足够仍需单请求试采。不要用其他网站、主账号或不同设备的值拼在一起。

在VS Code中选择“文件→打开文件夹”，打开 `F:\Codex\CS_YouOweMe`。按Ctrl+P输入 `scripts/config/credentials_uu_chart.json` 打开已准备的私有文件，填好后按Ctrl+S。JSON左边字段名、逗号、外层大括号和英文双引号保持原样，不写注释；如果有红色语法提示，先修正再运行。不要编辑或填入公开的uu_direct_auth.example.json。

若找不到请求，先确认Network正在记录、未选中过窄的其他类型过滤，然后再次切换时间范围；若网页本身加载失败或返回401/403/429，先停止，不用命令行反复尝试。浏览器配置步骤只用于首次取得/后续更新会话，脚本实际采集时不需要继续开着网页。

## 先查看计划，不联网

```powershell
python -B scripts/collect_uu_direct.py plan
```

此命令不读取凭证、不建采集运行、不发送请求。默认模板生成7个任务，展示间隔、配额和现存访问停止状态。自定义名单时给 plan/probe 加 `--items "你的清单路径"`。

## 第一次只尝试一组

旧 UU 直接入口曾返回429，新工具会继承该主机的停止事实，不因换账号或新建运行自动清除。先由你确认当前自己的正常 UU 页面可以访问，再显式运行：

```powershell
python -B scripts/collect_uu_direct.py probe --normal-access-confirmed
```

`--normal-access-confirmed` 表示你已经人工确认访问恢复，不是绕过检查的技术开关；不要在仍被限制时使用。历史停止证据保持原样，新工具另记这次确认；如服务端冷却未到，即使带此参数也拒绝请求。

probe 最多尝试第一商品的7天价格一组，另外六组保留 pending；不会一次采完商品清单。输出 `run_id` 和私有结果目录。需要更慢时可加 `--interval 30 --item-gap 120`，间隔会冻结在该运行中。

成功后，使用输出的真实 run_id 查看状态或继续：

```powershell
python -B scripts/collect_uu_direct.py status --run direct_这里替换成真实运行编号
python -B scripts/collect_uu_direct.py resume --run direct_这里替换成真实运行编号
```

status不联网、不读取凭证。resume只处理未尝试的pending，已成功、失败和结果未知的任务都不重发。对于单商品且首组成功的运行，继续最多尝试剩余六组。运行编号不是文件路径，不能把占位文字原样执行。

## 当前44828试采的下一步

运行 `direct_20261015T150205Z_b85af6ee` 已保存7天价格103点，partial_no_automatic_retry表示probe按设计只尝试一组，不是这次请求失败。用户可在原终端继续：

```powershell
python -B scripts/collect_uu_direct.py resume --run direct_20261015T150205Z_b85af6ee
```

只尝试同一商品剩余六组，已保存的一组不重发，沿用15秒请求间隔；不会自动变成循环采集。全部通过时应为status=completed、success=7、failed=0、pending=0、interrupted_unknown=0，点数以实际响应为准。失败或受限则停止，不反复运行。完成后只需反馈终端状态，不发送登录配置。

## 节奏、停止和保存

- 默认请求间隔15秒，换商品间隔至少60秒，并发1；可配置范围分别为10–300秒、30–600秒。跨新建/恢复运行仍共享本工具的上次请求与商品记录，不能重开脚本就跳过间隔。
- 同一台电脑该工具的所有配置共用每滚动24小时60次尝试上限；请求发出前即记账。每轮最多3商品/21任务，每次执行在启动新请求前检查15分钟预算，网络连接/读取超时至多30秒、单响应至多2MiB。这些是本项目初始预算，**不是UU公布的安全频率，不保证不封号**。
- 不自动重试，不轮换账号或IP；401/403/429、其他HTTP错误、业务失败、空序列、结构异常或网络失败都会保存状态并停止剩余队列。429如含Retry-After则解析为最早恢复时间；未提供时至少冷却15分钟，冷却结束也需要人工确认正常访问后才可继续。[429与Retry-After说明](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/429)。
- 新运行或更换本地凭证不会清除停止状态、配额或冷却。不要同时运行旧采集器、浏览器脚本和本工具；本工具互斥锁只管理自身进程，不能限制其他程序。
- Ctrl+C会记录中断。若中断发生在已发送但未保存结果的阶段，该任务为interrupted_unknown，不自动重发。不强制删除worker.lock；如果进程意外结束遗留锁，先确认没有旧进程，再人工处理。
- 登录信息只在私有配置与请求内存中；不跟随任何重定向，不使用环境代理，不记录错误响应正文/认证头/Set-Cookie，不把凭证复制进源码快照。会话更新仅由用户本地完成。

## 输出与数据用途

新结果只写 `data/local/staging/uu_charts/direct_<运行编号>/`：

| 文件 | 含义 |
| --- | --- |
| run.json / report.json | 清单、准确请求正文、成功/失败/待采/未知、取得时间、脚本版本和汇总 |
| raw/*.json | 通过指标、结构、数值与凭证回显检查的成功响应准确字节；错误正文不存 |
| charts.sqlite / points.csv | 各任务独立保留窗口点；价格精确文本、数量整数、historical_available_at为空 |
| source/ | 该运行实际采集和校验源码，继续运行前检查当前版本一致 |

`direct_control/`仅保存停止状态、请求时间、配额、人工恢复确认及锁，不存账号或凭证摘要。新工具不会改写旧数据库、下载批次、Notebook输出、旧受限入口或冻结采集源码。

用户运行direct_20261015T150205Z_b85af6ee已完成真实probe：44828七天价格103点，1成功/0失败/6待采/0未知，SQLite只读完整性和原响应哈希通过。当前本机配置在该次请求可用，不证明Cookie单独足够；其余六组、接口限制与多轮稳定性仍待验收。只积累和检查数据，不训练、不交易；成交价格统计、完整商品身份和历史可得时间仍有缺口。
