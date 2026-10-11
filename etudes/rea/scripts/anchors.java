// anchors.java — chasse aux xrefs des entrées de registre UI (binaire HotS).
// Voir etudes/rea/ETUDE.md §9 : les classes UI n'ont pas de RTTI complet ;
// leurs noms « .?AV<Classe>@@ » vivent dans une table .data ({u64, u64 0, nom}).
// Ce script localise chaque entrée et liste les fonctions qui la référencent.
//
// Exécution :
//   analyzeHeadless <projet> CervHots -process hots_x64.exe -noanalysis \
//       -scriptPath <ce dossier> -postScript anchors.java
//
// Sortie : anchors.json + tableau dans la console.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

import java.io.PrintWriter;
import java.util.*;

public class anchors extends GhidraScript {

    private static final String OUT_PATH = "C:\\Users\\Nauss\\ghidra-projects\\anchors.json";

    private static final String[] CLASSES = {
        "CTimerFrame", "CTimerWindow",
        "CUnitStatusHealth", "CUnitStatusHealthLabel", "CUnitStatusShieldedHealthBar",
        "CTeamHeroLevelFrame", "CPlayerHeroLevelFrame", "CUnitStatusLevel",
        "CPlayerDeathIndicatorFrame",
        "CHeroState",
        "CMinimap", "CMinimapUnitStatusPanel",
        "CGameStatsPanel", "CPlayerScoreResultFrame",
    };

    @Override
    public void run() throws Exception {
        StringBuilder json = new StringBuilder("{\n");
        boolean firstClass = true;

        for (String cls : CLASSES) {
            monitor.setMessage("anchor: " + cls);
            String name = ".?AV" + cls + "@@";
            Address sAddr = currentProgram.getMemory().findBytes(
                    currentProgram.getMinAddress(), name.getBytes("US-ASCII"), null, true, monitor);
            if (sAddr == null) {
                println(String.format("%-32s nom absent", cls));
                if (!firstClass) json.append(",\n");
                json.append("  \"").append(cls).append("\": {\"error\": \"nom absent\"}");
                firstClass = false;
                continue;
            }
            Address entry = sAddr.subtract(16);

            Set<String> xrefsEntry = new TreeSet<>();
            Set<String> xrefsString = new TreeSet<>();
            for (Reference r : getReferencesTo(entry)) {
                Function f = getFunctionContaining(r.getFromAddress());
                xrefsEntry.add(f != null ? f.getEntryPoint().toString()
                                         : "data:" + r.getFromAddress().toString());
            }
            for (Reference r : getReferencesTo(sAddr)) {
                Function f = getFunctionContaining(r.getFromAddress());
                xrefsString.add(f != null ? f.getEntryPoint().toString()
                                          : "data:" + r.getFromAddress().toString());
            }

            println(String.format("%-32s entry=%s xrefs=%d (entree) + %d (nom)",
                    cls, entry, xrefsEntry.size(), xrefsString.size()));

            if (!firstClass) json.append(",\n");
            firstClass = false;
            json.append("  \"").append(cls).append("\": {")
                .append("\"string_addr\": \"").append(sAddr).append("\", ")
                .append("\"entry_addr\": \"").append(entry).append("\", ")
                .append("\"xrefs_entry\": ").append(toJsonArray(xrefsEntry)).append(", ")
                .append("\"xrefs_string\": ").append(toJsonArray(xrefsString)).append("}");
        }

        json.append("\n}\n");
        try (PrintWriter pw = new PrintWriter(OUT_PATH, "UTF-8")) {
            pw.print(json.toString());
        }
        println("ECRIT: " + OUT_PATH);
    }

    private String toJsonArray(Set<String> items) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (String s : items) {
            if (!first) sb.append(", ");
            first = false;
            sb.append("\"").append(s).append("\"");
        }
        return sb.append("]").toString();
    }
}
