"""Deterministic offline A05-P2 gate material; never embeds, queries or downloads.

uv run python -m evaluation.rag_quality.prepare_gate
"""
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path

from evaluation.rag_quality.run_baseline import (
    HERE, ROOT, active_identities, chunk_catalog, digest, load_frozen,
)

P1 = ROOT / 'evaluation/reports/rag_quality/20261012T073909Z-a7bd452b'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def normalized(query):
    return ''.join(c for c in query.lower() if c.isalnum())


def similarity(a, b):
    a, b = normalized(a), normalized(b)
    left = {a[i:i+2] for i in range(len(a)-1)}
    right = {b[i:i+2] for i in range(len(b)-1)}
    return {'sequence_ratio': SequenceMatcher(None, a, b, autojunk=False).ratio(),
            'bigram_jaccard': len(left & right) / len(left | right) if left | right else 1.0}


def leakage_report(dev, test):
    nearest, exact, high = [], [], []
    for row in dev['cases']:
        comparisons = []
        for case in test['cases']:
            pair = {'dev_id': row['case_id'], 'test_id': case['case_id'],
                    **similarity(row['query'], case['query'])}
            comparisons.append(pair)
            if normalized(row['query']) == normalized(case['query']):
                exact.append(pair)
            if pair['sequence_ratio'] >= .75 or pair['bigram_jaccard'] >= .60:
                high.append(pair)
        nearest.append(max(comparisons, key=lambda p: max(p['sequence_ratio'], p['bigram_jaccard'])))
    return {'rules': {'normalization': 'lowercase + alnum', 'sequence_ratio_flag': .75,
                      'bigram_jaccard_flag': .60},
            'exact_duplicates': exact, 'high_similarity_flags': high, 'nearest_test_query': nearest,
            'semantic_review': 'Author checked requested attributes and ambiguity; independent human review pending',
            'limitation': 'No semantic model used; lexical checks cannot prove absence of semantic leakage. Shared corpus/themes limit generalization.'}


def validate_dev(corpus, dev, test):
    if not 12 <= len(dev['cases']) <= 20:
        raise ValueError('dev needs 12-20 cases')
    if dev['corpus_version'] != corpus['version'] or dev['as_of'] != corpus['as_of']:
        raise ValueError('dev corpus/time mismatch')
    ids = [r['case_id'] for r in dev['cases']]
    queries = [normalized(r['query']) for r in dev['cases']]
    if len(set(ids)) != len(ids) or len(set(queries)) != len(queries):
        raise ValueError('duplicate dev case/query')
    if any(not i.startswith('DEV-') for i in ids) or set(ids) & {r['case_id'] for r in test['cases']}:
        raise ValueError('dev/test IDs overlap or invalid prefix')
    chunks = {c['chunk_id']: c for c in chunk_catalog(corpus)}
    active = active_identities(corpus)
    for r in dev['cases']:
        if type(r['answerable']) is not bool or not r['query'].strip() or not r['annotation_reason'].strip():
            raise ValueError('invalid dev label')
        gold = ('gold_document_id', 'gold_chunk_id', 'policy_version', 'gold_evidence')
        if r['answerable']:
            chunk = chunks.get(r['gold_chunk_id'])
            if (not chunk or not r['gold_evidence'] or r['gold_evidence'] not in chunk['content']
                    or chunk['document_id'] != r['gold_document_id']
                    or chunk['policy_version'] != r['policy_version']
                    or (chunk['document_id'], chunk['policy_version']) not in active):
                raise ValueError('dev gold not in eligible corpus')
        elif any(r[f] is not None for f in gold):
            raise ValueError('no-answer dev has positive gold')
    counts = Counter(r['answerable'] for r in dev['cases'])
    if not counts[True] or not counts[False]:
        raise ValueError('dev needs both label classes')
    leak = leakage_report(dev, test)
    if leak['exact_duplicates'] or leak['high_similarity_flags']:
        raise ValueError('dev/test duplicate or high lexical similarity needs revision before freeze')
    return leak


