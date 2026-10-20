"""Typed Volskaya groups and conservative CURRENT visibility projection.

No hidden hero fields or public raw tags/pointers/positions. Structure health
is read only after CURRENT visibility and fixed structural catalogue matching.
These functions execute only inside a bounded recorded acquisition.
"""
import hashlib
import struct
from .native import NativeUnavailable
from .positions import AlliedPositions
from .visibility import CurrentVisibility, _UnknownVisibility

DEFENDERS = {1: ('OverwatchTurret','OverwatchMechanic'), 2: ('OverwatchTurret','OverwatchMechanic'),
             3: ('MercSiegeTrooperDefender',)*3, 4: ('MercSiegeTrooperDefender',)*3,
             5: ('MercDefenderMeleeIndividual',)}


class PositionMemo:
    def __init__(self, helper):
        self.helper, self.values = helper, {}

    def _xy(self, n, unit):
        if unit not in self.values:
            self.values[unit] = self.helper._xy(n, unit)
        return self.values[unit]


def group_members(n, reader, index, local_id, helper):
    defenders = getattr(reader, 'CAMP_DEFENDERS', DEFENDERS)
    laners = getattr(reader, 'CAMP_LANERS', {3: ('MercSiegeTrooperLaner',), 4: ('MercSiegeTrooperLaner',)})
    ref = n.value(n.base+0x3D0C920+index*780+0xDF21E)
    slots = n.value(n.base+0x4020970,'Q')
    if slots != n.base+0x4020980 or ref>>16 == 0 or (ref & 65535) <= 1:
        raise NativeUnavailable('reference_groupe_camp_invalide')
    gen, _, refs, kind, _, ptr = struct.unpack('<HHHBBQ',n.read(slots+(ref & 65535)*16,16))
    if gen != ref>>16 or not refs or kind != 22:
        raise NativeUnavailable('type_generation_groupe_camp_invalide')
    reader._pointer(ptr)
    vt, owner = struct.unpack('<QI',n.read(ptr,12))
    count = n.value(ptr+0x18,'i')
    if vt != n.base+40586608 or owner != ref or not 0 <= count <= len(defenders[index]):
        raise NativeUnavailable('objet_groupe_camp_invalide')
    array = n.value(ptr+0x28,'Q')
    tags = struct.unpack('<'+'I'*count,n.read(reader._pointer(array,alignment=4),count*4)) if count else ()
    if len(set(tags)) != len(tags):
        raise NativeUnavailable('membres_groupe_camp_ambigus')
    result = []
    for tag in tags:
        unit = reader._resolve(n,tag)
        if unit is None:
            result.append({'tag':tag,'role':'unknown','current_visible':None})
            continue
        name = reader._unit_type(n,unit)
        role = ('defender' if name in defenders[index] else 'departed_laner'
                if name in laners.get(index, ()) else 'unknown')
        row = {'tag':tag,'role':role,'unit_type':name,'owner':n.value(unit+0x44,'B'),
               'alive':n.value(unit+0x39,'B') & 6 == 0,'current_visible':None}
        if role == 'defender' and row['alive']:
            try:
                row['current_visible'] = CurrentVisibility(n)._current(n,unit,local_id+1,helper)
            except _UnknownVisibility as exc:
                row['visibility_reason'] = str(exc)
        result.append(row)
    return {'reference':ref,'members':result}


def camp_details(n, reader, rows, local_id, *, verify_visibility=True):
    if verify_visibility:CurrentVisibility(n)._verify(n)
    helper = PositionMemo(AlliedPositions(n,profile=reader.position_profile))
    for row in rows:
        unit = reader._resolve(n,row['beacon_tag'])
        row['anchor_current_visible'] = None
        if unit is not None:
            packed = n.value(unit+(0x20 if n.value(unit+0x3A,'B') & 4 else 0x18),'Q')
            catalog = reader._pointer(packed & ~31)
            try:
                # An always-visible minimap beacon is NOT camp fog permission.
                row['anchor_current_visible'] = CurrentVisibility(n)._point(n,unit,local_id+1,helper,catalog)
            except _UnknownVisibility as exc:
                row['anchor_visibility_reason'] = str(exc)
        row['defender_group'] = group_members(n,reader,row['index'],local_id,helper)
    return rows


