"""Offline comparison and report generation; no retrieval or threshold selection."""
import csv
import json
from collections import Counter
from pathlib import Path
from evaluation.rag_quality import run_baseline as b

OUT = Path(__file__).resolve().parent
OLD = b.ROOT / 'evaluation/reports/rag_quality/v2/20261012T165114Z-945bd721'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def md(text):
    return str(text).replace('|', '\\|').replace('\n', '<br>')


def main():
    rows = read(OUT / 'observations.json')
    cases = read(OUT / 'dataset_v2.json')['cases']
    old_rows = read(OLD / 'observations.json')
    manifest = read(OUT / 'manifest.json')
    summary = read(OUT / 'summary.json')
    check(manifest['outcome'] == 'measured' and manifest['collection_deleted'], 'formal run not complete')
    check(len(rows) == len(cases) == 30 and len({r['case_id'] for r in rows}) == 30, 'denominator mismatch')
    check(summary == b.aggregate(rows), 'metrics differ from recomputation')
    signature = lambda row: [(h['frozen_chunk_id'], h['score']) for h in row['candidates']]
    for repeat in (1, 2):
        group = [r for r in old_rows if r['repeat'] == repeat]
        check(all(r['case_id'] == o['case_id'] and signature(r) == signature(o)
                  for r, o in zip(rows, group)) and len(group) == 30, 'original candidate rankings/scores differ')
    old_group = [r for r in old_rows if r['repeat'] == 1]
    original_summary = read(OLD / 'summary.json')['1']
    check(original_summary == b.aggregate(old_group), 'original metrics not reproducible')
    comparisons = []
    for case, row, old in zip(cases, rows, old_group):
        gold = next((h for h in row['candidates'] if h['frozen_chunk_id'] == case['gold_chunk_id']), None)
        check(all(h['valid_at_as_of'] and h['score'] == 1-h['raw_distance'] for h in row['candidates']),
              'candidate validity/distance mismatch')
        if case['answerable'] and not row['gold_rank']:
            if gold is None:
                category, note = '原始候选未召回', '冻结有效Gold未进入Top5；不能归因为阈值过滤。'
            else:
                check(gold['score'] < .20, 'Gold vanished without score explanation')
                category, note = '正确候选被分数过滤', f"Gold在raw rank={row['diagnostic_candidate_gold_rank']}，score={gold['score']!r}<0.20；有效性校验通过。"
        elif row['false_positive']:
            category = '无答案问题错误判为usable；片段事实不足'
            note = case['annotation_reason']
            if case.get('excluded_evidence'):
                note += ' 返回的是现行demo-v2换货片段，无该题所问事实；不是被排除版本泄漏。'
        else:
            category, note = '通过', ('冻结Gold在最终rank1。' if case['answerable'] else '最终无证据；正确拒答。')
        comparisons.append(dict(case_id=case['case_id'], query=case['query'], answerable=case['answerable'],
            old_gold_rank=old['gold_rank'], new_gold_rank=row['gold_rank'],
            old_status=old['retrieval_status'], new_status=row['retrieval_status'],
            raw_gold_rank=row['diagnostic_candidate_gold_rank'], gold_score=gold['score'] if gold else None,
            failure_category=category, explanation=note, gold_issue='未发现新标签冲突；沿用已批准冻结口径',
            old_false_positive=old['false_positive'], new_false_positive=row['false_positive']))
    gained = [r['case_id'] for r in comparisons if not r['old_gold_rank'] and r['new_gold_rank']]
    added_fp = [r['case_id'] for r in comparisons if not r['old_false_positive'] and r['new_false_positive']]
    failures = dict(Counter(r['failure_category'] for r in comparisons if r['failure_category'] != '通过'))
    snapshot = read(OUT / 'n06_snapshot.json')
    default = read(OUT / 'default_snapshot_formal.json')
    corpus = read(OUT / 'corpus_v1.json')
    common_equal = {v[0] for v in default.values()} == {
        d['content'] for d in corpus['documents'] if d['source'].startswith('demo:cartcare-default')}
    comparison = dict(comparable=True, old_run=str(OLD.relative_to(b.ROOT)),
        same_test_gold_corpus_hashes=True, candidate_rank_score_identical_to_both_original_repeats=True,
        same_metric_functions=True, threshold_only_quality_difference=True,
        original=original_summary, calibrated=summary, per_case=comparisons,
        gained_gold_cases=gained, added_false_positive_cases=added_fp, failure_counts=failures,
        validity_filtered_gold_cases=[], newly_confirmed_gold_label_errors=[],
        default_body_texts_equal_frozen_six=common_equal,
        limitations=['单Gold、固定时点、21/9小样本、共享小语料；非生产或统计显著结论',
                    '没有生成答案；usable误报不等于观察到了LLM错误回答',
                    '拒答指标只按最终无证据；不把调用成功当命中',
                    '新运行有7次预检vector probe，延迟不与原运行作因果解释'])
    b.write_json(OUT / 'comparison.json', comparison)
    with (OUT / 'per_case.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    lines = ['# A05 B0-calibrated：逐题检索与归因', '',
        '此表沿用已批准Gold；分析不产生新的人工批准或修改标签。完整raw/final内容、distance、metadata、hash、citation见observations.json。', '',
        '| 题号 | Query | raw Gold排名 | Gold分数 | 0.35→0.20最终Gold排名 | 0.35→0.20状态 | 归因 |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for r in comparisons:
        lines.append('| ' + ' | '.join(md(x) for x in (r['case_id'], r['query'], r['raw_gold_rank'],
            r['gold_score'], f"{r['old_gold_rank']}→{r['new_gold_rank']}",
            f"{r['old_status']}→{r['new_status']}", r['failure_category'])) + ' |')
    for case, row, c in zip(cases, rows, comparisons):
        lines += ['', f"## {case['case_id']}：{case['query']}", '',
            f"- 人工审核来源：freeze_v2.review 的全集用户批准（2026-10-13），非新增逐题签署。",
            f"- answerable={case['answerable']}；Gold Chunk={case['gold_chunk_id']}；Gold evidence={case['gold_evidence']}",
            f"- 归因：{c['failure_category']}。{c['explanation']}",
            f"- Gold/业务口径：{c['gold_issue']}。",
            f"- annotation_reason：{case['annotation_reason']}", '',
            '| Raw rank | Document/version | Chunk ID | score（完整double） | 状态 | content_hash |',
            '| --- | --- | --- | --- | --- | --- |']
        for h in row['candidates']:
            lines.append('| ' + ' | '.join(md(x) for x in (h['rank'],
                f"{h['document_id']}/{h['policy_version']}", h['frozen_chunk_id'], repr(h['score']),
                h['retrieval_status'], h['content_hash'])) + ' |')
        lines += ['', '最终引用：' + json.dumps(row['citations'], ensure_ascii=False), '',
                  '最终片段正文：' + ('<br>'.join(h['content'] for h in row['hits']) or '无')]
    (OUT / 'per_case.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    report = '''# A05 B0-calibrated 核验与正式测试

2026-10-13（Asia/Shanghai）；HEAD `8cefc6c3e24230177c1db6dbb54f2e45f1c86f23`，起始工作区干净。A05继续doing/partial；本阶段measured/verify，待人工验收。没有启动B1、提交或推送。

## 前置核验与隔离

真实Chroma HTTP `127.0.0.1:8001`，Compose映射容器`chromadb:8000`到主机8001，client/server 0.5.23。旧B0-v2临时集合已删除，本轮从原冻结语料create-only新建随机集合；默认集合始终通过get_collection只读。预检和正式测试各自创建/删除独立集合，名称、清理证据在两个preflight JSON和manifest内。

评测集合：11 ready publication + 11物理chunk，固定`2026-10-12T00:00:00Z`有效7个；全部chunk正文SHA256匹配metadata，publication revision/片段IDs/生命周期通过N06。完整publication/chunk快照与开发校准snapshot结构完全一致；原B0-v2全部chunk正文、ID、hash和7个有效ID相同。实际存储float32向量逐元素匹配char-bigram-1024-v1；7次HTTP自检向量查询均rank1。预检不使用测试Query。正式前再次核验；查询及重复发布均不改变快照。

默认业务集合另有6条旧格式记录：0 publication、0有效chunk、6条都缺content_hash，实际search报`legacy knowledge requires reviewed republication`。6篇正文与冻结语料中的6篇默认资料完全相同，但存储生命周期状态不同；评测有效性不能转移为默认业务库有效性。隔离评测并不要求默认库迁移，本轮没有修改它。前后默认snapshot相同；这是独立发现的默认库阻塞问题，应另行审核后重发布，本轮不执行。

## 冻结、审核与可复现性

corpus SHA256 `f1ca8679113529a54c6cb229f29b669e8e385509e9a08ad6aac8cb8d9d1e6b39`；test `c5eefac673cd34529793d83bb860fbb07ef5393507c99652dfe4eef2e76a0818`；dev `e49037acd561248f93b5e72ce23ab1d20b3fed1b9d7910b2ba8448f64d9fb002`；freeze `7ea0b1c40d430de13fead53ed1f21af082410efc7c0cdf6bb967c22030524f79`。所有冻结文件（含Gold review/diff）与原B0-v2报告字节hash相同，30题Gold标签逐条与freeze相等，正式cases与获批candidate相等，候选hash也不变。21有答案/9无答案，分层10/8/5/7不变。

freeze_v2.review保存用户原授权“我已核对 A05 Gold v2 候选版及逐项差异，批准按当前候选内容正式冻结 v2。”这是对完整候选的人工批准，不是Codex本轮自动认定通过；非独立双人、非完全盲审、没有额外逐题独立签名。原gold_review_v2.md的pending属于批准前历史；不改历史，当前批准以正式freeze为准。附per_case.md/CSV便于再次逐题检查，但本阶段人工验收仍待完成。

开发锁SHA256 `c65630d00d33e51d345b2fb94982b24331e7385d05195ec2c34eaf213fc84ad2`，0.20精确hex `0x1.999999999999ap-3`，绑定dev/corpus/freeze、原始开发观测、曲线、快照、协议及代码/依赖。逐项重新验证，没有重新选择阈值。Python3.12.3/uv.lock及全部锁定包版本一致。源代码hash与开发锁完全一致；原B0 runner归档hash匹配原manifest，10个发布/数据校验/检索/指标函数AST与当前runner完全相同。新的独立脚本仅编排核验及显式设置隔离实例min_score，并调用原retrieve_b0/observe/aggregate；未编辑原runner或生产路径。

所有原tracked文件运行前后hash一致，完整列表见protected_inputs.json；正式报告保留原输入字节、脚本及实现hash、时间、dirty、服务版本、快照、逐题结果。只新增独立报告与更新已有Workbench/progress。普通沙箱目录/文件写入被Windows拒绝后通过自动审批的授权执行保存；未发生正式测试失败或重跑。

## 正式结果与对照

真实HTTP仅一次30题；char-bigram-1024-v1/1024维、title boost6、Top5、0.20、固定时点、Rewrite/Rerank/Cache/LLM关闭。NoModel sentinel阻断模型路径；每题1 handler/1 vector query，30次测试vector query、7次正式前probe单列（预检另7次）；模型调用/token/API费用0，本机资源/电力费用未测。生产默认阈值仍0.35。

| 指标 | 原0.35 B0-v2 | 锁定0.20正式测试 | 差异 |
| --- | --- | --- | --- |
| Recall@1/3/5 | 均6/21=28.57% | 均9/21=42.86% | +3题，+14.29个百分点 |
| MRR | 6/21=0.2857 | 9/21=0.4286 | +0.1429 |
| 无答案FPR | 4/9=44.44% | 8/9=88.89% | +4题，+44.44个百分点 |
| 引用证据精度 | 6/10=60% | 9/17=52.94% | -7.06个百分点 |
| raw Recall@5（诊断） | 18/21=85.71% | 18/21=85.71% | 不变 |
| 正确无答案拒答 | 5/9 | 1/9 | -4题 |
| 最终无返回 | 20/30 | 13/30 | -7题 |

新运行17 usable/13 low_confidence，全部success=true；9个正确Gold全在最终rank1，所以各K与MRR相等。引用分母17包括8个无答案误报；不把主题相关度当事实充分性。没有生成Agent回答，不能把usable误报说成已观测的LLM错误答复。

逐题raw候选ID/顺序/完整double分数与原0.35两轮全部相同；数据、Gold、chunk、生命周期、源代码语义、指标协议、依赖/服务版本可比，唯一质量处理差异为0.35→0.20。新增正确13/14/15（会员门槛、运费门槛、物流更新），新增误报27–30。没有原正确变错；4个旧误报19/20/21/23仍保留。开发FPR1/8不能转移到测试8/9。

延迟见summary：包含Embedding、HTTP召回/快照及N06/N07最终复核，排除启动/发布/probe。新运行先做过vector probes，机器时间/负载也不同；延迟差异不能解释为阈值因果收益，不声称冷启动性能。

## 逐个失败归因

全部30题的原始Top5、分数/版本/hash、最终引用正文、Gold和注释见per_case.md与observations.json；CSV方便人工筛选。20个失败分别如下。

| 类别 | 样本 | 证据与含义 |
| --- | --- | --- |
| 原始候选未召回 | 01/05/06，共3题 | 正确有效Gold未进Top5，降阈值无法补回；包括口语退款、快送及积分折抵 |
| 正确候选被分数过滤 | 02/03/04/07/08/09/10/12/17，共9题 | Gold已进Top5且有效，但score<0.20；本轮0题因有效性条件剔除Gold，不混同分数问题与生命周期问题 |
| 相关片段事实不足，且无答案误判usable | 19/20/21/23/27/28/29/30，共8题 | 以下逐题指出缺失事实；该原因与“误判usable”重叠，不能相加当16题 |

19：退款政策没有到账天数且明示不承诺渠道时效。20：账户指南只说用户开启两步验证，未给客服关闭权限/流程，不能从未说明推导禁止。21：订单查询指南不含ORD-999实时位置，动态事实须Provider。23：消费升级门槛不是金卡年费。27：现行demo-v2换货片段没有被替代demo-v1寄回地址。28：现行v2没有未来v3的指定承运人。29：现行换货片段没有过期优惠券口令。30：现行换货片段没有被撤销延保赠品。

27–30没有召回旧/未来/过期/撤销片段；N06仍正确过滤。它们暴露相近主题通过分数门槛但无法回答所问事实，不能当作N06退役失效。单Gold和“固定时点当前有效ready证据”口径已获批准；历史询问27/29等在该协议下为no-answer，不评历史档案回答能力。本轮未发现需要重标的新Gold冲突；这不是新的独立人工审核，若用户希望支持历史档案/多Gold，需另建协议和数据版本后重做基线，不能更改本冻结测试。

默认业务库publication缺失是业务运行存储漂移，与冻结测试Gold无效不同，不因这一发现修改Gold。README/核心Wiki描述的N06实现仍正确，但Workbench“在线RAG曾验证”只代表历史证据，不能表示当前默认库ready；本次在已有Workbench记录当前观察。无需扩写其他Wiki。

## B1建议与验收

建议在本结果人工验收且原模型资源/下载/依赖/CPU授权与独立环境smoke门满足后，开展隔离B1对照；当前不启动B1。预期收益是改善口语/同义的raw覆盖与排序（01/05/06），并在同一dev约束下改善最终证据召回与FPR取舍。收益是待检验假设，不保证语义Embedding解决事实缺失；题19/20/21/23及生命周期问题可能仍需单独的answerability/范围判断，B1不能凭主题相似度宣称解决。

0.20保持开发锁，但该测试结果不支持推广为生产阈值。不要在test上回调到另一个阈值，也不要修改Gold或正文使指标变好。默认库可信审核/重发布应作为独立任务，不能把修复效果混入本对照。A05整体doing/partial；本阶段measured，建议verify待用户验收，B1仍not_executed/blocked于原资源门。

独立练习：不用Codex，打开per_case.csv，统计13/14/15和27–30，手算Recall=9/21、FPR=8/9、precision=9/17；再在observations.json核对27的引用版本为demo-v2，解释为何它是事实不足而非旧片段泄漏。

建议提交信息（不执行）：`eval(rag): verify frozen B0 calibrated baseline and tradeoffs`。
'''
    latency = summary['latency_ms']
    report += f"\n本轮P50/P95={latency['p50']:.2f}/{latency['p95']:.2f} ms；测试和核验命令及实际计数见validation.json。\n"
    (OUT / 'report.md').write_text(report, encoding='utf-8')
    print(json.dumps(dict(gained=gained, added_fp=added_fp, failures=failures,
                         candidate_scores_identical=True, default_body_texts_equal=common_equal), ensure_ascii=False))


if __name__ == '__main__':
    main()
