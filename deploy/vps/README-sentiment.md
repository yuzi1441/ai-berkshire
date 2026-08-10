# A/H 情绪快照 VPS 任务

这条任务只读取投资决策总表中的 A 股和港股股票池，输出独立情绪数据，
不会修改研报、决策结论、看板 JSON 或网页。

## 产物

- `data/sentiment/latest.json`：最新快照
- `data/sentiment/snapshots/YYYY-MM-DD.json`：每日历史快照

数据包括：

- A 股市场温度：涨跌家数、涨跌停、极端涨跌、炸板率和情绪指数动量
- A 股个股：新闻方向分、事件强度、时间衰减和同花顺关注度
- 港股个股：新闻方向分、事件强度和时间衰减

关注度只表示拥挤/过热，不会被当作方向性利好。

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

## 可选远程模型

默认使用无需额外 Python 依赖的规则评分。若要提升标题语义判断，可编辑
`/etc/ai-berkshire/sentiment.env`，填入 OpenAI-compatible Chat Completions
接口的 key、model 和 endpoint。密钥文件权限为 `0600`，不会写入仓库。

检查定时器和最近日志：

```bash
systemctl list-timers ai-berkshire-sentiment-update.timer --no-pager
systemctl status ai-berkshire-sentiment-update.timer --no-pager
journalctl -u ai-berkshire-sentiment-update.service -n 100 --no-pager
```
