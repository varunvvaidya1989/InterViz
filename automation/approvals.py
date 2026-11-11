"""Versioned approval intents; this module never grants controller authority."""
import re

from .runtime import digest


def approval_cards(ledger, policy, controller_revision=None):
    cards = []
    for release in ledger['releases']:
        if release['state'] == 'RELEASED':
            continue
        release_id = release['id']
        manifest = ledger['kv'].get('plan:' + release_id) or {}
        if (release.get('plan_hash') and release.get('plan_approved_hash') != release['plan_hash']
                and manifest.get('hash') == release['plan_hash']):
            document = manifest.get('document') or {}
            revision = manifest.get('revision') or controller_revision
            if document and revision:
                cards.append({'kind': 'plan', 'release_id': release_id, 'title': release['title'],
                              'expected_hash': release['plan_hash'], 'revision': revision,
                              'stories': [{'title': s['title'], 'acceptance': s['acceptance']}
                                          for s in document.get('user_stories', [])],
                              'sections': {k: document.get(k) for k in ('ui_ux', 'architecture', 'operations', 'acceptance_tests', 'delivery_tasks')},
                              'url': manifest.get('pr_url')})
        candidate = ledger['kv'].get('candidate:' + release_id)
        sha = release.get('candidate_sha')
        if (candidate and sha and candidate.get('commit_sha') == sha
                and release.get('qa_passed') and sha == release.get('qa_sha') == release.get('integration_sha')
                and release.get('release_approved_sha') != sha
                and candidate.get('policy_sha256') == digest(policy)):
            cards.append({'kind': 'release', 'release_id': release_id, 'title': release['title'],
                          'expected_hash': digest(candidate), 'revision': sha,
                          'changelog': candidate.get('changelog', ''),
                          'publication_enabled': bool(policy['authority']['production_release_enabled'])})
    for card in cards:
        card['id'] = intent_id(card)
    return cards


def intent_id(value):
    return digest({k: value[k] for k in ('kind', 'release_id', 'expected_hash', 'revision')})


def validate_intent(value):
    if not isinstance(value, dict) or set(value) != {'kind', 'release_id', 'expected_hash', 'revision'}:
        raise ValueError('Invalid approval request.')
    if value['kind'] not in {'plan', 'release'} or not isinstance(value['release_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value['release_id']):
        raise ValueError('Invalid approval target.')
    if not isinstance(value['expected_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['expected_hash']):
        raise ValueError('Invalid approval version.')
    if not isinstance(value['revision'], str) or not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', value['revision']):
        raise ValueError('Invalid approval revision.')
    return value
