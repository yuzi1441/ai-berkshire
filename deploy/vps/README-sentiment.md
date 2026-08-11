# A股情绪快照 VPS 任务

这条任务目前只读取投资决策总表中的 A 股股票池，输出独立情绪数据，
不会修改研报、决策结论或投资决策总表；它会更新看板读取的情绪数据。

## 产物

- `data/sentiment/latest.json`：最新快照
- `data/sentiment/snapshots/YYYY-MM-DD.json`：每日历史快照
- `site/data/sentiment.json`：看板读取的同一份最新快照

数据包括：

- A 股市场温度：涨跌家数、涨跌停、极端涨跌、炸板率和情绪指数动量
- A 股个股：新闻方向分、事件强度、时间衰减、同花顺关注度和来源核验等级
- 行业层：按东方财富主行业分类，同一行业只抓取一次行业新闻，作为辅助信息

个股综合情绪分只使用个股新闻 100%。行业新闻、A 股市场温度和同花顺关注度会在看板
中展示，但不计入个股综合分，避免把宏观或行业噪音混入个股判断。

关注度只表示拥挤/过热，不会被当作方向性利好。

新闻来源分为四级：

- A 级：直连巨潮资讯公告、交易所、监管机构、公司公告或投资者关系页面等一手披露，可评分。
- B 级：财联社、证券时报等专业媒体，可进入评分，但明确标注为单一二手来源；重大事件仍需人工核对一手公告。
- C 级：Google News RSS、Bing News RSS、东方财富平台资讯以及聚合转载等，仅作为辅助，不计入评分。
- D 级：东方财富股吧普通用户帖子等社区/传闻，仅作为辅助，不计入评分。

看板会展示全部抓取结果，并标注“已纳入评分”“相关性不足”或“仅辅助”。A 股公司新闻
会同时经过东方财富广泛发现和巨潮资讯官方公告查询；相同标题优先保留巨潮原始 PDF 链接。
C/D 级新闻
不会发送给模型，也不会改变情绪分；A 股可评分新闻仍要求主模型和复核模型均成功，任一
模型失败则本次快照不发布，保留上一份成功结果。

个股新闻有本地相关性保护：标题和摘要均没有公司名或股票代码的搜索结果会被降权，
避免把同一行业的其他公司新闻误归因给当前公司。

新闻抓取优先使用近 7 日窗口；如果窗口内没有抓到新闻，则自动回溯近 30 日，
并在结果中标记“近 7 日无新消息，参考近 30 日”。旧新闻仍按事件半衰期衰减，
不会与当天新闻等权处理。完全没有新闻、只有辅助新闻和抓到新闻但没有有效相关新闻
会分别标记。看板详情同时显示所有抓取新闻和实际纳入评分的新闻，未纳入的新闻会标注
来源等级、核验状态和过滤原因。

每只股票默认保留 8 条可评分候选，同时额外抓取最多 20 条 C/D 级辅助资讯；其中东方
财富股吧公开页面会把普通用户帖子标为 D，把平台资讯/自媒体帖子标为 C；Google News
RSS 和 Bing News RSS 作为独立 C 级聚合搜索渠道。辅助池只增加看板可见信息，不发送给
模型，因此不会增加模型评分 token；可通过 `--auxiliary-news-limit` 和
`--rss-news-limit` 调整。

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

## A股双模型复核配置

`SENTIMENT_LLM_*` 为主模型（当前使用 DeepSeek Flash），负责 A股可评分个股新闻和行业
辅助新闻。`SENTIMENT_REVIEW_*` 为中转站复核模型，只复核 A股可评分个股新闻。
请编辑 `/etc/ai-berkshire/sentiment.env`，填写 A股复核模型的 key、model 和 endpoint。
两组模型的单次请求超时默认均为 180 秒，可分别用 `SENTIMENT_LLM_TIMEOUT` 和
`SENTIMENT_REVIEW_TIMEOUT` 调整，允许范围为 30–600 秒。

对于 A股新闻，任一模型超时、接口错误、JSON 格式错误或返回缺失新闻条目时，本次快照不会生成；
看板保留上一份成功快照，并通过 `site/data/sentiment_status.json` 显示更新失败。
密钥文件权限为 `0600`，不会写入仓库。

检查定时器和最近日志：

```bash
systemctl list-timers ai-berkshire-sentiment-update.timer --no-pager
systemctl status ai-berkshire-sentiment-update.timer --no-pager
journalctl -u ai-berkshire-sentiment-update.service -n 100 --no-pager
```
