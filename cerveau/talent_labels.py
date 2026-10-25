"""Pure, fail-closed documentary lookup, NOT a native/build qualification.

Only the pinned Sonya source exists here. Its version does not prove build98348
or a native slot mapping. Therefore the chosen label ALWAYS remains unknown.
The source's English name is shown separately, never translated or promoted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

SOURCE_FILE = 'cerveau/data/talent-labels/sonya.json'
SOURCE_SHA256 = 'e0b243fa3aa4b9f1cff2f1e0c1e52e0b4d3ed8834723bf4cd85c24dad1559755'
SOURCE_VERSION = '2dcbbf65f81bc3ce85926a5f90b6d8b44d1e4027'
SOURCE_LIMIT = 65536


def source_bytes():
    """Only a fixed packaged file, bounded read, no global KB or key-derived path."""
    try:
        with (Path(__file__).resolve().parent/'data/talent-labels/sonya.json').open('rb') as stream:
            return stream.read(SOURCE_LIMIT + 1)
    except OSError:
        return b''


def resolve_selected(build, hero, tier, data):
    """Resolve only an already selected exact native identity against pinned bytes.

    `sort` and array order NEVER identify a choice. Array index is used only as
    a JSON pointer AFTER exact talentTreeId + required-level matching. Even a
    unique match cannot prove that this old source describes the recorded build
    or native slot. No caller-supplied label/build metadata is trusted.
    """
    result = dict(label=None, status='unknown', reason='selection_unknown',
                  missing_provenance=['selected_identity'], source_match=None)
    if type(tier) is not dict or tier.get('status') != 'selected':
        return result
    if type(build) is not int or build != 98348:
        result.update(reason='build_unknown', missing_provenance=['exact_build'])
        return result
    slot, ident = tier.get('slot'), tier.get('catalog_id')
    required = tier.get('required_level')
    if (type(slot) is not int or not 1 <= slot <= 32
            or type(tier.get('tier')) is not int or not 1 <= tier['tier'] <= 31
            or type(required) is not int or not 1 <= required <= 30
            or type(ident) is not str or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,127}', ident)):
        result.update(reason='selected_identity_invalid')
        return result
    if type(hero) is not str or hero != 'sonya':
        result.update(reason='hero_source_unavailable', missing_provenance=['hero_source'])
        return result
    if (type(data) is not bytes or len(data) > SOURCE_LIMIT
            or hashlib.sha256(data).hexdigest() != SOURCE_SHA256):
        result.update(reason='source_integrity_refused', missing_provenance=['pinned_source_bytes'])
        return result
    try:
        source = json.loads(data)
        # Explicit source hero identity, not a filename alone.
        if source.get('shortName') != 'sonya':
            raise ValueError('source_hero')
        entries = source['talents'].get(str(required), [])
        matches = [(i, row) for i, row in enumerate(entries)
                   if type(row) is dict and row.get('talentTreeId') == ident]
        if len(matches) != 1:
            result.update(reason='source_identity_ambiguous' if matches else 'source_identity_absent',
                          missing_provenance=['unique_source_identity'])
            return result
        index, row = matches[0]
        name = row.get('name')
        if type(name) is not str or not 1 <= len(name) <= 160 or any(ord(c) < 32 for c in name):
            raise ValueError('source_label')
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        result.update(reason='source_schema_refused', missing_provenance=['valid_source_schema'])
        return result
    result.update(reason='source_build_and_slot_unproven',
        missing_provenance=['exact_build', 'native_slot_mapping', 'french_label'],
        source_match=dict(label=name, language='en', basis='documentary_only_not_chosen_label',
            provenance=dict(file=SOURCE_FILE, sha256=SOURCE_SHA256, version=SOURCE_VERSION,
                origin_file='hero/sonya.json', key=f'/talents/{required}/{index}/name',
                identity_key=f'/talents/{required}/{index}/talentTreeId')))
    return result


REASONS = dict(
    source_build_and_slot_unproven='build exact non attesté ; correspondance slot natif non attestée ; français absent',
    selection_unknown='aucun choix établi', build_unknown='build inconnu',
    selected_identity_invalid='identité choisie invalide ou slot absent',
    hero_source_unavailable='source exacte du héros absente',
    source_integrity_refused='octets source épinglés absents ou altérés',
    source_identity_ambiguous='identité source ambiguë', source_identity_absent='identité source absente au niveau requis',
    source_schema_refused='schéma source invalide')


def detail_text(detail):
    """Plain French text, HTML escapes it at its existing text-node boundary."""
    selection, resolution = detail['selection_provenance'], detail['resolution']
    lines = [f"  palier {detail['tier']} / slot natif {detail['slot']} / identifiant {detail['catalog_id']} : libellé choisi inconnu.",
             '    Motif : '+REASONS[resolution['reason']]+'.',
             f"    Sélection enregistrée (non authentifiée) : SHA256 {selection['journal_sha256']}, séquence {selection['sequence']}, clé {selection['key']}, build {selection['build']}, héros {selection['hero']}."]
    match = resolution['source_match']
    if match is not None:
        p = match['provenance']
        lines.extend([f"    Source {match['language']} — documentaire seulement, PAS le libellé choisi qualifié : {match['label']}.",
                      f"    Provenance documentaire : {p['file']} ; SHA256 {p['sha256']} ; version {p['version']} ; clé {p['key']} ; identité {p['identity_key']}."])
    else:
        lines.append('    Aucun libellé source retenu ; provenance manquante : '+', '.join(resolution['missing_provenance'])+'.')
    return lines
