# A05-P2-DEV-CAL — 仅开发集的Lexical阈值校准

2026-10-13；起始HEAD `4685741e3fcdde23c3646afc48754d5196aa6f8e`，工作区干净。用户验收Gold v2及B0-original后仅授权dev16题校准。结果implemented，建议verify；整体A05仍doing/partial，B1 blocked。本轮没有用30题test观测调参、没有执行test B0-calibrated、没有改生产默认0.35，也没有模型下载/依赖安装/付费调用/提交推送。

## 调用路径与冻结边界

现有runner增加 `--split dev`（默认仍test），必须显式 `--dataset-version v2`：

```powershell
uv run python -m evaluation.rag_quality.run_baseline --dataset-version v2 --split dev --host 127.0.0.1 --port 8001 --repeats 2
```

dev专用loader只解析corpus_v1和dev_dataset_v2，通过freeze_v2检查所有绑定文件hash、批准状态、dev版本/Gold/8+8分母及as_of；test文件只做字节hash，不解析测试问题或测试分数，不复制到dev报告目录。错误版本、缺失/hash/审批/分母/Gold不一致均fail closed。v1/v2测试入口兼容保持。旧B0报告仅核对manifest/验证范围和文件hash；兼容性pytest可以审查历史证据，但校准选择器只接收DEV行。

复用同一个真实Chroma HTTP采集流程：随机create-only集合→原KnowledgeBase发布→N06有效候选→Top5召回→原0.35结果作为dev参考；同时捕获原始HTTP distance和全部低分候选，不在采集时丢弃。每题记录rank、score、score_kind、Chunk ID/document/version、有效性、Gold匹配与answerable。两轮候选一致，16题每轮分别计数，不能合成32独立样本。

离线重放在核验前后相等的真实HTTP publication/chunk snapshot上运行**原生产build_hit、N06 `_eligible`/`validate_hits_async`、N07 `_finalize_rag`**。仅copy评测KB实例的_snapshot读取函数，使用固定捕获快照；不修改生产源码，不生成Fake检索排名/分数。保留实际distance再次build_hit，不用1-score重建distance；0.35重放的hits/citations/status/Gold rank必须与真实采集逐题相同。snapshot存档hash绑定，重放不能用于绕过未来线上退役。

11物理Chunk、7有效Chunk、500字符目标切分、as_of=2026-10-12T00:00:00Z、char-bigram-1024-v1/1024维、Top5均不变。Rewrite/Rerank/Cache关闭，模型调用0。N06/N07和其他业务路径未改变。

## 评分和选择口径

score_kind=`one_minus_chroma_distance`，score严格等于1−实际Chroma distance，高分通过；保留score≥threshold。集合配置hnsw:space=cosine，但不把该启发式值自动解释为概率或跨后端标准余弦相似度。实测分数包含负数，范围约[-0.0115286,0.337441]，没有裁剪。

沿用已冻结协议的101点grid0.00–1.00步长0.01，包含0.35；这也是现有KnowledgeBase.min_score允许的参数范围，**不是假定所有score位于[0,1]**。实际dev分数通过完整契约重放决定每点结果，本轮不根据test分数添加阈值。浮点采用原始IEEE754 double，无四舍五入比较/epsilon。0.20的精确hex为 `0x1.999999999999ap-3`。

选择：先FPR≤1/8，再最大最终Recall@5计数；并列依次FPR计数最少→MRR最大→引用精度最大（用未舍入的分子/分母，N/A最后）→较高阈值。没有结果后改变规则。正向仅认原Gold，负向任何不充分但usable的引用即误报；degraded不能当正确拒答，当前重放若degraded即阻断校准。

## 实测结果

新独立目录 `evaluation/rag_quality/calibration/20261013T025559Z-ed4a1cb4/`；真实Chroma client/server0.5.23，Python3.12.3，代码/依赖/时间/hash见manifest及锁记录。两轮各16 handler/vector query，共32；原候选/曲线一致，Collection已清理，重复发布和查询前后snapshot一致。进程NO_PROXY只绕过本机地址。

原始候选Recall@1=7/8，@3/@5=8/8；raw MRR=.9167。它包含低分候选，不等于可用证据。

| dev指标 | 原0.35 | 锁定0.20 |
| --- | --- | --- |
| 最终Recall@1/3/5 | 均0/8 | 均2/8=25% |
| MRR | 0 | .25 |
| 无答案FPR | 0/8 | 1/8=12.5% |
| 引用精度 | 0引用，N/A | 2/3≈66.67% |
| 正确拒答（负向无最终证据） | 8 | 7 |
| 无返回（全部查询的最终证据为空） | 16 | 13 |

