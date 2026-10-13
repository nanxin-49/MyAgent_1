"""Development-only threshold replay; no test scores or semantic model access."""
import copy
import csv
import json
import math

from mcp.rag_contract import build_hit
from mcp.tool_manager import RerankResult, ToolResult

from evaluation.rag_quality.run_baseline import (
    ROOT, active_identities, aggregate, chunk_catalog, digest, make_manager, observe, write_json,
)

GRID = tuple(i / 100 for i in range(101))  # Predeclared protocol; not an assumed score range.
SCORE_KIND = 'one_minus_chroma_distance'
TIE_BREAK = ['Recall@5 max', 'FPR count min', 'MRR max', 'citation precision max (N/A last)', 'threshold max']


def load_dev_frozen(dataset_version, directory):
    if dataset_version != 'v2':
        raise ValueError('development calibration requires formal v2')
    lock = json.loads((directory / 'freeze_v2.json').read_text(encoding='utf-8'))
    expected = {'corpus_v1.json', 'dataset_v2.json', 'dev_dataset_v2.json', 'gold_review_v2.md', 'gold_v1_to_v2_diff.md'}
    if set(lock['files']) != expected or lock['version'] != 'a05-freeze-v2':
        raise ValueError('invalid development freeze file registry')
    for name, sha in lock['files'].items():
        if digest(directory / name) != sha:
            raise ValueError('frozen file hash mismatch: ' + name)
    # Only these contents are parsed. Test file and historical observations are never parsed here.
    corpus = json.loads((directory / 'corpus_v1.json').read_text(encoding='utf-8'))
    dev = json.loads((directory / 'dev_dataset_v2.json').read_text(encoding='utf-8'))
    if (lock['review']['status'] != 'user_approved_v2' or dev['human_review_status'] != 'user_approved_v2'
            or dev['version'] != 'a05-threshold-dev-v2' or lock['dev_dataset_version'] != dev['version']
            or corpus['version'] != dev['corpus_version'] or corpus['version'] != lock['corpus_version']
            or corpus['as_of'] != dev['as_of'] or corpus['as_of'] != lock['as_of']):
        raise ValueError('development approval/version/time mismatch')
    cases = dev['cases']
    if (len(cases) != 16 or len({r['case_id'] for r in cases}) != 16
            or any(not r['case_id'].startswith('DEV-') or type(r['answerable']) is not bool for r in cases)
            or sum(r['answerable'] for r in cases) != 8 or lock['dev_counts'] != {'total': 16, 'answerable': 8, 'no_answer': 8}):
        raise ValueError('development IDs/denominators invalid')
    fields = ('case_id', 'answerable', 'gold_document_id', 'gold_chunk_id', 'gold_evidence', 'policy_version')
    if lock['dev_gold_labels'] != [{key: r[key] for key in fields} for r in cases]:
        raise ValueError('development frozen Gold labels mismatch')
    chunks = {c['chunk_id']: c for c in chunk_catalog(corpus)}
    active = active_identities(corpus)
    for row in cases:
        if not row['query'].strip() or not row['annotation_reason'].strip():
            raise ValueError('development label incomplete')
        if row['answerable']:
            chunk = chunks.get(row['gold_chunk_id'])
            if (not chunk or not row['gold_evidence'] or row['gold_evidence'] not in chunk['content']
                    or chunk['document_id'] != row['gold_document_id'] or chunk['policy_version'] != row['policy_version']
                    or (chunk['document_id'], chunk['policy_version']) not in active):
                raise ValueError('development Gold not in active corpus')
        elif any(row[k] is not None for k in ('gold_document_id', 'gold_chunk_id', 'gold_evidence', 'policy_version')):
            raise ValueError('no-answer case carries positive Gold')
    return corpus, dev, lock


def unique_repeat(rows, cases, repeat):
    group = [r for r in rows if r['repeat'] == repeat]
    ids = [r['case_id'] for r in group]
    if len(ids) != len(set(ids)) or set(ids) != {r['case_id'] for r in cases}:
        raise ValueError('duplicate/incomplete observation group; repeats do not expand denominator')
    if any(not i.startswith('DEV-') for i in ids):
        raise ValueError('calibration cannot consume test observations')
    return group


