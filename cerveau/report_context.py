"""Explicit presentation context, not inferred from untrusted historical data.

Only the synthetic demo composer opts in. Generic schemas, journal markers,
paths and successful integrity checks never establish this context or trust.
"""


def synthetic_notice(synthetic=False):
    """Closed bool opt-in; no caller text/HTML and no positive attestation."""
    if type(synthetic) is not bool:
        raise ValueError('invalid_presentation_context')
    if not synthetic:
        return ''
    return ('<aside role="note" aria-label="Données fictives" '
            'style="position:sticky;top:0;z-index:10;box-sizing:border-box;'
            'padding:10px 14px;margin:0;background:#402d08;color:#fff1c2;'
            'border-bottom:2px solid #f4c673;overflow-wrap:anywhere">'
            '<strong>SYNTHETIC — données fictives.</strong> '
            'Aucune lecture native réelle ni validation HUD. Jamais CURRENT.</aside>')
