"""Minimized disk-only cooperative STOP requests, never a liveness probe."""
import json
import os
from .control_io import absolute, parent, file_handle, regular

SCHEMA = 'passive_stop_control_v1'
MAX_CONTROL = 16384


def _paths(output, stop):
    output, stop = absolute(output), absolute(stop)
    if stop == output or output in stop.parents or stop == output.parent/'passive-session.lock':
        raise ValueError('overlap')
    return output, stop


def _closed(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_key')
        result[key] = value
    return result


def record_control(output, stop):
    output, stop = _paths(output, stop)
    row = {'schema': SCHEMA, 'output_dir': str(output), 'stop_file': str(stop)}
    raw = (json.dumps(row, ensure_ascii=True)+'\n').encode('ascii')
    if len(raw) > MAX_CONTROL:
        raise ValueError('control_too_large')
    control = output/'control.json'
    with parent(stop), parent(control) as fd_parent, file_handle(control, fd_parent, create=True) as fd:
        with os.fdopen(os.dup(fd), 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def request_stop(output, stop):
    result = {'event': 'stop_request', 'state': 'refused', 'reason': 'control_or_target_unavailable',
              'reader_active': None, 'current_permission': False,
              'summary_fr': 'Signal refuse ; activite du lecteur inconnue.'}
    try:
        output, stop = _paths(output, stop)
        control = output/'control.json'
        with parent(stop) as stop_parent, parent(control) as control_parent:
            with file_handle(control, control_parent) as fd:
                regular(os.fstat(fd))
                if os.fstat(fd).st_size > MAX_CONTROL:
                    raise ValueError('control_too_large')
                with os.fdopen(os.dup(fd), 'rb') as stream:
                    raw = stream.read(MAX_CONTROL + 1)
                if len(raw) > MAX_CONTROL or not raw.endswith(b'\n'):
                    raise ValueError('invalid_control')
                record = json.loads(raw, object_pairs_hook=_closed)
                if record != {'schema': SCHEMA, 'output_dir': str(output), 'stop_file': str(stop)}:
                    raise ValueError('control_mismatch')
                # The only write target comes from argv, not from metadata.
                try:
                    with file_handle(stop, stop_parent, create=True) as stop_fd:
                        os.fsync(stop_fd)
                    state = 'published'
                except FileExistsError:
                    with file_handle(stop, stop_parent) as stop_fd:
                        regular(os.fstat(stop_fd))
                    state = 'already_present'
        result.update(state=state, reason='signal_only', summary_fr=(
            'Signal STOP publie ; fermeture effective non verifiee.' if state == 'published' else
            'Signal STOP deja present ; fermeture effective non verifiee.'))
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    return result