async def replay(case, observation, threshold, manager, now, chunks):
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('threshold outside existing min_score parameter contract')
    rebuilt = []
    for candidate in observation['candidates']:
        if (candidate['score_kind'] != SCORE_KIND or not math.isfinite(candidate['raw_distance'])
                or candidate['score'] != 1.0 - candidate['raw_distance']):
            raise ValueError('raw HTTP score contract mismatch')
        rebuilt.append(build_hit(candidate['content'], candidate['metadata'], candidate['raw_distance'],
                                 min_score=threshold, now=now).model_dump(mode='json'))
    usable = [h for h in rebuilt if h['retrieval_status'] == 'usable' and h['citation']]
    if usable:
        final = await manager._finalize_rag('knowledge_search', usable,
                                           RerankResult(usable, False, 'not_requested'), 5)
    else:
        final = ToolResult(True, [], 'knowledge_search', retrieval_status='low_confidence' if rebuilt else 'no_answer')
    if not final.success:
        raise RuntimeError('replay evidence degraded; never counted as a correct refusal')
    raw = ToolResult(True, rebuilt, 'knowledge_search', attempts=0)
    row = observe({**case, 'category': 'development'}, raw, final, chunks, 0, observation['repeat'], 0)
    row['threshold'] = threshold
    row['mode'] = 'offline contract replay; latency not measured'
    return row


def curve_point(rows, threshold):
    metrics = aggregate(rows)  # Rejects duplicate question IDs.
    return {'threshold': threshold,
            **{k: metrics[k] for k in ('Recall@1', 'Recall@3', 'Recall@5', 'MRR',
                                       'no_answer_false_positive_rate', 'citation_evidence_precision')},
            'correct_refusals': sum(not r['answerable'] and not r['hits'] and r['success'] for r in rows),
            'no_returned_hits': sum(not r['hits'] for r in rows),
            'status_counts': metrics['status_counts']}


def select_threshold(curve):
    if not curve or any(p['no_answer_false_positive_rate']['denominator'] != 8
                        or p['Recall@5']['denominator'] != 8 for p in curve):
        raise ValueError('development calibration requires 8 positive and 8 negative questions')
    feasible = [p for p in curve if p['no_answer_false_positive_rate']['numerator'] <= 1]
    if not feasible:
        return None
    def key(p):
        citation = p['citation_evidence_precision']
        precision = citation['numerator'] / citation['denominator'] if citation['denominator'] else None
        return (p['Recall@5']['numerator'], -p['no_answer_false_positive_rate']['numerator'],
                p['MRR']['numerator'], precision if precision is not None else -1, p['threshold'])
    return max(feasible, key=key)


