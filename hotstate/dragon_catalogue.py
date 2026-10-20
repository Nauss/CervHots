"""Dragon fixed-coordinate catalogue shape/integrity, not release permission.

The initial native catalogue remains candidate until independent same-match
replay qualification. Publication is separately closed in dragon_battlefield.
"""
import hashlib
import json
import re
from pathlib import Path
from .battlefield import structure_kind
from .native import NativeUnavailable

STRUCTURE_LAYOUT = json.loads((Path(__file__).parent/'profiles/98348-dragon-structures.json').read_text(encoding='utf-8'))


def validate_layout(layout):
    if (not isinstance(layout, dict) or layout.get('build') != 98348
            or layout.get('map') != 'DragonShire' or layout.get('schema_version') != 1):
        raise NativeUnavailable('catalogue_structures_dragon_invalide')
    rows = layout.get('structures')
    if not isinstance(rows, list) or len(rows) != 90:
        raise NativeUnavailable('catalogue_structures_dragon_incomplet')
    ids, points = set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise NativeUnavailable('catalogue_structures_dragon_invalide')
        ident, x, y = row.get('id'), row.get('x_fixed'), row.get('y_fixed')
        name, kind, team = row.get('unit_type'), row.get('kind'), row.get('team')
        if (not isinstance(ident, str) or re.fullmatch(r'dragon-[0-9]{3}', ident) is None
                or ident in ids or type(x) is not int or type(y) is not int
                or not 0 <= x <= 1024*4096 or not 0 <= y <= 1024*4096
                or (x, y) in points or not isinstance(name, str)
                or kind != structure_kind(name) or kind is None or kind == 'tower_ruins'
                or type(team) is not int or team not in (0, 1)):
            raise NativeUnavailable('catalogue_structures_dragon_invalide')
        ids.add(ident)
        points.add((x, y))
    if ids != {f'dragon-{i:03d}' for i in range(1, 91)}:
        raise NativeUnavailable('identifiants_catalogue_dragon_incomplets')
    return layout


def qualified_layout():
    """Validate fixed layout integrity; this NEVER grants recipe permission."""
    layout = validate_layout(STRUCTURE_LAYOUT)
    canonical = sorted(({key:s[key] for key in ('unit_type', 'kind', 'team', 'x_fixed', 'y_fixed')}
                        for s in layout['structures']), key=lambda s:(s['x_fixed'], s['y_fixed'], s['unit_type']))
    encoded = json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()
    if (hashlib.sha256(encoded).hexdigest() != layout.get('catalogue_sha256')
            or not isinstance(layout.get('raw_sha256'), str)
            or re.fullmatch('[0-9a-f]{64}', layout['raw_sha256']) is None):
        raise NativeUnavailable('empreinte_catalogue_structures_dragon_invalide')
    return layout