def validate_review(corpus, dataset, review):
    expected = {r['case_id'] for r in dataset['cases']}
    ids = [r['case_id'] for r in review['cases']]
    if set(ids) != expected or len(ids) != 30:
        raise ValueError('review must cover exactly 30 unique cases')
    if review['human_review_status'] != 'pending':
        raise ValueError('author suggestions cannot assert human approval')
    for r in review['cases']:
        if r['recommendation'] not in {'合理', '需人工判断', '疑似错误'}:
            raise ValueError('invalid review suggestion')
        if not r['reasoning'].strip() or not r['proposed_revision'].strip() or r['human_decision'] != 'pending':
            raise ValueError('incomplete review or unsupported human acceptance')
        for quote in r['additional_evidence']:
            if quote['quote'] not in corpus['documents'][quote['document_index']]['content']:
                raise ValueError('review quote not in frozen source')
    return dict(Counter(r['recommendation'] for r in review['cases']))


def verify_p1(observations, dataset):
    results = {}
    labels = {r['case_id']: r for r in dataset['cases']}
    for repeat in (1, 2):
        rows = [r for r in observations if r['repeat'] == repeat]
        if len(rows) != 30 or {r['case_id'] for r in rows} != set(labels):
            raise ValueError('P1 repeat incomplete')
        missing, threshold, false_positive, raw_correct, final_correct = [], [], [], [], []
        for r in rows:
            label = labels[r['case_id']]
            if label['answerable']:
                raw_gold = [h for h in r['candidates'] if h['frozen_chunk_id'] == label['gold_chunk_id']]
                final_gold = [h for h in r['hits'] if h['frozen_chunk_id'] == label['gold_chunk_id']]
                if raw_gold:
                    raw_correct.append(r['case_id'])
                else:
                    missing.append(r['case_id'])
                if final_gold:
                    final_correct.append(r['case_id'])
                elif raw_gold:
                    if not all(h['score'] < .35 and h['retrieval_status'] == 'low_confidence' for h in raw_gold):
                        raise ValueError('gold filtered for reason other than score')
                    threshold.append(r['case_id'])
            elif r['retrieval_status'] == 'usable' and r['hits'] and r['citations']:
                false_positive.append(r['case_id'])
        results[str(repeat)] = {'raw_gold_cases': raw_correct, 'final_gold_cases': final_correct,
                               'not_recalled': missing, 'below_threshold': threshold,
                               'theme_without_requested_fact': false_positive,
                               'counts': [len(raw_correct), len(final_correct), len(missing),
                                          len(threshold), len(false_positive)],
                               'denominators': {'answerable': 21, 'no_answer': 9}}
        if results[str(repeat)]['counts'] != [18, 6, 3, 12, 4]:
            raise ValueError('P1 count verification failed')
    return results


