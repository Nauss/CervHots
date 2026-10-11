// anchors2.java — xrefs des ANCRAGES RÉELS du moteur Storm (chaînes littérales).
//
// Découverte (etudes/rea/ETUDE.md §9-10) : le moteur possède son propre registre
// de classes, indexé par les chaînes « c_classId<Classe> » / « c_classId<Classe>Name »
// (1156 classes : CAbil, CBehavior*, CActor*, CTalent, CValidator*, CGameUI…).
// Ces chaînes littérales sont référencées par le code d'enregistrement -> xrefs
// exploitables (contrairement à la table .?AV sans RTTI).
//
// Exécution :
//   analyzeHeadless <projet> CervHots -process hots_x64.exe -noanalysis \
//       -scriptPath <ce dossier> -postScript anchors2.java
//
// Sortie : anchors2.json + tableau console.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;

import java.io.PrintWriter;
import java.util.*;

public class anchors2 extends GhidraScript {

    private static final String OUT_PATH = "C:\\Users\\Nauss\\ghidra-projects\\anchors2.json";

    private static final String[] ANCHORS = {
        "replay.tracker.events",
        "CBehaviorUnitTracker",
        "c_classIdCBehaviorUnitTracker",
        "c_classIdCBehaviorUnitTrackerName",
        "c_classIdCTalent",
        "c_classIdCGameUI",
        "c_classIdCValidatorPlayerTalent",
        "c_classIdCAccumulatorTrackedUnitCount",
        ".StormReplay",
    };

    @Override
    public void run() throws Exception {
        StringBuilder json = new StringBuilder("{\n");
        boolean first = true;

        for (String target : ANCHORS) {
            monitor.setMessage("xref: " + target);
            Address sAddr = findLiteral(target);
            if (sAddr == null) {
                println(String.format("%-42s chaine absente", target));
                if (!first) json.append(",\n");
                json.append("  \"").append(target).append("\": {\"error\": \"chaine absente\"}");
                first = false;
                continue;
            }
            Set<String> refs = new TreeSet<>();
            for (Reference r : getReferencesTo(sAddr)) {
                Function f = getFunctionContaining(r.getFromAddress());
                refs.add(f != null ? f.getEntryPoint().toString()
                                   : "data:" + r.getFromAddress().toString());
            }
            println(String.format("%-42s @%s -> %d xref(s) : %s",
                    target, sAddr, refs.size(), refs.toString()));
            if (!first) json.append(",\n");
            first = false;
            json.append("  \"").append(target).append("\": {")
                .append("\"addr\": \"").append(sAddr).append("\", ")
                .append("\"xrefs\": ").append(toJsonArray(refs)).append("}");
        }

        json.append("\n}\n");
        try (PrintWriter pw = new PrintWriter(OUT_PATH, "UTF-8")) {
            pw.print(json.toString());
        }
        println("ECRIT: " + OUT_PATH);
    }

    /** Recherche d'une chaîne littérale ASCII, quel que soit le bloc mémoire. */
    private Address findLiteral(String s) {
        byte[] needle;
        try {
            needle = s.getBytes("US-ASCII");
        } catch (Exception e) {
            return null;
        }
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.isInitialized()) {
                continue;
            }
            Address hit = currentProgram.getMemory().findBytes(
                    b.getStart(), needle, null, true, monitor);
            if (hit != null && b.contains(hit)) {
                return hit;
            }
        }
        return null;
    }

    private String toJsonArray(Set<String> items) {
        StringBuilder sb = new StringBuilder("[");
        boolean firstIt = true;
        for (String s : items) {
            if (!firstIt) sb.append(", ");
            firstIt = false;
            sb.append("\"").append(s).append("\"");
        }
        return sb.append("]").toString();
    }
}
