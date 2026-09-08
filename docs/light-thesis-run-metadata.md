# 本地轻量复核批次操作记录

未来获准正式运行时，先确认客户端模型及推理档位，再运行 start。
以下为用法示例，不代表已经执行，也不能补填为 Phase 7.4 的历史证明。

```bash
python3 tools/light_thesis_run_manifest.py start --run-id example-batch --model gpt-5.6-luna --reasoning-effort high --eligible 2
python3 tools/light_thesis_run_manifest.py complete --run-id example-batch --success 2 --failed 0
```

eligible 必须使用本次实际集合数量。reasoning-effort 必填；无法读取客户端配置时，
要求运行者明确声明实际档位。记录标注 operator_declared，不冒充 provider 回执。
工具不会调用模型或读取、更改客户端配置。

记录保存在 logs/light-thesis-runs/ 下的独立 started/completed JSON。
开始记录保存开始时间和当时 authority SHA；结束记录沿用已声明模型/档位并记录
完成时间、成功/失败数量和结束时 authority SHA。success+failed 必须等于 eligible；
中断且未完成的批次保留 started 文件，不伪装为完成。相同文件禁止覆盖。

记录不被 builder、signal identity 或 evidence fingerprint 读取，不扩展 authority。
该工具只能证明操作声明及文件 SHA，不能独立证明模型实际执行或每条结果来源。