def choose_threshold(dev_rows, grid=None, max_false_positive=1):
    """Offline score arithmetic only. Inputs must be dev, never test observations.

    Rows: case_id DEV-*, answerable, gold_chunk_id, candidates [{chunk_id,score}].
    Caller supplies already N06/N07-valid candidates, in retrieval order. No model runs.
    """
    if (not dev_rows or any(not r['case_id'].startswith('DEV-') for r in dev_rows)
            or len({r['case_id'] for r in dev_rows}) != len(dev_rows)):
        raise ValueError('threshold selection requires unique DEV- rows, not test rows')
    positive = [r for r in dev_rows if r['answerable']]
    negative = [r for r in dev_rows if not r['answerable']]
    if not positive or not negative:
        raise ValueError('calibration needs both classes')
    grid = grid if grid is not None else [i / 100 for i in range(101)]
    if not grid or any(not 0 <= t <= 1 for t in grid):
        raise ValueError('invalid threshold grid')
    table = []
    for t in sorted(set(grid)):
        ranks, citations, correct_citations, fp = [], 0, 0, 0
        for r in dev_rows:
            hits = [h for h in r['candidates'][:5] if h['score'] >= t]
            rank = next((i for i, h in enumerate(hits, 1)
                         if r['answerable'] and h['chunk_id'] == r['gold_chunk_id']), None)
            if r['answerable']:
                ranks.append(rank)
            else:
                fp += bool(hits)
            citations += len(hits)
            correct_citations += sum(r['answerable'] and h['chunk_id'] == r['gold_chunk_id'] for h in hits)
        table.append({'threshold': t, 'recall5_count': sum(v is not None for v in ranks),
                      'answerable_denominator': len(positive), 'false_positive_count': fp,
                      'no_answer_denominator': len(negative),
                      'mrr_sum': sum(1 / v for v in ranks if v),
                      'citation_precision': correct_citations / citations if citations else None})
    feasible = [r for r in table if r['false_positive_count'] <= max_false_positive]
    best = max(feasible, key=lambda r: (r['recall5_count'], -r['false_positive_count'], r['mrr_sum'],
                                        r['citation_precision'] if r['citation_precision'] is not None else -1,
                                        r['threshold'])) if feasible else None
    return {'status': 'selected' if best else 'calibration_infeasible', 'selected': best,
            'max_false_positive_count': max_false_positive, 'table': table}


def render_review(corpus, dataset, review):
    active = active_identities(corpus)
    catalog = chunk_catalog(corpus)
    by_chunk = {r['chunk_id']: r for r in catalog}
    lines = ['# Gold v1 人工审核辅助表', '',
             '**30条作者审核建议；独立人工审核未完成，所有用户决定均待填写。**',
             '冻结时点2026-10-12T00:00:00Z；仅当前有效且ready的知识是答案证据。',
             '建议先解决歧义/口径，再决定接受v1或批准创建v2。本文件不修改任何Gold。', '',
             '| case_id | 建议 | 用户决定 |', '| --- | --- | --- |']
    lines += [f"| {r['case_id']} | {r['recommendation']} | 待审核 |" for r in review['cases']]
    docs_by_identity = {(d['document_id'], d.get('policy_version')): (i, d)
                        for i, d in enumerate(corpus['documents'])}
    def source_details(doc):
        identity = (doc['document_id'], doc.get('policy_version'))
        successors = [d.get('policy_version') for d in corpus['documents']
                      if d['document_id'] == doc['document_id'] and doc.get('policy_version') in d.get('supersedes', [])]
        return (f"来源 `{doc['source']}`；版本 `{doc.get('policy_version') or '非政策，无版本'}`；"
                f"effective_at `{doc.get('effective_at') or '无时间限制'}`；expires_at `{doc.get('expires_at') or '无'}`；"
                f"publication_status `{doc.get('publication_status', 'active')}`；"
                f"supersedes `{doc.get('supersedes', [])}`；被替代版本 `{successors}`；"
                f"固定时点有效 `{identity in active}`。所有冻结版本通过P1 ready发布，失效与未发布须区分。")
    for case, note in zip(dataset['cases'], review['cases'], strict=True):
        if case['case_id'] != note['case_id']:
            raise ValueError('review ordering mismatch')
        lines += ['', f"## {case['case_id']} — {note['recommendation']}", '',
                  f"- Query：{case['query']}", f"- Category：`{case['category']}`；answerable：`{case['answerable']}`。",
                  f"- Gold Document：`{case['gold_document_id']}`；Chunk：`{case['gold_chunk_id']}`；位置：`{case['evidence_location']}`。"]
        if case['answerable']:
            chunk = by_chunk[case['gold_chunk_id']]
            _, doc = docs_by_identity[(chunk['document_id'], chunk['policy_version'])]
            lines += ['- 原Gold证据（逐字）：', '', '> ' + case['gold_evidence'], '',
                      '- 完整实际Chunk（用于上下文复核）：', '', '> ' + chunk['content'], '',
                      '- 版本与生命周期：' + source_details(doc)]
        else:
            lines += ['- 正向Gold证据：无；不虚构缺失事实。判断范围为全部7个当前有效Chunk。']
            excluded = case.get('excluded_evidence')
            if excluded:
                _, doc = docs_by_identity[(excluded['document_id'], excluded['policy_version'])]
                chunk = next(c for c in catalog if c['document_id'] == doc['document_id']
                             and c['policy_version'] == doc['policy_version'])
                lines += [f"- 排除的Document/Chunk：`{doc['document_id']}` / `{chunk['chunk_id']}`；不是正向Gold。",
                          '- 失效正文原文（仅供审核，不允许作为本实验答案）：', '', '> ' + doc['content'], '',
                          '- 版本与生命周期：' + source_details(doc)]
            else:
                lines += ['- 当前有效版本/时间范围：见下方有效语料清单；无替代Gold来源，相关主题不补全缺失事实。']
        for ev in note['additional_evidence']:
            doc = corpus['documents'][ev['document_index']]
            lines += [f"- 补充对照证据 `{doc['document_id']}`：", '', '> ' + ev['quote'], '',
                      '- 对照来源生命周期：' + source_details(doc)]
        others = [corpus['documents'][i]['document_id'] for i in note['alternative_document_indices']]
        lines += [f"- 是否多个有效答案来源：{'可能：' + ', '.join(others) + '，是否充分需人工确认' if others else '未发现第二个充分的有效文档；同Chunk可含多个选项/事实，不能据此消除语义歧义'}。",
                  '- 能否回答/无答案理由及争议：' + note['reasoning'],
                  '- 修订建议：' + note['proposed_revision'], '- 用户审核决定：**待审核**（不自动标记通过）。']
    lines += ['', '## 当前有效语料及版本清单', '']
    for doc in corpus['documents']:
        if (doc['document_id'], doc.get('policy_version')) in active:
            lines += ['- ' + f"`{doc['document_id']}`：" + source_details(doc)]
    lines += ['', '## v2 决策建议', '', review['recommendation'],
              '若批准更改query/Gold/answerable/corpus，应创建dataset_v2及对应freeze与审核版本；本轮不修改v1。',
              '改问法会改变向量与召回，改Gold/可回答性会改变Recall/MRR/FPR分母或成功条件；需对批准版本重新运行B0，原P1仍作为v1历史证据。',
              '即使只精简证据跨度，也应新版本保留来源；重新B0可验证引用充分性与版本口径，不能把旧结果冒充新版本。']
    return '\n'.join(lines) + '\n'


