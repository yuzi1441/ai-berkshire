# A/H 情绪快照 VPS 任务

这条任务只读取投资决策总表中的 A 股和港股股票池，输出独立情绪数据，
不会修改研报、决策结论、看板 JSON 或网页。

## 产物

- `data/sentiment/latest.json`：最新快照
- `data/sentiment/snapshots/YYYY-MM-DD.json`：每日历史快照
- `site/data/sentiment.json`：看板读取的同一份最新快照

数据包括：

- A 股市场温度：涨跌家数、涨跌停、极端涨跌、炸板率和情绪指数动量
- A 股个股：新闻方向分、事件强度、时间衰减和同花顺关注度
- 行业层：按东方财富主行业分类，同一行业只抓取一次行业新闻
- 港股个股：新闻方向分、事件强度、时间衰减和行业情绪

综合情绪分默认按以下权重计算：A 股为个股新闻 70% + 行业新闻 20% + 市场温度
10%；港股为个股新闻 80% + 行业新闻 20%。缺少行业数据时会自动按现有组件重新归一化。

关注度只表示拥挤/过热，不会被当作方向性利好。

个股新闻有本地相关性保护：标题和摘要均没有公司名或股票代码的搜索结果会被降权，
避免把同一行业的其他公司新闻误归因给当前公司。

新闻抓取优先使用近 7 日窗口；如果窗口内没有抓到新闻，则自动回溯近 30 日，
并在结果中标记“近 7 日无新消息，参考近 30 日”。旧新闻仍按事件半衰期衰减，
不会与当天新闻等权处理。完全没有新闻和抓到新闻但没有有效相关新闻会分别标记。
看板详情同时显示所有抓取新闻和实际纳入评分的新闻，未纳入的新闻会标注过滤原因。

## 安装

在 `/opt/ai-berkshire` 已有仓库和 `.venv` 的前提下，以 root 执行：

```bash
cd /opt/ai-berkshire
git pull --ff-only origin main
bash deploy/vps/install-sentiment-job.sh
systemctl start ai-berkshire-sentiment-update.service
journalctl -u ai-berkshire-sentiment-update.service -n 100 --no-pager
```

定时器默认在工作日北京时间 18:10 后加 0–5 分钟随机延迟执行。脚本与技术面任务
共用 Git 仓库锁，避免同时 pull/commit/push。

## 双模型复核配置

当前快照要求两个 OpenAI-compatible Chat Completions 模型都配置成功：
`SENTIMENT_LLM_*` 为主模型（当前使用 DeepSeek Flash），`SENTIMENT_REVIEW_*` 为中转站复核模型。
请编辑 `/etc/ai-berkshire/sentiment.env`，填写复核模型的 key、model 和 endpoint。
两组模型的单次请求超时默认均为 180 秒，可分别用 `SENTIMENT_LLM_TIMEOUT` 和
`SENTIMENT_REVIEW_TIMEOUT` 调整，允许范围为 30–600 秒。

任一模型超时、接口错误、JSON 格式错误或返回缺失新闻条目时，本次快照不会生成；
看板保留上一份成功快照，并通过 `site/data/sentiment_status.json` 显示更新失败。
密钥文件权限为 `0600`，不会写入仓库。

检查定时器和最近日志：

```bash
systemctl list-timers ai-berkshire-sentiment-update.timer --no-pager
systemctl status ai-berkshire-sentiment-update.timer --no-pager
journalctl -u ai-berkshire-sentiment-update.service -n 100 --no-pager
```
