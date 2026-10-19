"""Typed camps/structures boundary: no raw tags/pointers/XY or hidden health."""
import math
import re
from hotstate.acquisition import fresh


def number(v):
    return type(v) is int or type(v) is float and math.isfinite(v)


def project_battlefield(raw, local, team):
    from hotstate.battlefield import VALIDATED_MAPS, STRUCTURE_LAYOUT
    meta=raw.get('meta',{});parts=raw.get('battlefield');core=raw.get('perspective')
    if (not isinstance(local,dict) or team!=local.get('team') or not isinstance(parts,dict)
            or meta.get('source')!='live' or meta.get('native_build')!=98348
            or meta.get('context_source') not in ('initdata_memory','initdata_native_fields')
            or not isinstance(core,dict) or not fresh(core)
            or not isinstance(meta.get('match_id'),str) or re.fullmatch('[0-9a-f]{64}',meta['match_id']) is None):
        return None
    clean={}
    for section,expected_count in (('camps',5),('structures',90)):
        p=parts.get(section)
        if (not isinstance(p,dict) or not fresh(p) or p.get('status')!='validated'
                or p.get('map_id') not in VALIDATED_MAPS or p.get('map_id')!=meta.get('map_id')
                or p.get('match_id')!=meta['match_id'] or p.get('section')!=section
                or type(p.get('local_id')) is not int or p['local_id']!=local.get('id')
                or type(p.get('team')) is not int or p['team']!=team
                or p.get('local_hero')!=local.get('hero') or p.get('native_session')!=core.get('native_session')
                or not isinstance(p.get('native_session'),str) or re.fullmatch('[0-9a-f]{64}',p['native_session']) is None
                or not number(p.get('mission_t_s')) or not number(meta.get('t_s'))
                or not 0<=p['mission_t_s']<=21600 or abs(p['mission_t_s']-meta['t_s'])>1
                or not number(p.get('read_window_s')) or not 0<=p['read_window_s']<=0.125):
            return None
        rows=p.get(section)
        if not isinstance(rows,list) or len(rows)!=expected_count:
            return None
        out=[];ids=set()
        catalogue={x['id']:x for x in STRUCTURE_LAYOUT['structures']}
        for row in rows:
            if not isinstance(row,dict):return None
            ident=row.get('id');visible=row.get('current_visible');state=row.get('state');owner=row.get('owner')
            if type(ident) not in (int,str) or ident in ids or visible is not None and type(visible) is not bool:
                return None
            ids.add(ident)
            if section=='camps':
                if type(ident) is not int or ident not in range(1,6):return None
                kind=('turret','turret','siege_troopers','siege_troopers','support')[ident-1]
                if row.get('kind')!=kind or state not in ('available','fighting','capture_available','captured','unavailable','unknown'):
                    return None
                cycle=row.get('cycle');remaining=row.get('respawn_s')
                if cycle is not None and (not isinstance(cycle,str) or re.fullmatch('[0-9a-f]{64}',cycle) is None):return None
                if remaining is not None and (type(remaining) is not int or not 0<=remaining<=600):return None
                if state=='unknown' and (owner is not None or remaining is not None or cycle is not None):return None
                timer=row.get('respawn_timer')
                clean_timer=None
                if timer is not None:
                    if not isinstance(timer,dict):return None
                    value=timer.get('remaining_s');paused=timer.get('paused')
                    if (visible is not True or state not in ('captured','unavailable')
                            or not number(value) or not 0<=value<=600
                            or type(paused) is not bool or remaining!=int(value)):
                        return None
                    clean_timer={'remaining_s':value,'paused':paused}
                out.append({'id':ident,'kind':kind,'state':state,'owner':owner,'current_visible':visible,'cycle':cycle,'respawn_s':remaining,'respawn_timer':clean_timer})
            else:
                if not isinstance(ident,str) or ident not in catalogue:return None
                spec=catalogue[ident];kind=row.get('kind');generation=row.get('generation')
                health=row.get('health_percent')
                if kind not in (spec['kind'],'tower_ruins' if spec['kind']=='tower' else spec['kind']) or state not in ('alive','destroyed','unknown'):
                    return None
                if generation is not None and (type(generation) is not int or not 0<=generation<0x400000):return None
                if state=='unknown' and (owner is not None or generation is not None or kind!=spec['kind']):return None
                if health is not None and (visible is not True or state!='alive' or not number(health) or not 0<=health<=100):return None
                if visible is True and state=='alive' and health is None:return None
                out.append({'id':ident,'kind':kind,'state':state,'owner':owner,'current_visible':visible,'generation':generation,'health_percent':health})
            if (visible is not True and state!='unknown'
                    or owner is not None and not (owner=='neutral' or type(owner) is int and owner in (0,1))):
                return None
        clean[section]={'t':p['mission_t_s'],'entries':out}
        if section=='structures':
            # The reader measures (component maximum - damage) / maximum.
            # This is NOT ShieldedHealthLabel's combined HUD numerator.
            clean[section]['health_basis']='life_component'
    return clean


def battlefield_key(packet):
    if not isinstance(packet,dict):return None
    result={}
    for section,extra in (('camps',('cycle',)),('structures',('generation',))):
        rows=[]
        for row in packet[section]['entries']:
            item={k:row[k] for k in ('id','kind','state','owner','current_visible',*extra)}
            if section=='camps':
                timer=row.get('respawn_timer')
                item['respawn_paused']=None if timer is None else timer['paused']
            if section=='structures':
                h=row['health_percent']
                item['health_band']=None if h is None else sum(h>c for c in (25,50,75))
            rows.append(item)
        result[section]=rows
    return result
