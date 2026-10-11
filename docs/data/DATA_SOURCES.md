# 数据来源与分发

主要来源为 [SteamDT](https://www.steamdt.com/) 的匿名公开商品详情页。其[官方介绍](https://www.steamdt.com/terms/AboutUs)将平台定位为 CS 饰品数据分析工具。

首批访问 20 个商品 URL，提取服务端渲染的 `__NUXT_DATA__` 数据，使用明确的商品名匹配主对象，检查响应 `success=true`。完整网页留在 `data/local/archive/initial_collection/` 的最初本地采集归档，不作为开源代码分发。

公开样本目录包含同批提取的 JSON payload、标准化 CSV、manifest 和质量报告。每条 CSV 的 source_url 指向原始商品页面；raw_path 相对仓库根目录，raw_sha256 校验本仓库中的 payload 字节；original_html_sha256 记录原始完整网页字节的 SHA-256。

样本采集时间为北京时间 2026-10-11 22:15 至 22:16。20 个主样本均为普通版、久经沙场；关联规格是同页返回的有限字段。样本不能代表全市场，也不能替代成交明细或历史时间序列。

官方 API 参考：

- [接入与认证](https://doc.steamdt.com/)
- [接口权限与频率](https://doc.steamdt.com/6369437m0)
- [基础目录](https://doc.steamdt.com/278832832e0)
- [批量报价](https://doc.steamdt.com/278832831e0)
- [饰品 K 线](https://doc.steamdt.com/428124801e0)

官方 API 的采集代码已准备，真实认证调用、币种和 K 线字段定义尚未验证。文档示例不作为采集数据。

原创采集代码与文档采用 MIT 许可。样本中的第三方市场事实、平台商标和原站内容不因本项目发布而获得新的授权。

官方 K 线文档明确“不包含成交数据”。历史价格、真实成交量与供给历史必须分别核实可得性，研究设计见 [因子建模方案](../research/FACTOR_MODELING.md)。