def camp_public(row, *, kinds=('turret','turret','siege_troopers','siege_troopers','support')):
    ident = row['index']
    result = {'id':ident,'kind':kinds[ident-1],
              'state':'unknown','owner':None,'current_visible':row.get('anchor_current_visible'),
              'cycle':None,'respawn_s':None,'respawn_timer':None}
    if result['current_visible'] is not True:
        return result
    members = row['defender_group']['members']
    living = [m for m in members if m.get('role') == 'defender' and m.get('alive')]
    all_visible = bool(living) and all(m.get('current_visible') is True for m in living)
    no_unknown = all(m.get('role') != 'unknown' for m in members)
    # A visible anchor never overrides hidden living defenders, irrespective
    # of the raw state code (including contradictory transition snapshots).
    if not no_unknown or living and not all_visible:
        return result
    code = row['state_code']
    if row['enabled'] and code in (0,1) and all_visible and no_unknown:
        result.update(state='available' if code == 0 else 'fighting',owner='neutral')
    elif row['enabled'] and code == 3 and row['capture_enabled'] and no_unknown:
        result.update(state='capture_available',owner='neutral')
    elif code == 2 and type(row['last_capture_team']) is int and row['last_capture_team'] in (0,1) and (row['respawn']['remaining_s'] or 0)>0:
        result.update(state='captured',owner=row['last_capture_team'])
    elif not row['enabled'] or code in (2,4,5):
        result['state'] = 'unavailable'
    if result['state'] != 'unknown':
        # Never expose even a hash of hidden/departed/dead member identities.
        if members and all(m.get('role')=='defender' and m.get('alive') and m.get('current_visible') is True for m in members):
            result['cycle'] = hashlib.sha256(struct.pack('<'+'I'*len(members),*sorted(m['tag'] for m in members))).hexdigest()
        remaining = row['respawn']['remaining_s']
        if remaining is not None and result['state'] in ('captured','unavailable'):
            result['respawn_s'] = int(remaining)
            # Preserve the native fixed4096 value and pause state. The legacy
            # integer is the HUD's truncation, not time until camp availability.
            # Birth/preload, hibernation and availability are distinct states.
            result['respawn_timer'] = {'remaining_s':remaining,'paused':row['respawn']['paused']}
    return result


def structure_details(n, reader, census, units, local_id, layout, *, verify_visibility=True):
    if verify_visibility:CurrentVisibility(n)._verify(n)
    helper = PositionMemo(AlliedPositions(n,profile=reader.position_profile))
    by_point = {(s['x_fixed'],s['y_fixed']):s for s in layout['structures']}
    matched, ambiguous = {}, set()
    for row in census['structures']:
        unit = units[row['tag']]
        x,y = helper._xy(n,unit)
        spec = by_point.get((round(x*4096),round(y*4096)))
        if spec is None:
            continue
        name = row['unit_type']
        if name != spec['unit_type'] and not (spec['kind'] == 'tower' and name == 'TownCannonTowerDead'):
            continue
        ident = spec['id']
        if ident in matched:
            ambiguous.add(ident)
            continue
        item = dict(row,id=ident,current_visible=None)
        try:
            item['current_visible'] = CurrentVisibility(n)._current(n,unit,local_id+1,helper)
        except _UnknownVisibility as exc:
            item['visibility_reason'] = str(exc)
        item['health_percent'] = None
        if item['current_visible'] is True and item['state'] == 'alive':
            maximum,damage = n.value(unit+0x220,'i'),n.value(unit+0x22C,'i')
            if not 0 < maximum <= 1000000*4096 or not 0 <= damage <= maximum:
                raise NativeUnavailable('vie_structure_visible_invalide')
            item['health_percent'] = 100*(maximum-damage)/maximum
            # Private diagnostic components, NOT a claim that the selected
            # target's combined HUD numerator is life alone. Current property
            # cases0/2 and8/10 in getter2050820 use these four offsets.
            shields,shield_damage = n.value(unit+0x224,'i'),n.value(unit+0x230,'i')
            if not 0 <= shields <= 1000000*4096 or not 0 <= shield_damage <= shields:
                raise NativeUnavailable('bouclier_structure_visible_invalide')
            item['visible_vitals'] = {'life':(maximum-damage)/4096,'life_max':maximum/4096,
                'shields':(shields-shield_damage)/4096,'shields_max':shields/4096}
        matched[ident] = item
    return [{'id':spec['id'],'spec':spec,'observation':None if spec['id'] in ambiguous else matched.get(spec['id'])}
            for spec in layout['structures']]


def structure_public(row):
    spec, observation = row['spec'],row['observation']
    result = {'id':spec['id'],'kind':spec['kind'],'state':'unknown','owner':None,
              'generation':None,'health_percent':None,'current_visible':None if observation is None else observation['current_visible']}
    if observation is not None and result['current_visible'] is True:
        result.update(kind=observation['kind'],state=observation['state'],owner=observation['team'],generation=observation['generation'],health_percent=observation.get('health_percent'))
    return result
