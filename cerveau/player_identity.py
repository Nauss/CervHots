"""Bounded, noncredential local player-label input; never discovers identities."""
from pathlib import Path
import stat
import unicodedata


MAX_LABEL_BYTES = 261  # 64 UTF8 codepoints + optional BOM and CRLF.


def read_player_label(path):
    """Read one explicit UTF8/UTF8sig label, not a proof of active identity.

    One terminal LF/CRLF is permitted; other line breaks, controls and outer
    whitespace are ambiguous. Errors contain neither file contents nor paths.
    Python strings are not securely zeroizable.
    """
    try:
        path = Path(path)
        info = path.stat()
        if not path.is_absolute() or not stat.S_ISREG(info.st_mode) or info.st_size > MAX_LABEL_BYTES:
            raise ValueError
        with path.open('rb') as stream:
            raw = stream.read(MAX_LABEL_BYTES + 1)
        if len(raw) > MAX_LABEL_BYTES:
            raise ValueError
        label = raw.decode('utf-8-sig')
        if label.endswith('\r\n'):
            label = label[:-2]
        elif label.endswith('\n'):
            label = label[:-1]
        if (not 2 <= len(label) <= 64 or label != label.strip()
                or any(unicodedata.category(c).startswith('C') or
                       (c.isspace() and c != ' ') for c in label)):
            raise ValueError
        return label
    except (OSError, UnicodeError, ValueError, TypeError):
        raise ValueError('private_identity_unavailable') from None