def main():
    corpus, dataset, lock = load_frozen()
    review, dev = read(HERE / 'gold_review_notes_v1.json'), read(HERE / 'dev_dataset_v1.json')
    counts = validate_review(corpus, dataset, review)
    leak = validate_dev(corpus, dev, dataset)
    verification = verify_p1(read(P1 / 'observations.json'), dataset)
    (HERE / 'gold_review_v1.md').write_text(render_review(corpus, dataset, review), encoding='utf-8')
    report = {'scope': 'Offline gate preparation only; no model or retrieval calls',
              'frozen_hashes': lock['files'], 'freeze_file_sha256': digest(HERE / 'freeze_v1.json'),
              'p1_observations_sha256': digest(P1 / 'observations.json'),
              'review_counts': counts, 'human_review_status': 'pending',
              'dev_counts': dict(Counter('answerable' if r['answerable'] else 'no_answer' for r in dev['cases'])),
              'leakage': leak, 'p1_verification': verification,
              'dev_sha256': digest(HERE / 'dev_dataset_v1.json'),
              'notes_sha256': digest(HERE / 'gold_review_notes_v1.json')}
    (HERE / 'gate_checks_v1.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('review:', counts, 'dev:', report['dev_counts'], 'high-similarity flags:', len(leak['high_similarity_flags']))


if __name__ == '__main__':
    main()
