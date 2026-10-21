# 凭证与发布

说明版本 security-1.2，目录 layout-1.0。真实凭证仅留在忽略的 scripts/config/.env 或环境变量；公开 scripts/config/.env.example 保持空白。

Git 忽略 data/local、docs/local、scripts/local 和本地配置。scripts/local 仅保存实际运行源码的私有版本快照。版本清单不会复制凭证内容或记录其哈希；私有文件路径只进入私有清单。来源响应可能含账户信息，不直接公开。

本地 hooks 位于 scripts/hooks，提交前检查暂存字节，推送前检查可达历史。本轮用户已授权公开分支迭代；私有原始响应、数据库、实验、截图、真实认证配置与用户Notebook执行输出不提交。`python -B scripts/check_secrets.py --history` 检查已知凭证及编码形式、非空赋值、受保护路径和常见凭证格式，只报告位置与状态。

凭证已经公开时先撤销或轮换，再处理公开内容和历史。仅删除最新文件不能清除历史。工程检查不替代最终 P06 对发布清单、个人资料及第三方数据的审查。
