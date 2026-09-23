"""Prepare source-bound behavioral comparisons for human review, before training.

Authored candidate text is not a semantic proof, task approval or training row.
Audit-only owner state never enters the bounded behavioral input view.
"""
from __future__ import annotations

import copy
import argparse
from pathlib import Path

import conversation_tasks as C
import decision_authoring as A
import cross_module_rows as J
import training_evidence as E
import speaker_tasks as S

CHANNELS = {'temperament', 'conditions', 'relationship', 'threat', 'cognition',
            'experience', 'needs', 'activity', 'movementGoal', 'alternatives'}
AXES = {'nerve', 'discipline', 'aggression', 'initiative', 'selfPreservation',
        'compassion', 'appetite', 'talkativeness'}
OWNERS = dict(temperament='SAO.Disposition', conditions='SAO.Conditions', relationship='SAO.Standing',
              threat='SAO.Perception / SAO.Pressure', cognition='SAO.Neuro', experience='SAO.Identity / SAO.Lessons',
              needs='SAO.Needs', activity='SAO.Controller', movementGoal='SAO.Locomotion', alternatives='action-specific producers')


def validate_behavior(capture):
    value = capture['behavior']
    A.fields(value, {'schema', 'schemaVersion', 'personId', 'listenerRef', 'atTick',
                     'atHour', 'channels'}, 'behavior')
    A.schema(value, 'sao-behavior-evidence')
    A.require(all(value[k] == capture['context'][k] for k in ('personId', 'listenerRef', 'atTick'))
              and value['atHour'] == capture['namespace']['hour'], 'behavior identity/time differs')
    channels = value['channels']
    A.fields(channels, CHANNELS, 'behavior channels')
    for name, channel in channels.items():
        status = channel.get('status')
        A.require(status in ('available', 'unavailable'), 'behavior availability differs')
        A.fields(channel, {'owner', 'status', 'value' if status == 'available' else 'reason'}, name)
        A.require(channel['owner'] == OWNERS[name], 'behavior owner differs')
        if status == 'unavailable':
            A.require(isinstance(channel['reason'], str) and channel['reason'], 'availability reason absent')
    # Version 2 is the source-reviewed bodyless capture contract. A loaded
    # reader exists upstream; its controlled unit test is not a captured scene.
    for name in ('needs', 'activity', 'movementGoal'):
        A.require(channels[name]['status'] == 'unavailable'
                  and channels[name]['reason'] == 'body-not-loaded', 'bodyless capture claims loaded state')
    A.require(channels['alternatives']['status'] == 'unavailable', 'uncaptured action alternatives')
    traits = channels['temperament']['value']
    A.fields(traits, AXES, 'trait contributions')
    person = capture['sourceState']['person']
    for name, parts in traits.items():
        A.fields(parts, {'base', 'history', 'lesson', 'condition', 'effective'}, 'trait contribution')
        A.require(all(J.finite_number(v) for v in parts.values()), 'nonfinite trait contribution')
        A.require(parts['history'] == person.get('traitEchoes', {}).get(name, 0)
                  and parts['lesson'] == person.get('lessonEchoes', {}).get(name, 0),
                  'trait contribution source differs')
        computed = max(.15, min(.85, sum(parts[k] for k in ('base', 'history', 'lesson', 'condition'))))
        A.require(abs(parts['effective'] - computed) < 1e-12
                  and parts['effective'] == capture['catalogue']['conditioning']['traits'][name],
                  'effective trait differs')
    relation = channels['relationship']['value']
    conditioning = capture['catalogue']['conditioning']
    A.fields(relation, {'trust', 'debt', 'hostile'}, 'relationship')
    A.require(relation['trust'] == conditioning['trust']
              and relation['hostile'] == conditioning['moment']['hostile']
                  and (relation['debt'] > 0) == conditioning['moment']['debt'], 'relationship differs')
    condition = channels['conditions']['value']
    A.require(set(condition) <= {'carried', 'focus', 'phase', 'fearContribution'}
              and {'carried', 'fearContribution'} <= set(condition), 'condition fields differ')
    A.require(isinstance(condition['carried'], (list, dict)) and J.finite_number(condition['fearContribution']),
              'condition values differ')
    threat = channels['threat']['value']
    A.require(set(threat) in ({'pressure', 'scope'}, {'pressure', 'scope', 'nearest'})
              and threat['scope'] == 'retained-zombie-beliefs' and J.finite_number(threat['pressure']), 'threat fields differ')
    if 'nearest' in threat:
        nearest = threat['nearest']
        A.require(set(nearest) <= {'x', 'y', 'dist', 'at', 'source', 'teller', 'form', 'formPerformance', 'attributeMutations', 'prone'}
                  and J.finite_number(nearest.get('at')) and nearest['at'] <= value['atTick'], 'threat time or fields differ')
    cognition = channels['cognition']
    if cognition['status'] == 'available':
        cognitive = cognition['value']
        A.fields(cognitive, {'observedAtHour', 'enabled', 'load', 'clarity', 'affectiveVolatility',
                            'baseDecisionTicks', 'decisionTicks'}, 'cognitive projection')
        A.require(type(cognitive['enabled']) is bool
                  and all(J.finite_number(v) for k, v in cognitive.items() if k != 'enabled')
                  and cognitive['observedAtHour'] == value['atHour'], 'cognitive time/value differs')
    experience = channels['experience']['value']
    A.require(experience == {'known': person.get('lessonsKnown', {}), 'provenance': person.get('lessonMeta', {}),
                            'legacy': person.get('lessons', {})}, 'lesson provenance differs')
    return value


