"""Offline-only structural position audit; never opens a process or coach.

Usage: python -m etudes.rea.scripts.audit_positions --image module.bin
       --heap heap.bin --manifest heap.json --map-id Volskaya --out audit.json
All-player output is private diagnostic evidence, NOT a player observation.
"""
import argparse
import json
from pathlib import Path

from hotstate.native import NativeReader, NativeUnavailable
from hotstate.positions import AlliedPositions
from hotstate.reader import DumpBackend


def audit(image, heap, manifest, map_id):
    backend = DumpBackend(Path(heap), Path(manifest), image=Path(image))
    try:
        reader = AlliedPositions(NativeReader(backend))
        result = reader.inspect_saved(map_id)
        # An observer is deliberately not converted to one of the ten bots.
        try:
            reader.read({'local_player': None})
        except NativeUnavailable as exc:
            observer_refusal = str(exc)
        else:
            raise AssertionError('Observer unexpectedly accepted')
        return {'scope': 'offline_structure_only', 'local_player': None,
                'publication_validated': False, 'minimap_calibration_validated': False,
                'observer_refusal': observer_refusal, 'sample': result}
    finally:
        backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--heap', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--map-id', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.image, args.heap, args.manifest, args.map_id)
    except NativeUnavailable as exc:
        result = {'scope': 'offline_structure_only', 'publication_validated': False,
                  'unavailable': str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if 'sample' in result else 1


if __name__ == '__main__':
    raise SystemExit(main())
