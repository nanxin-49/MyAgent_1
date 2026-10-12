# A05-P2 正式对照协议 v1（准备完成，正式运行 blocked）

2026-10-12；准备起始HEAD `aba22b2514cf4dd7668c12ed620972ebc708e253`，工作区干净。本轮是A05-P2-GATE，建议verify；整体A05仍partial。协议只设计实验，不下载权重、不安装依赖、不计算语义向量、不执行B1。P1原始数据和报告只读。

## 先决门与审核版本

正式运行当前 **blocked**：用户Gold审核未完成，开发集也待审核，模型下载/依赖安装/计算未获授权，独立环境尚未锁定与smoke验证，可用RAM低于下述暂定预算。模型revision和权重标识已可固定，不能再以main作为运行版本。

用户可接受v1的限定口径，或批准创建v2。gold_review_v1.md是30条作者辅助建议，不是独立人工审核：19合理、10需人工判断、1疑似错误。重点为A05-05未区分快送类型、A05-02可能多来源、A05-03表达不清、A05-19/20的具体事实无答案定义、27–30的当前有效范围。A05-12有完整双事实证据但引文较宽；A05-16可由规则边界支持否定回答，不是Gold缺失。

倾向建议用户批准v2来澄清05/02/03，同时写清无答案的操作定义；**本轮没有修改v1或创建v2**。若用户选择接受v1，要明确单Gold限定和生命周期历史问法的范围，并记录签署者/日期/逐题决定。若改query/Gold/answerable/corpus，创建新dataset/corpus（仅必要时）与freeze，重新B0；不得将P1结果冒充新版本结果。审核签署文件应绑定dataset/corpus SHA256及gold_review_v1.md SHA256，本轮所有决定pending，不自动通过。

## 保持不变的变量

- Corpus `a05-corpus-v1`，SHA256 `f1ca8679113529a54c6cb229f29b669e8e385509e9a08ad6aac8cb8d9d1e6b39`。
- Test `a05-dataset-v1`，SHA256 `e9442c1d8dc6b67784296c94f4ba49619991d7aeb6c0216ff51cd1253413c028`，以及用户最终确认的Gold审核版本。只有明确批准版本变更才能启用新协议/新B0，不能混用v1/v2。
- 生产 `_chunk_text`，500字符目标、无overlap，当前11个物理Chunk/7个有效Chunk；不改变document/version/content/chunk ID或来源。
- 有效时点 `2026-10-12T00:00:00Z`，保留N06 ready、supersedes、expires_at、revoked和旧格式不可用规则。固定时点仅影响隔离评测进程，不能改系统时间。
- Top-K=5（报告K=1/3/5），N07最终证据校验、N06 await后复核与引用hash绑定保持。success=true不是命中。
- Rewrite、LLM Rerank、命中缓存全部关闭。没有生成Agent回答；不测Task Success或模型答复事实正确率。
- 单Gold v1的Recall成功条件及所有分母保持P1口径；有答案21、无答案9。若用户改为多Gold，则先重新定义指标和B0，不能只给B1更宽标签。

## 四个组别

| 组别 | Embedding | 候选与最终阈值 | 用途 |
| --- | --- | --- | --- |
| B0-original | char-bigram-1024-v1 / 1024维 | 固定0.35 | 原P1两轮证据原样保留，作为历史参照；若v2获准则另跑对应B0 |
| B0-calibrated | 同一lexical实现 | 独立16题dev选择阈值，写入锁定calibration.json | 分离阈值影响与向量影响 |
| B1-raw | 推荐BGE；备选另作为预先声明的子组，不看test后换模型 | 原Top5候选，不套lexical 0.35；不据此生成usable/citations | 测检索覆盖/排序能力，不宣称可回答性 |
| B1-calibrated | 与B1-raw完全相同的模型/输入/向量 | 同一dev及同一校准目标 | 最终可用证据、无答案误报与引用精度对照 |

B1-raw仅保存经N06候选来源校验的raw列表。它的“最终可用Recall/MRR、最终无答案FPR、Citation precision”标 **N/A**，因为尚无可用性阈值；可另给raw候选排名MRR及raw非空率，必须显式诊断标识，不能与最终指标混淆。若需要最终结果，看B1-calibrated。所有组均记录raw Recall@1/3/5；B0和calibrated组再记录最终指标。

语义向量维度512或384，不得复用1024维B0 Collection。每个embedding配置/运行使用随机新建专用Chroma HTTP cosine Collection，metadata绑定model_id、revision、权重sha、dimension、pooling、normalization、query/document格式与数据hash。禁止覆盖正常知识集合或P1历史，create-only，结束清理拥有的集合并保存snapshot/cleanup证据。