def model_view(capture):
    """Whitelist projections; source records and latent medical causes stay audit-only."""
    channels = validate_behavior(capture)['channels']
    result = {name: copy.deepcopy(channels[name]) for name in
              ('conditions', 'relationship', 'threat', 'cognition', 'needs', 'activity', 'movementGoal', 'alternatives')}
    result['temperament'] = {'status': 'available', 'owner': 'SAO.Disposition',
                            'value': {key: entry['effective'] for key, entry in channels['temperament']['value'].items()}}
    # A lesson's wording already belongs in the person's private catalogue.
    # Its provenance remains inspectable separately from the model view.
    return {'context': copy.deepcopy(capture['context']),
            'utteranceRoles': {'speakerRef': capture['context']['listenerRef'],
                               'listenerRef': capture['context']['personId']},
            'catalogue': copy.deepcopy(capture['catalogue']), 'behavior': result,
            'reports': [S.report_content(c, capture) for c in capture['catalogue']['claims'] if c['topic']=='world']}


def prepare(request, evidence=None):
    evidence = evidence or E.Store()
    A.fields(request, {'schema', 'schemaVersion', 'familyId', 'baselineImportSha256', 'cases'}, 'comparison request')
    A.schema(request, 'speakeasy-behavior-comparison-request')
    A.identifier(request['familyId'], 'comparison family')
    baseline = C.validate_import(evidence.read(request['baselineImportSha256']))['capture']
    validate_behavior(baseline)
    A.require(isinstance(request['cases'], list) and request['cases'], 'comparison cases absent')
    cases, seen = [], set()
    for case in request['cases']:
        A.fields(case, {'id', 'importSha256', 'question', 'candidates', 'learningConsequence'}, 'comparison case')
        A.identifier(case['id'], 'comparison id')
        A.require(all(isinstance(case[k], str) and case[k].strip() for k in ('question', 'learningConsequence')),
                  'comparison explanation absent')
        A.require(case['id'] not in seen, 'duplicate comparison case')
        seen.add(case['id'])
        captured = C.validate_import(evidence.read(case['importSha256']))['capture']
        channels = validate_behavior(captured)['channels']
        A.require(captured['context'] == baseline['context'], 'comparison context differs')
        A.require(captured['sourceState']['person']['worldKnowledge'] == baseline['sourceState']['person']['worldKnowledge'],
                  'comparison acquired report differs')
        A.require(isinstance(case['candidates'], list) and len(case['candidates']) >= 2, 'comparison needs alternatives')
        for candidate in case['candidates']:
            A.fields(candidate, {'id', 'text', 'act', 'emphasis'}, 'authored candidate')
            A.identifier(candidate['id'], 'candidate id')
            A.require(all(isinstance(v, str) and v.strip() for v in candidate.values()), 'empty candidate')
        A.require(len({c['id'] for c in case['candidates']}) == len(case['candidates']), 'duplicate candidate')
        changed = sorted(name for name in CHANNELS if channels[name] != baseline['behavior']['channels'][name])
        cases.append({**copy.deepcopy(case), 'changedChannels': changed,
                      'modelInput': model_view(captured),
                      'intervention': copy.deepcopy(evidence.read(case['importSha256'])['manifest']['scenario']['behaviorIntervention']),
                      'standing': 'unreviewed-authored-comparison', 'trainingEligible': False})
    return A.seal({'schema': 'speakeasy-behavior-comparison', 'schemaVersion': 1,
                   'request': copy.deepcopy(request), 'baselineInput': model_view(baseline),
                   'cases': cases, 'sourceGroup': 'document:' + baseline['sourceState']['person']['worldKnowledge']['acquisitions'][0]['source']['sha256'],
                   'standing': 'awaiting-behavior-review', 'trainingEligible': False,
                   'limits': ['authored-scenarios-not-play-observations', 'candidate-text-not-semantically-validated',
                              'one-source-family-not-independent-evaluation', 'no-trained-model',
                              'native-needs-active-work-goals-and-options-not-captured']})


def validate(value, evidence=None):
    A.unseal(value, 'speakeasy-behavior-comparison')
    A.require(prepare(value['request'], evidence) == value, 'comparison differs from source evidence')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        result = prepare(A.read(args.request))
        data = A.encoded(result) + b'\n'
        if args.check:
            A.require(args.output.read_bytes() == data, 'saved comparison differs')
        else:
            A.require(not args.output.exists() or args.output.read_bytes() == data,
                      'different comparison exists; choose a new output path')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(data)
        print(result['contentSha256'], result['standing'])
    except (J.ContractError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, 'REFUSED: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
