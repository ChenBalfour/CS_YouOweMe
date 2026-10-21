# UU 图表导出与离线核验

版本 uu-chart-export-1.0，2026-10-14，北京时间。本说明只导出正常登录页面已取得的响应，并在本地解析；不会启动市场采集。

## 在 Edge 复制数据

1. 在 UU 商品页选择“价格走势”，明确选择“成交价格”或“在售数量”及时间范围。
2. 按 F12，打开 Network（网络）；若列表为空，重新选择图表范围，让页面正常加载。
3. 找到路径含 `/api/youpin/price/trend/data` 的请求，点击后看 Response（响应），应是含 code/data 的 JSON。
4. 右键该请求 → Copy（复制）→ **Copy response（复制响应）**。此路径见 [Microsoft Edge 文档](https://learn.microsoft.com/en-us/microsoft-edge/devtools/network/reference#copy-a-response-to-the-clipboard)。
5. 在 VS Code 将正文保存为项目私有 `data/local/staging/uu_charts/inputs_<新批次>/price.json` 或 `count.json`。另记商品名称、版本、磨损、templateId、页面指标和天数。

仅需要响应正文。Copy as fetch、请求头或完整 HAR 会带入账号会话资料；不将它们保存或贴入文档。不要提供登录凭证或验证码。

## 从项目根离线运行

Python 3.11+，标准库即可。以下命令可对已保存的价格附件再次离线核验；参数中的 980/30 只对应现有技术例子，换商品时必须使用实际请求上下文。

```powershell
python -B scripts/review_uu_chart.py data/local/staging/uu_charts/inputs_20261014_v1/price_response.json --template-id 980 --order-type 1 --days 30 --output data/local/staging/uu_charts/price_local_review_01
```

成交价格用 `--order-type 1`，在售数量用 `--order-type 11`；`--days` 是页面实际请求窗口。输出目录须为私有 uu_charts 下的全新目录，已有批次不能覆盖。

终端只显示简要结果；文件保存在 `--output` 指定的目录：

| 文件 | 用途 |
| --- | --- |
| report.json | 字段、真实时间间隔、各日点数、质量标记与限制 |
| points.csv | 直接查看规范点，价格/数量各占独立列 |
| chart_review.sqlite | SQLite 主结构化结果；查看时用只读连接 |
| response_input.json、manifest.json、review_source.py | 输入字节、来源上下文、哈希及本次核验的准确源码 |

本工具没有网络调用，不读取登录配置，不启动 Notebook。它验证结构与数值，并不确认商品身份、统计价格含义、过去可得时间或可执行卖价。当前仍限 L0 来源观察，完整历史下载与训练尚未开始。字段与样例结果见 [图表说明](../data/UU_HISTORY_CHART.md)。