当前KnowledgeBase直接引用lexical embedding函数且校验embedding_version，不能仅换一个向量文件就运行B1。后续授权后需要**evaluation-only适配器**：在隔离子进程上下文替换KnowledgeBase导入的embedding函数和版本标识，继续复用其原发布/候选/复核代码；不编辑生产模块、N06/N07源码。发布记录向量也使用相同维度，但record_type=publication始终不进入候选。适配器必须验证数据/Chunk IDs相同、生命周期不回归、上下文退出恢复、不能访问业务Collection。阈值通过已允许的实例min_score配置传入，仅作用评测对象；不改环境全局或生产默认。

## 独立阈值开发集及泄漏检查

`dev_dataset_v1.json`：16题（8有答案/8无答案），同一语料与时点，DEV-前缀。正向优先取测试未问属性：异常登录锁定、每天送件时段、改地址条件、基础积累、会员折扣、网络排查、偏远加时、退款金额上限。反向问到期提醒、破损赔付、失去找回渠道后的证件、优惠组合、地址手续费、夜间客服、支付失败冻结、延长换货窗口等正文没有的事实。语言和语义均由作者核对，独立人工审核仍pending。

泄漏规则在运行dev检索前声明：规范化为小写alnum；完全重复禁用；SequenceMatcher(auto-junk关闭)比率≥0.75或字符bigram集合Jaccard≥0.60标高相似，必须人工处理后新版本再冻结。256个dev/test配对检查：0完全重复、0高相似标记；最近配对和数值全部见gate_checks_v1.json。最大sequence ratio约0.432，最大bigram Jaccard约0.192。作者语义复核：DEV-05问折扣而A05-13问门槛，DEV-11问失去找回渠道后的证件而A05-02问一般找回；DEV-16问延长窗口而24–26问现行规则。算法不能证明不存在语义泄漏，不冒充独立人工审核。

虽然问题分离，仍复用同7个有效Chunk与主题；这是小语料内query级泛化，不能宣称文档域外泛化。DEV-04需要简单12×1计算，需用户确认是否允许此确定性一步推导，或在dev新版本改为基础积累比率问题。若用户改v2测试问法，必须重新做与dev的相似/语义检查；若产生冲突，改dev版本，不在看过test结果后挑题。

本轮不运行dev检索、不读取测试结果来选阈值。开发集、校准规则、review辅助材料和资源快照由独立p2_gate_freeze_v1.json绑定，不能动原freeze_v1.json。用户审核通过后再正式锁定calibration产物；如果dev标签变更，也须新版本与新门记录。

## 相同的阈值校准目标

Lexical与Semantic使用同一16题dev、相同cosine score=1-distance、相同Top5/有效过滤与grid `0.00,0.01,…,1.00`；不假设同数值阈值有同等语义置信度。输入格式/pooling按模型要求提前声明，不在这30题上挑选前缀或标题配置。

首要约束：dev无答案误报 **≤1/8（12.5%）**。在满足约束的阈值中，按以下顺序择优：最终Recall@5计数最大 → FPR计数最少 → MRR最大 → Citation precision最大 → 阈值较高。原始分数用完整精度，边界保留score≥threshold，空引用precision=N/A，选择时N/A低于已测值。不能只优化Recall。报告完整101点Recall/FPR权衡表，选定值写入带dev/model/hash的calibration.json，之后测试只执行该值，不根据test成绩调阈值。

若无任何满足约束的阈值，校准为calibration_infeasible，正式可用性对照blocked；不挑更高测试Recall遮蔽失败。若唯一有效策略近乎全部拒答，照实报告Recall=0，不能把低FPR当模型有用。8个无答案的一个错误就占12.5个百分点，此约束是演示决策条件而非统计保证。

`prepare_gate.choose_threshold`只实现DEV-输入的离线算术，有Toy测试验证trade-off；本轮不对真实dev/test分数运行校准。假设候选已通过N06/N07验证，每个可用hit对应一个引用；生产正式复核结果仍需记录，依赖失败degraded单列，不能当拒答正确。

## 模型选择与输入配置

推荐 **BAAI/bge-small-zh-v1.5**：中文用途且官方512维/4层配置；模型包约96.4MB，明显小于E5的492.8MB，更适合当前小型中文CPU实验。理由是语言/资源匹配，不声称其质量更高。E5为多语备用，适合未来跨语言场景；本轮不做两模型挑优。

