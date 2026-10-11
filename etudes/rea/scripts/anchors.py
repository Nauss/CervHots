# anchors.py — chasse aux ancres UI dans le binaire HotS (version Ghidra).
#
# Réalité vérifiée sur le binaire (etudes/rea/ETUDE.md §9) :
#  - les classes UI (CTimerFrame, CUnitStatusHealth…) n'ont PAS de RTTI complet
#    (pas de CompleteObjectLocator) ;
#  - leurs noms « .?AV<Classe>@@ » vivent dans une table .data (1892 entrées,
#    format {u64 commun, u64 0, nom}) ;
#  - il faut donc trouver QUI référence ces entrées : le code usine/binding UI.
#    Les xrefs en x64 sont des LEA RIP-relatives -> l'analyse Ghidra les connaît.
#
# Exécution (projet Ghidra « CervHots » analysé) :
#   analyzeHeadless <projet> CervHots -process hots_x64.exe -noanalysis \
#       -scriptPath <ce dossier> -postScript anchors.py
#
# Sortie : anchors.json = {classe: {entry, string_addr, xrefs: [fonctions]}}
from __future__ import print_function

import json

OUT_PATH = r"C:\Users\Nauss\ghidra-projects\anchors.json"

CLASS_NAMES = [
    "CTimerFrame", "CTimerWindow",
    "CUnitStatusHealth", "CUnitStatusHealthLabel", "CUnitStatusShieldedHealthBar",
    "CTeamHeroLevelFrame", "CPlayerHeroLevelFrame", "CUnitStatusLevel",
    "CPlayerDeathIndicatorFrame",
    "CHeroState",
    "CMinimap", "CMinimapUnitStatusPanel",
    "CGameStatsPanel", "CPlayerScoreResultFrame",
]

program = currentProgram
mem = program.getMemory()
rm = program.getReferenceManager()
fm = program.getFunctionManager()


def _to_byte_array(seq):
    try:
        import jarray
        return jarray.array([(x if x < 128 else x - 256) for x in seq], 'b')
    except ImportError:
        return bytes(bytearray(seq))


def find_pattern(byte_vals):
    start = mem.getMinAddress()
    return mem.findBytes(start, _to_byte_array(byte_vals), None, True, monitor)


def refs_of(addr):
    out = []
    for ref in rm.getReferencesTo(addr):
        f = fm.getFunctionContaining(ref.getFromAddress())
        out.append(str(f.getEntryPoint()) if f is not None
                   else "data:" + str(ref.getFromAddress()))
    return sorted(set(out))


results = {}
for cls in CLASS_NAMES:
    monitor.setMessage("anchor: " + cls)
    name = ".?AV%s@@" % cls
    s_addr = find_pattern([ord(c) for c in name])
    if s_addr is None:
        results[cls] = {"error": "nom absent"}
        print("%-32s nom absent" % cls)
        continue
    entry = s_addr.subtract(16)
    entry_refs = refs_of(entry)
    str_refs = refs_of(s_addr)
    results[cls] = {
        "string_addr": str(s_addr),
        "entry_addr": str(entry),
        "xrefs_entry": entry_refs[:20],
        "xrefs_string": str_refs[:20],
    }
    print("%-32s entry=%s xrefs=%d (entree) + %d (nom)"
          % (cls, str(entry), len(entry_refs), len(str_refs)))

with open(OUT_PATH, "w") as fh:
    json.dump(results, fh, indent=2)
print("ECRIT: " + OUT_PATH)