正确Gold为DEV-02与DEV-07；误报为DEV-16。阈值0.17仍2个无答案误报；0.18/0.19/0.20各2个Gold、1个误报，所有目标指标并列，按最后tie-break选0.20。DEV-14最高分约.177942、DEV-02 Gold约.202336、DEV-07 Gold约.241456解释该平台。0.21会丢DEV-02，Recall只1/8。选定后配置锁定，不等正式测试结果再改。

完整101点CSV和两轮JSON曲线均提供Recall@1/3/5、MRR、FPR/误报数、引用精度、正确拒答及最终无返回数量。开发集空候选与最终空证据不同；本次每题都有5个原始候选。0.35在dev上全拒答，不能因为FPR=0就称好。

真实采集0.35的P50/P95：首轮26.17/34.58ms，次轮27.65/31.66ms。选定0.20是离线重放，**没有测其在线HTTP延迟**；重放latency不作为性能。模型API/Token/API费用0，本机资源/电力成本未估算。

## 校准锁与历史保护

- `b0_lexical_dev_v2_observations.json` SHA256：`31a70535aea795466c09948ba652f550474f778e2efda26c9b7a4ffa2c29859a`。
- `b0_lexical_threshold_sweep_v2.csv` SHA256：`f39a22e47582240542e42c2e5f2879f978ab64a4d0e27cc0a0d9bf86a68c5bfb`。
- `b0_lexical_calibration_v2.json` SHA256：`c65630d00d33e51d345b2fb94982b24331e7385d05195ec2c34eaf213fc84ad2`。

锁JSON绑定corpus/dev/freeze hash、观察/曲线/snapshot hash、代码/依赖、score_kind、方向/边界、grid/目标/tie、Top5、时点、最终指标和threshold=0.20。只标开发校准locked，不表示测试集/生产验收。旧正式数据、候选、审核、协议及所有旧报告不改；旧v2 runner按其原manifest hash精确归档为history/run_baseline_before_dev_cal.py.txt，旧v1源码归档也保留。新模块只用于同一runner的开发重放，不另建检索系统。

## 测试与DoD

专项（dev校准+v1/v2兼容+数据/原指标+N06/N07）173 passed；完整pytest466 passed/3 skipped/1既有AnyIO警告。默认skip仍为live Memory和2条HTTP opt-in；本轮实际dev质量采集是独立真实HTTP，并非Fake。Toy测试只验证边界/选择算术，不冒充模型效果。uv lock --check53 packages、git diff --check通过（Git LF/CRLF提示不是空白错误）。

新增测试覆盖错误版本/冻结hash、只解析dev、8/8分母、原始double边界与nextafter、负分/大于1不裁剪、FPR优先/最高Recall/全部tie、无Gold不算正向、退化全拒/无可行阈值、重复不扩分母、N06退役和内容hash、真实dev锁/101点/两轮一致。验证命令和历史hash在新validation.json。所有DoD限定为开发校准，test B0-calibrated未执行。

## 风险与下一轮

0.20不是零Recall退化方案，但仍漏6/8正向、13/16最终无证据。DEV-16主题相关度最高却没有付费延长规则；阈值不能识别所问事实缺失。仅8个无答案，每个错误占12.5%，满足dev约束不保证测试或生产FPR；共用小语料不代表域外泛化，更不证明答案完整性。

用户验收后需另行授权正式test一次性评测。下一轮给runner最小增加显式锁配置加载，验证此JSON hash及模型/输入/score/Top5/as_of绑定，仅隔离实例设min_score=.20；对同v2的30题运行一次B0-calibrated，保存新报告并对照已验收同v2 B0-original。好坏都不反改阈值，额外开发实验应新版本。当前没有实现/执行该测试配置入口，不能直接给现有命令添加未存在的参数。

只更新原Workbench/progress：已验收B0-v2 done/measured，DEV-CAL verify，A05 partial，B1 blocked。README/核心Wiki生产调用路径无变化，不需改写；旧协议过去的pending/未执行段落属于历史，当前状态以工作台为准。

独立练习：用CSV比较0.17的Recall2/8但FPR2/8与0.18–0.20的平台，按约束和tie-break选0.20；解释为什么不能拿开发集25%直接宣称测试集改善。

建议提交：`eval(rag): calibrate lexical threshold on frozen dev v2`。停止等待验收，不进入test/B1。
