"""Source-separated question evaluation of verified saved weights and their seed control.

Only the public learner problem/instructions reach inference. Source answers remain
with education_assessment; unsupported media, context overflow and unknown output
remain explicit coverage rather than being converted into evidence of competence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import byte_tokenizer as B
import decision_authoring as A
import education_assessment as G
import education_backgrounds as I
import education_corpus as C
import foundation_pretraining as F

VERSION = 1
DEFAULT_POLICY = {'schema': 'speakeasy-foundation-question-policy/1',
                  'evaluationSplits': ['validation', 'test'], 'maximumItemsPerSplit': 1024,
                  'maximumNewTokens': 32, 'contextOverflow': 'withhold',
                  'choiceScoring': 'public-option-key-loglikelihood',
                  'generation': 'greedy-argmax-no-sampling'}
AUTHORITY = {'personKnowledgeAuthority': False, 'nativeSkillAuthority': False,
             'currentWorldAuthority': False, 'peerAssentAuthority': False,
             'runtimeIntegration': False, 'modelTrainingAuthority': False}


def policy(value):
    A.fields(value, set(DEFAULT_POLICY), 'question evaluation policy')
    A.require(value['schema'] == DEFAULT_POLICY['schema'], 'unsupported question policy')
    splits = value['evaluationSplits']
    A.require(isinstance(splits, list) and splits and len(splits) == len(set(splits))
              and set(splits) <= {'validation', 'test'}, 'evaluation must use held-out validation/test only')
    for key, maximum in [('maximumItemsPerSplit', 4096), ('maximumNewTokens', 128)]:
        A.require(type(value[key]) is int and 1 <= value[key] <= maximum, 'invalid bounded ' + key)
    for key in ('contextOverflow', 'choiceScoring', 'generation'):
        A.require(value[key] == DEFAULT_POLICY[key], 'unsupported evaluation ' + key)
    return value


def state_digest(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        digest.update(A.encoded({'name': name, 'shape': list(value.shape), 'dtype': str(value.dtype)}))
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def source_text(node):
    """Retain MathML/tables verbatim; never flatten powers, fractions or table structure."""
    local = node.tag.rsplit('}', 1)[-1]
    A.require(local not in {'solution', 'answer', 'hint'}, 'hidden answer markup in public input')
    if node.tag.startswith('{http://www.w3.org/1998/Math/MathML}') or local == 'table':
        for child in node.iter():
            A.require(child.tag.rsplit('}', 1)[-1] not in {'solution', 'answer', 'hint'},
                      'hidden answer markup in public input')
        preserved = copy.deepcopy(node); preserved.tail = None
        return ET.tostring(preserved, encoding='unicode', short_empty_elements=True)
    if (local == 'list' and node.get('list-type') == 'enumerated'
            and node.get('number-style') in {'lower-alpha', 'upper-alpha'}):
        parts, index = [node.text or ''], 0
        for child in node:
            label = ''
            if child.tag.rsplit('}', 1)[-1] == 'item':
                A.require(index < 26, 'unsupported source alphabetic list length')
                label, index = '(' + chr(65 + index) + ') ', index + 1
            parts.extend([label, source_text(child), child.tail or '', '\n'])
        return ''.join(parts)
    parts = [node.text or '']
    for child in node:
        parts.extend([source_text(child), child.tail or ''])
        if child.tag.rsplit('}', 1)[-1] in {'para', 'item', 'title', 'list'}:
            parts.append('\n')
    return ''.join(parts)


def public_prompt(public):
    G.validate_seal(public, 'learner item')
    A.require(public['schema'] == 'speakeasy-educational-learner-item/1', 'unsupported public item')
    item = public['input']; G.validate_seal(item, 'learner input')
    A.require(item['coverage']['solutionTextIncluded'] is False, 'public input includes source solution')
    # IDs, source metadata, target and eligibility are excluded from model text.
    instructions = [source_text(ET.fromstring(value)).strip() for value in item['contextXml']]
    problems = [ET.fromstring(value) for value in item['problemXml']]
    question = '\n'.join(source_text(node).strip() for node in problems)
    prompt = '\n'.join([*instructions, question, 'Answer: '])
    options = G.choice_options(problems[0]) if len(problems) == 1 else None
    return prompt, options or []


def inference(model, public, tokenizer, context_length, settings, model_evidence=None):
    prompt, options = public_prompt(public)
    payload = tokenizer.encode_text(prompt)
    ids = [B.SPECIAL_IDS['bos'], *payload]
    reserve = max([len(tokenizer.encode_text(option['key'])) for option in options] or
                  [settings['maximumNewTokens']])
    coverage = {'originalPromptTokens': len(ids), 'inputTokens': 0,
                'contextLength': context_length, 'reservedOutputTokens': reserve,
                'contextOverflowTokens': max(0, len(ids) + reserve - context_length),
                'truncatedTokens': 0,
                'mediaReferencesPresent': public['input']['coverage']['mediaReferencesPresent'],
                'mediaBytesAcquired': public['input']['coverage']['mediaBytesAcquired'],
                'promptSha256': C.sha(prompt.encode()), 'inputTokenIdsSha256': A.digest(ids)}
    base = {'schema': 'speakeasy-foundation-generated-answer/1', 'learnerItemSha256': public['contentSha256'],
            'itemSha256': public['itemSha256'], 'prompt': prompt, 'inputTokenIds': [],
            'modelEvidence': model_evidence,
            'coverage': coverage, 'response': '', 'generatedTokenIds': [], 'generatedBytesHex': '',
            'modelConfidence': None, 'confidenceMeaning': 'no-supported-inference',
            'status': 'withheld', 'reason': None, 'candidateScores': [], **AUTHORITY}
    if coverage['mediaReferencesPresent']:
        base['reason'] = 'required-source-media-not-provided'
        return A.seal(base)
    if coverage['contextOverflowTokens']:
        # The source question is kept in the receipt, but no partial prompt is scored.
        base['reason'] = 'complete-question-exceeds-context-budget'
        return A.seal(base)
    coverage['inputTokens'], base['inputTokenIds'] = len(ids), ids
    torch = F.torch_owner(); device = next(model.parameters()).device
    was_training = model.training; model.eval()
    try:
        with torch.no_grad():
            if options:
                scores = []
                for option in options:
                    sequence, score = list(ids), 0.0
                    target = tokenizer.encode_text(option['key'])
                    for token in target:
                        logits = model(torch.tensor([sequence], dtype=torch.long, device=device))[0, -1]
                        A.require(torch.isfinite(logits).all().item(), 'nonfinite generated logits')
                        score += float(torch.log_softmax(logits, dim=-1)[token])
                        sequence.append(token)
                    scores.append({'key': option['key'], 'tokenIds': target, 'logLikelihood': score})
                winner = max(scores, key=lambda entry: (entry['logLikelihood'], -ord(entry['key'])))
                largest = max(entry['logLikelihood'] for entry in scores)
                denominator = sum(math.exp(entry['logLikelihood'] - largest) for entry in scores)
                base.update(response=winner['key'], generatedTokenIds=winner['tokenIds'],
                            generatedBytesHex=winner['key'].encode().hex(), candidateScores=scores,
                            modelConfidence=math.exp(winner['logLikelihood'] - largest) / denominator,
                            confidenceMeaning='normalized-public-option-key-likelihood',
                            status='generated', reason='public-choice-scoring')
            else:
                sequence, generated, log_probabilities = list(ids), [], []
                reason = 'maximum-output-tokens'
                for _ in range(settings['maximumNewTokens']):
                    logits = model(torch.tensor([sequence], dtype=torch.long, device=device))[0, -1]
                    A.require(torch.isfinite(logits).all().item(), 'nonfinite generated logits')
                    token = int(torch.argmax(logits))
                    log_probabilities.append(float(torch.log_softmax(logits, dim=-1)[token]))
                    generated.append(token)
                    if token in B.SPECIAL_IDS.values():
                        reason = 'source-eos' if token == B.SPECIAL_IDS['eos'] else 'structural-token-stop'
                        break
                    A.require(token in tokenizer.vocabulary, 'generated token is outside frozen vocabulary')
                    sequence.append(token)
                ordinary = [token for token in generated if token in tokenizer.vocabulary]
                raw = tokenizer.decode_bytes(ordinary)
                try:
                    response = raw.decode('utf-8', errors='strict')
                except UnicodeError:
                    response, reason = '', 'generated-bytes-not-valid-utf8'
                base.update(response=response, generatedTokenIds=generated, generatedBytesHex=raw.hex(),
                            modelConfidence=math.exp(sum(log_probabilities) / len(log_probabilities)),
                            confidenceMeaning='geometric-mean-selected-token-probability-not-answer-calibration',
                            status='generated', reason=reason)
    finally:
        model.train(was_training)
    return A.seal(base)


def statistics(rows):
    counts = {'selectedSupportedTargets': len(rows), 'attemptedCompleteInputs': 0,
              'withheld': 0, 'correct': 0, 'incorrect': 0, 'unscored': 0}
    for row in rows:
        counts['attemptedCompleteInputs'] += row['generation']['status'] == 'generated'
        counts['withheld'] += row['generation']['status'] == 'withheld'
        status = row['grade']['status']
        counts[status if status in {'correct', 'incorrect'} else 'unscored'] += 1
    scored = counts['correct'] + counts['incorrect']
    return {**counts, 'scoredResponses': scored,
            'accuracyOnScoredResponses': counts['correct'] / scored if scored else None,
            'correctFractionOfSelectedSupportedTargets': counts['correct'] / len(rows) if rows else None,
            'coverageStanding': 'no-supported-targets' if not rows else 'bounded-source-question-evaluation'}


def select_families(items, maximum):
    families = {}
    for item in items:
        families.setdefault(item['familyId'], []).append(item)
    for rows in families.values(): rows.sort(key=lambda item: item['contentSha256'])
    A.require(maximum >= len(families), 'evaluation bound cannot cover supported source families')
    chosen, index = [], 0
    while len(chosen) < min(maximum, len(items)):
        for family in sorted(families):
            if index < len(families[family]) and len(chosen) < maximum:
                chosen.append(families[family][index])
        index += 1
    return chosen


def evaluate(archive, prepared, dataset, artifact, request, data, run, bank,
             expected_run_sha, expected_bank_sha, as_of_time, session_id, settings=None, store=None):
    settings = policy(dict(DEFAULT_POLICY) if settings is None else settings)
    for digest in (expected_run_sha, expected_bank_sha): A.hash_value(digest, 'trusted evaluation input')
    A.identifier(session_id, 'explicit evaluation session')
    # Validate attribution even when a held-out split contains no supported items.
    G.validate_response({'schema': 'speakeasy-educational-assessment-response/1', 'itemSha256': '0' * 64,
                         'learner': {'kind': 'model', 'id': 'foundation-shared-cognitive-base', 'version': expected_run_sha},
                         'sessionId': session_id, 'asOfTime': as_of_time, 'learningMode': 'independent-retrieval',
                         'assistanceEvidenceRefs': [], 'evidenceRefs': ['evaluation-attribution-preflight'], 'response': ''})
    # Verify the authoritative saved run and source data before inference or receipt creation.
    saved, trained = F.evaluate(archive, prepared, dataset, artifact, request, data, run, expected_run_sha, store)
    manifest, items = G.validate_bank(archive, bank)
    A.require(manifest['contentSha256'] == expected_bank_sha, 'assessment bank identity differs')
    isolation = G.validate_training_isolation(manifest, request, settings['evaluationSplits'], archive=archive, bank=bank)
    data_manifest = A.read(data / 'manifest.json')
    A.require(saved['dataManifestSha256'] == data_manifest['contentSha256'], 'evaluated data identity differs')
    tokenizer = B.Tokenizer(artifact)
    untrained = F.make_model(saved['config'], B.FIRST_MERGE + len(artifact['merges']), data_manifest['sequenceLength'])
    initial_sha, learned_sha = state_digest(untrained), state_digest(trained)
    selected, coverage = [], {}
    for split in settings['evaluationSplits']:
        source_items = [item for item in items if item['split'] == split]
        eligible = [item for item in source_items if item['gradingTarget'] is not None]
        chosen = select_families(eligible, settings['maximumItemsPerSplit'])
        selected.extend(chosen)
        coverage[split] = {'sourceExercises': len(source_items), 'supportedTargets': len(eligible),
                           'unsupportedSourceTargets': len(source_items) - len(eligible),
                           'selectedTargets': len(chosen), 'omittedByBound': len(eligible) - len(chosen),
                           'sourceFamilyIds': sorted({item['familyId'] for item in source_items}),
                           'supportedFamilyIds': sorted({item['familyId'] for item in eligible}),
                           'selectedFamilyIds': sorted({item['familyId'] for item in chosen}),
                           'sampling': 'source-family-round-robin-then-item-sha256'}
    model_ids = {'savedWeights': {'kind': 'model', 'id': 'foundation-shared-cognitive-base',
                                  'version': expected_run_sha},
                 'sameUntrainedSeed': {'kind': 'model', 'id': 'foundation-shared-cognitive-base-untrained-control',
                                      'version': A.digest({'comparisonRunSha256': expected_run_sha,
                                                         'config': saved['configSha256'], 'tokenizer': artifact['contentSha256'],
                                                         'sequenceLength': data_manifest['sequenceLength'], 'state': initial_sha})}}
    generated, responses = [], []
    for name, model in [('savedWeights', trained), ('sameUntrainedSeed', untrained)]:
        for item in selected:
            public = G.learner_input(item)
            model_evidence = {'learner': model_ids[name], 'comparisonRunSha256': expected_run_sha,
                              'stateSha256': learned_sha if name == 'savedWeights' else initial_sha,
                              'weightsSha256': saved['weightsSha256'] if name == 'savedWeights' else None,
                              'seed': saved['config']['seed'], 'configSha256': saved['configSha256'],
                              'sessionId': session_id, 'asOfTime': as_of_time}
            generation = inference(model, public, tokenizer, data_manifest['sequenceLength'], settings, model_evidence)
            response = {'schema': 'speakeasy-educational-assessment-response/1', 'itemSha256': item['contentSha256'],
                        'learner': model_ids[name], 'sessionId': session_id, 'asOfTime': as_of_time,
                        'learningMode': 'independent-retrieval', 'assistanceEvidenceRefs': [],
                        'evidenceRefs': [generation['contentSha256'], isolation['contentSha256']],
                        'response': generation['response']}
            G.validate_response(response)
            generated.append({'model': name, 'split': item['split'], 'generation': generation, 'response': response})
            responses.append(response)
    # This public owner API reconstructs actual source answers; it does not trust saved grade rows.
    grades = G.grade_many(archive, bank, responses)
    rows = [A.seal({**row, 'grade': grade}) for row, grade in zip(generated, grades)]
    A.require(len(grades) == len(generated), 'grader response count differs')
    A.require(state_digest(trained) == learned_sha and state_digest(untrained) == initial_sha,
              'read-only question evaluation changed model weights')
    result = A.seal({'schema': 'speakeasy-foundation-question-evaluation/1', 'evaluatorVersion': VERSION,
                     'runSha256': expected_run_sha, 'weightsSha256': saved['weightsSha256'],
                     'dataManifestSha256': saved['dataManifestSha256'], 'tokenizerSha256': artifact['contentSha256'],
                     'assessmentBankSha256': expected_bank_sha, 'sourceIsolationProof': isolation,
                     'asOfTime': as_of_time, 'sessionId': session_id, 'policy': settings,
                     'sameSeedConfigSha256': saved['configSha256'], 'untrainedStateSha256': initial_sha,
                     'savedStateSha256': learned_sha, 'sourceCoverage': coverage, 'rows': rows,
                     'metrics': {name: {split: statistics([row for row in rows if row['model'] == name and row['split'] == split])
                                       for split in settings['evaluationSplits']} for name in model_ids},
                     'standing': 'source-question-performance-of-reference-weights',
                     'limits': ['bounded-question-sample', 'unrecognized-output-remains-unscored',
                                'no-coverage-is-no-evidence', 'model-probability-is-not-answer-calibration'], **AUTHORITY})
    # Refuse mid-evaluation edits to the pinned runtime inputs as well.
    A.require(A.read(run / 'manifest.json') == saved and C.sha((run / 'weights.pt').read_bytes()) == saved['weightsSha256'],
              'saved weights/run changed during evaluation')
    F.check_data_files(data, data_manifest)
    A.require(A.read(bank / 'manifest.json') == manifest, 'assessment bank changed during evaluation')
    A.require(C.sha((bank / 'assessments.jsonl').read_bytes()) == manifest['assessmentsSha256']
              and C.sha((bank / 'learner-items.jsonl').read_bytes()) == manifest['learnerItemsSha256'],
              'assessment bank rows changed during evaluation')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'prepared', 'dataset', 'tokenizer', 'splits', 'data', 'run', 'bank', 'time', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--run-sha256', required=True); parser.add_argument('--bank-sha256', required=True)
    parser.add_argument('--session-id', required=True); parser.add_argument('--policy', type=Path)
    args = parser.parse_args(argv)
    try:
        A.require(not args.out.exists(), 'preserve existing question evaluation receipt')
        A.require(not any(args.out.resolve().is_relative_to(path.resolve())
                          for path in (args.archive, args.prepared, args.dataset, args.data, args.run, args.bank)),
                  'evaluation output cannot modify source/run inputs')
        result = evaluate(args.archive, args.prepared, args.dataset, A.read(args.tokenizer), A.read(args.splits),
                          args.data, args.run, args.bank, args.run_sha256, args.bank_sha256, A.read(args.time),
                          args.session_id, A.read(args.policy) if args.policy else None)
        I.write_immutable(args.out, result)
    except (ValueError, OSError, RuntimeError, ET.ParseError, KeyError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr); return 2
    print('VERIFIED ' + result['contentSha256'] + '; ' + str(result['metrics']))
    return 0


if __name__ == '__main__': raise SystemExit(main())
