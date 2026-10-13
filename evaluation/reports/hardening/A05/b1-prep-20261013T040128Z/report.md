# A05-B1-PREP：资源门阻塞记录

2026-10-13；HEAD `eb55ae85532100829f7f8dd92d6a8c4813f6572c`，起始工作区干净。本轮用户有条件批准B1-PREP，未批准开发校准或正式B1。A05整体doing/partial；B1-PREP blocked/partial；B1正式实验blocked/not_started。没有提交或推送。

## 资源门槛与停止位置

北京时间2026-10-13 12:01:28，使用Windows `GlobalMemoryStatusEx`和`shutil.disk_usage`实测：

| 项目 | 实测 | 用户要求 | 结果 |
| --- | --- | --- | --- |
| 可用物理内存 | 1,857,789,952 bytes = 1.7302 GiB | 至少4 GiB | **未通过** |
| 总物理内存 | 15.2458 GiB；系统内存占用88% | 非门槛 | 背景信息 |
| E盘可用空间 | 177,984,860,160 bytes = 165.7613 GiB | 至少6 GiB | 通过 |
| CPU / 现有解释器 | 16逻辑CPU / Python3.12.3 | 独立环境使用Python3.12 | 独立环境尚未创建 |
| 本阶段新增网络下载 | **0 bytes** | 不超过1 GiB | 未发生下载；完整依赖预算尚未解析 |
| Embedding进程峰值内存 | N/A，未启动Embedding进程 | 暂按2 GiB预算 | 未验证，不能称预算已通过 |

资源门在安装、环境创建和模型加载之前失败。依照本次用户指令立即停止这些阶段；没有通过重试、换存储、低精度、减少线程或终止其他程序绕过门槛。只有核验报告和已有Workbench/progress状态记录继续完成。完整原始观测见resource_gate.json。

## 模型与环境交付状态

指定`BAAI/bge-small-zh-v1.5`，revision `7999e1d3359715c523056ef9478215996d62a620`，权重`model.safetensors`，预期SHA256 `354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026`。这是用户给定的预期hash；没有下载或检验本地权重，不冒充实际文件校验通过。

- 独立环境、完整精确依赖锁和wheel hashes：**未创建**。
- 完整新增下载预算：**未解析/未验证**；不能将模型大小当完整环境下载量。
- 模型本地SHA256与离线加载：**未执行**。
- CPU-only/FP32/batch1/threads4/CLS/L2/512维/Query指令/标题一次+换行+正文/512-token硬限制：用户协议已收到，**未实现或运行**。
- 禁止CUDA、付费模型和trust_remote_code的边界保持；没有模型推理。
- 模型加载耗时、单条编码耗时、模型实际CPU时间和Embedding峰值内存：**N/A**；不以资源检查脚本耗时替代模型测量。

## Smoke逐项状态

| 用户验收项 | 状态 | 原因 |
| --- | --- | --- |
| 1 指定本地权重离线加载 | not_run | 首个资源门未通过 |
| 2 维度、FP32、归一化范数 | not_run | 未启动模型 |
| 3 相同输入重复编码容差 | not_run | 未启动模型 |
| 4 冻结Chunk仅token长度检查 | not_run | 未准备tokenizer；没有读取冻结问题进行编码 |
| 5 独立cosine集合合成发布/检索 | not_run | 未启动模型；本轮0次Chroma调用 |
| 6 publication/chunk同维、publication不进入候选 | not_run | 未创建集合或适配器 |
| 7 版本、正文hash、有效性与引用 | not_run | 未进入smoke；不使用旧回归冒充新语义验证 |
| 8 临时集合完整清理 | not_applicable | 本轮创建0个集合，无本轮集合需要清理；不能称清理smoke已通过 |
| 9 时间、峰值内存和资源异常 | partial | 已记录启动前内存不足；模型性能/峰值尚未测量 |

## 变更、回归与保留边界

新增本目录资源JSON、只读门槛检查脚本、报告和validation；更新既有Workbench/progress中的A05-B1-PREP阻塞记录与授权范围。生产调用路径没有改变；未建立新进度系统。

原pyproject.toml、uv.lock、Embedding、KnowledgeBase、Policy/Skills、冻结Gold及B0历史文件应保持原hash，最终保护检查见validation.json。本轮没有Chroma调用，不触及默认业务库、词法集合或其生命周期；没有再次验证实时服务快照。默认业务库publication缺失和Answerability仍是独立待办，不混入B1。

**完整pytest回归未运行**：资源门失败且没有进入环境/模型/适配器实现，本轮不再启动测试负载。没有将历史466 passed或上轮smoke建议当作本轮结果。仅进行证据JSON解析、原文件hash保护、工作台状态一致性和git diff --check；结果在validation.json。

B1-PREP不能标verify，因为环境、依赖锁、权重校验及必要smoke均未完成。B0-calibrated原verify/待人工验收状态保持；本轮授权不等于其最终验收。

## 最小解决方案与独立练习

由用户自行释放部分应用内存或选择其他执行时段，使可用物理内存达到**至少4 GiB**（该观测距离门槛约差2.27 GiB）；本助手不会自动结束进程。达标后先重新检查资源门，再恢复本次有条件B1-PREP，安装前解析完整CPU-only依赖/wheel来源及hash并计入累计下载预算；超过1 GiB时仍须停止。加载前再次核验内存，smoke期间按2 GiB峰值预算监测和安全停止。

独立练习：在项目根目录运行以下只读脚本，比较available_ram_GiB与4；exit code 2表示资源不足，0仅表示当前内存/磁盘门通过，不授权或自动触发安装：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe .\evaluation\reports\hardening\A05\b1-prep-20261013T040128Z\check_resource_gate.py
```

只有B1-PREP全部必要项通过后才能推荐verify；开发校准与正式B1仍等待另行授权。建议提交信息（不执行）：`docs(eval): record B1 prep resource gate blocker`。