| 项目 | BGE-small-zh-v1.5 | multilingual-e5-small |
| --- | --- | --- |
| 用途/中文 | 中文dense检索/相似度；模型卡明确Chinese | 多语dense检索，支持中文，模型卡说明100种语言 |
| 许可证 | MIT（官方model card/API） | MIT（官方model card/API） |
| dimension/layers | **512 / 4**，不是英文small常见的384 | **384 / 12** |
| 固定revision | `7999e1d3359715c523056ef9478215996d62a620` | `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| 权重文件 | model.safetensors：95,827,648 bytes | model.safetensors：470,641,600 bytes |
| 权重LFS SHA256（元数据，未下载验证） | `354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026` | `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477` |
| 预选模型文件包 | 96,378,296 bytes / 91.91MiB | 492,795,290 bytes / 469.97MiB |
| Query输入 | `为这个句子生成表示以用于检索相关文章：` + 原query；官方v1.5允许不加，本实验预先选加指令 | `query: ` + 原query；中文也使用英文前缀 |
| Document输入 | title + 换行 + 原chunk，不加query指令 | `passage: ` + title + 换行 + 原chunk |
| Pooling | 最后隐状态首token CLS | attention_mask加权mean，排除padding |
| 归一化 | L2 | L2；不使用示例展示的×100缩放 |
| 最大tokens | 512 | 512 |

以上大小来自官方Hub API的固定revision文件size/LFS sha，只读取JSON metadata/config，未获取任何权重或tokenizer大文件。包只选择一份safetensors，不含重复pytorch_model.bin、ONNX/OpenVINO、README/训练文件；明细见model_resources_v1.json（E5含tokenizer JSON及sentencepiece字典，以便明确依赖/加载选择）。下载后必须计算实文件sha，不能把API hash误称已经验证的本地hash。

官方来源：

- [BGE模型卡](https://huggingface.co/BAAI/bge-small-zh-v1.5)、[固定config](https://huggingface.co/BAAI/bge-small-zh-v1.5/resolve/7999e1d3359715c523056ef9478215996d62a620/config.json)、[固定Pooling](https://huggingface.co/BAAI/bge-small-zh-v1.5/resolve/7999e1d3359715c523056ef9478215996d62a620/1_Pooling/config.json)、[固定文件元数据](https://huggingface.co/api/models/BAAI/bge-small-zh-v1.5/revision/7999e1d3359715c523056ef9478215996d62a620?blobs=true)。
- [E5模型卡](https://huggingface.co/intfloat/multilingual-e5-small/raw/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)、[固定config](https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json)、[固定Pooling](https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/1_Pooling/config.json)、[固定文件元数据](https://huggingface.co/api/models/intfloat/multilingual-e5-small/revision/614241f622f53c4eeff9890bdc4f31cfecc418b3?blobs=true)。

语义文档标题只出现一次，lexical保持原6倍title特征；这是各embedding的预先声明输入方法差异，不能将结果解释成仅神经权重的孤立因果效果。若未来要消除title格式影响，另开受控实验，不用test选择。两候选均float32、CPU、eval/inference mode、batch=1、threads=4、关闭dropout，记录随机种子。tokenizer先对冻结所有文本检查长度，超过512不允许静默截断，正式运行blocked并报告；不能偷偷改Chunk或丢掉Gold。

## Python、内存与磁盘

可采用独立Python3.12 CPU虚拟环境，建议直接torch + transformers + safetensors + tokenizers + huggingface-hub及必要传递依赖，按官方Pooling实现，不必安装Sentence Transformers整套。若选Sentence Transformers，固定相应版本及模块配置，不使用它的默认前缀猜测；E5慢tokenizer可需sentencepiece/protobuf，fast tokenizer选择和实际依赖在环境锁中写明。

本轮读取PyPI JSON：torch 2.14.1有cp312/win_amd64 wheel，transformers 5.19.0有py3 universal wheel；safetensors 0.8.0、tokenizers 0.23.3有cp310-abi3/win_amd64 wheel，可覆盖CPython3.12。它们只是核查时版本，不是已经验证的组合/最终安装锁。PyPI requires_python均覆盖3.12；[PyTorch Windows说明](https://pytorch.org/get-started/locally/)涵盖3.12，[Sentence Transformers安装说明](https://sbert.net/docs/installation.html)提供相应框架要求。旧model config的transformers_version是保存时版本，不是Python3.12的兼容性保证。授权后先在独立环境解析完整依赖锁、CPU wheel来源和sha，完成小样本smoke后再正式运行；不能直接改项目pyproject/uv.lock。

本机Python3.12.3、16逻辑CPU，总RAM约15.25GiB，核查瞬间可用约2.93GiB，E盘空闲约165.94GiB；当前项目环境未装torch/transformers/safetensors/tokenizers/huggingface-hub，配置/默认HF缓存未发现两个模型。仅查指定缓存，不宣称全磁盘没有模型；未加载模型。

官方资料没有给出这台机器CPU peak RSS或硬性最低内存，**实际最低/峰值内存与延迟未知**。fp32 tensor载荷约对应上述95.8/470.6MB权重大小，不能把权重大小当总进程内存。临时工程预算（待用户确认、非官方最低要求）：BGE先预留≥4GiB可用RAM和≥6GiB自由磁盘；E5先预留≥6GiB可用RAM和≥6GiB磁盘。磁盘预算覆盖模型、依赖展开、下载缓存及报告，实际依赖总量未解析。当前空闲磁盘够该预算，可用RAM不够，运行前重新检查，不关闭用户应用或自行改变资源设置。CPU实验无需GPU授权；若改GPU、batch、精度或线程，应新协议预先声明。

## 正式采集与指标

每组必须记录commit/dirty、输入与审核sha、模型revision/实文件sha、依赖锁、时间、collection/config、线程/batch/精度、实际维度、prefix/pooling、token长度、有效Chunk IDs、重复发布/重复运行一致性。至少两轮，同一题同组的重复不能扩大统计样本量；第一次冷读、后续暖读分别报告。

每题保存全部raw候选的rank/score/来源/hash/Chunk ID、最后hits/citations/status、Gold定位、失败原因、Query embedding计算时间、Chroma与N06/N07总体检索时间、实际vector query/handler次数、模型forward次数（Publication/文档预计算与Query分开）、本地Token数量（如果tokenizer可观测）、模型API调用次数与费用。无外部API时API调用/费用0，不能说本地计算免费；CPU time/电力/货币成本未测则N/A，不能估算成实测。

模型加载和文档预计算单独计时，P50/P95 query embedding时间与端到端检索时间分开。端到端定义与P1一致，包含N06快照和最终证据复核；对失败请求也计耗时。记录进程基线RSS、模型加载后RSS、采样peak RSS（标明采样间隔与可能漏峰）、CPU time、磁盘缓存/权重/环境实际大小、服务/进程资源范围；无法测则N/A，不用权重大小替代。P1缺这些分项，B0-original相应项N/A，不能补造。

| 指标 | 分母与成功条件 |
| --- | --- |
| 原始候选Recall@1/3/5 | 21条正向，Gold进入经生命周期校验的原排序前K；低分也计候选诊断 |
| 最终可用Recall@1/3/5 | 21条正向，Gold进入最后非空usable证据的前K，失败/缺失=0 |
| 最终MRR | 21条正向，累加1/最终Gold排名；缺失=0，Top5截断 |
| 无答案FPR | 9条无答案，最终usable且非空hits/citations的题数/9；degraded单列，不当正确拒答 |
| Citation evidence precision | 支持对应Gold事实的引用数/所有发出的引用数，包括无答案错误引用；0引用=N/A |
| P50/P95 | 每轮实际墙钟样本，(n-1)*q线性插值；计算分项与总体分开 |
| 调用/Token/成本/资源 | 上述真实可观测计数；缺测=N/A；不把NoModel/Fake输出当质量 |

对B0-original→B0-calibrated与B0-calibrated→B1-calibrated，逐题分别记录final Recall@5从0→1为改进、1→0为退化、相同为无变化；另列rank变化、无答案误报消除/新增、引用精度变化和资源开销。没有测试统计显著结论；不能仅更高Recall就宣布更好。FPR超出开发约束或测试误报恶化也必须展示。固定测试质量不足或资源/版本不可复现时，正式结果保持blocked。

## 本轮验证与后续授权

运行新增审核/开发集/泄漏/校准算术的确定性测试；不触发模型或Chroma。原freeze/dataset/corpus与P1目录保留原字节。完整pytest必要时跑常规Fake/opt-in跳过路径，uv lock和diff检查照常。具体结果记录gate_validation_v1.json，不修改P1 validation。

下一轮需用户明确：逐题Gold/无答案范围与v1或v2决定；开发集接受；选定BGE revision的约96.4MB文件包下载、独立Python3.12 CPU依赖安装与锁定（完整大小待解析）；释放/提供暂定≥4GiB可用RAM、≥6GiB磁盘及限定CPU计算；适配器smoke与正式对照执行范围。备选E5与付费API不自动获得授权。

独立练习（**Toy分数，不是检索测量**）：两条正向Gold分数为0.60、0.40，一条无答案最高分0.50。试阈值0.30、0.50、0.70，分别手算Recall和FPR，说明为什么只选最高Recall会选到100%误报；若约束FPR=0，哪一个有非零Recall的阈值更合适？再解释为什么这个阈值不能直接从Toy迁移到30题测试集。