async def calibrate(output, observations, dataset, live_kb, snapshot, fixed_time, manifest):
    cases = dataset['cases']
    chunks = {c['chunk_id']: c for c in chunk_catalog(json.loads((output / 'corpus_v1.json').read_text(encoding='utf-8')))}
    replay_kb = copy.copy(live_kb)
    frozen_snapshot = copy.deepcopy(snapshot)
    replay_kb._snapshot = lambda: copy.deepcopy(frozen_snapshot)
    # Exact production N06 eligibility/validate_hits + N07 finalize on the captured immutable snapshot.
    # Vector scores originate from real HTTP; no Fake Chroma ranks or distances are generated.
    manager = make_manager(replay_kb)
    curves, selected_rows = {}, {}
    signatures = []
    for repeat in range(1, manifest['repeats'] + 1):
        group = unique_repeat(observations, cases, repeat)
        by_id = {r['case_id']: r for r in group}
        signatures.append([(r['case_id'], r['candidates']) for r in group])
        curve, sweep_rows = [], {}
        for threshold in GRID:
            rows = [await replay(c, by_id[c['case_id']], threshold, manager, fixed_time, chunks) for c in cases]
            sweep_rows[threshold] = rows
            curve.append(curve_point(rows, threshold))
        # Replay at 0.35 must exactly agree with real capture final evidence, not merely a score count.
        for row in sweep_rows[.35]:
            original = by_id[row['case_id']]
            if any(row[k] != original[k] for k in ('hits', 'citations', 'gold_rank', 'retrieval_status')):
                raise RuntimeError('offline replay diverged from the real 0.35 contract')
        curves[str(repeat)] = curve
        chosen = select_threshold(curve)
        selected_rows[str(repeat)] = sweep_rows[chosen['threshold']] if chosen else []
    if any(s != signatures[0] for s in signatures) or any(v != curves['1'] for v in curves.values()):
        raise RuntimeError('development candidates/curve are not repeatable; calibration blocked')
    chosen = select_threshold(curves['1'])
    write_json(output / 'b0_lexical_dev_v2_observations.json', observations)
    write_json(output / 'b0_lexical_threshold_sweep_v2.json', curves)
    write_json(output / 'b0_lexical_selected_replay_v2.json', selected_rows)
    columns = ['threshold', 'recall1_count', 'recall3_count', 'recall5_count', 'recall1', 'recall3', 'recall5',
               'mrr', 'false_positive_count', 'fpr', 'citation_correct', 'citation_count', 'citation_precision',
               'correct_refusals', 'no_returned_hits', 'answerable_denominator', 'no_answer_denominator']
    with (output / 'b0_lexical_threshold_sweep_v2.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
        for p in curves['1']:
            prec = p['citation_evidence_precision']; fpr = p['no_answer_false_positive_rate']
            writer.writerow(dict(threshold=p['threshold'], recall1_count=p['Recall@1']['numerator'],
                recall3_count=p['Recall@3']['numerator'], recall5_count=p['Recall@5']['numerator'],
                recall1=p['Recall@1']['value'], recall3=p['Recall@3']['value'], recall5=p['Recall@5']['value'],
                mrr=p['MRR']['value'], false_positive_count=fpr['numerator'], fpr=fpr['value'],
                citation_correct=prec['numerator'], citation_count=prec['denominator'], citation_precision=prec['value'],
                correct_refusals=p['correct_refusals'], no_returned_hits=p['no_returned_hits'],
                answerable_denominator=8, no_answer_denominator=8))
    scores = [h['score'] for r in observations for h in r['candidates']]
    binding = {name: digest(output / name) for name in ('corpus_v1.json', 'dev_dataset_v2.json', 'freeze_v2.json')}
    record = {'status': 'locked' if chosen else 'calibration_infeasible', 'split': 'dev',
              'selected_threshold': chosen['threshold'] if chosen else None,
              'selected_threshold_hex': chosen['threshold'].hex() if chosen else None,
              'objective': 'max final Recall@5 subject to dev no-answer false positives <=1/8',
              'tie_break': TIE_BREAK, 'threshold_grid': list(GRID),
              'score_kind': SCORE_KIND, 'score_meaning': '1 - actual Chroma distance; heuristic, not probability or assumed standard cosine',
              'direction': 'higher passes; score >= threshold', 'float_rule': 'full stored IEEE754 doubles, no rounding/epsilon/clip; original distance retained',
              'parameter_bounds': '[0,1] per KnowledgeBase.min_score, not score bounds',
              'observed_score_range': [min(scores), max(scores)], 'baseline_035_dev_metrics': curves['1'][35],
              'selected_dev_metrics': chosen, 'degenerate_zero_recall': bool(chosen and chosen['Recall@5']['numerator'] == 0),
              'reason': 'Apply preregistered grid/objective/tie-break solely to 16 development cases; test scores never consumed.',
              'data_binding_sha256': binding, 'as_of': manifest['as_of'], 'top_k': 5,
              'embedding_version': manifest['embedding_version'], 'dimensions': manifest['dimensions'],
              'raw_observations_sha256': digest(output / 'b0_lexical_dev_v2_observations.json'),
              'curve_csv_sha256': digest(output / 'b0_lexical_threshold_sweep_v2.csv'),
              'head': manifest['head'], 'python': manifest['python'], 'packages': manifest['packages'],
              'code_sha256': {**manifest['implementation_sha256'], 'evaluation/rag_quality/dev_calibration.py': digest(ROOT / 'evaluation/rag_quality/dev_calibration.py')},
              'protocol_sha256': digest(ROOT / 'evaluation/rag_quality/p2_experiment_protocol.md'),
              'snapshot_sha256': None, 'real_http_candidate_capture': True, 'repeats_scored_separately': True,
              'test_scores_consumed': False, 'test_evaluation_executed': False,
              'production_configuration_changed': False, 'model_calls': 0}
    write_json(output / 'n06_snapshot.json', {k: list(v) for k, v in snapshot.items()})
    record['snapshot_sha256'] = digest(output / 'n06_snapshot.json')
    write_json(output / 'b0_lexical_calibration_v2.json', record)
    manifest['calibration_sha256'] = digest(output / 'b0_lexical_calibration_v2.json')
    manifest['calibration_status'] = record['status']
    lines = ['# B0 lexical development v2 threshold calibration', '',
             'Real HTTP candidate capture; 16 DEV questions only, two repeats scored separately. No test evaluation.',
             'Raw score=1-Chroma distance; original doubles/distances retained, not clipped or assumed probabilistic.',
             'Offline replay: production build_hit + N06 eligibility/validate_hits + N07 finalize on immutable verified snapshot.',
             'Grid 0.00..1.00 by 0.01 is preregistered and min_score-valid, not an assertion that scores lie in [0,1].',
             'Objective: FPR<=1/8 then Recall@5 max; ties: FPR min, MRR max, citation precision max, threshold max.',
             '', '```json', json.dumps(record, ensure_ascii=False, indent=2), '```', '',
             'Full 101-point Recall@1/3/5, MRR, FPR/FP count, citation precision, refusal/empty counts in CSV.',
             'Offline sweep latency is not a real HTTP latency measurement; capture latency is in summary.json.',
             'A low FPR with zero Recall is degenerate and must not be called a useful quality improvement.',
             'After acceptance: use this locked JSON/hash for ONE same-v2 30-case B0-calibrated run; no retrospective threshold change.',
             'Small shared corpus and only eight negatives; cannot prove generalization or answer completeness.']
    (output / 'b0_lexical_calibration_v2.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
