// xrefs3.java — qui référence quoi (générique) : table des blocs, helpers.
//
// Cible de cette passe : la table des blocs replay (DAT_7ff62f63e240) et son
// registreur (FUN_7ff62bf80150) — les écritureurs de blocs (dont le bloc
// tracker, id 0x15) doivent être atteignables depuis là.
//
// Exécution : run_mem_scripts.bat xrefs3.java
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

import java.util.*;

public class xrefs3 extends GhidraScript {

    private static final long[] TARGETS = {
        0x7ff62d04e510L,   // constructeur de writer de bloc typé
        0x7ff62d04b8f0L,   // constructeur d'objet événement (0x830)
        0x7ff62bff32c0L,   // ouverture de bloc (game/message/load_info…)
        0x7ff62d072530L,   // allocation d'événement (taille 0x830)
    };

    @Override
    public void run() throws Exception {
        for (long a : TARGETS) {
            Address addr = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(a);
            Function target = getFunctionContaining(addr);
            println(String.format("=== %x (%s) ===", a,
                    target != null ? target.getName() : "data"));
            ReferenceIterator it = currentProgram.getReferenceManager()
                    .getReferencesTo(addr);
            Map<String, Integer> callers = new TreeMap<>();
            int n = 0;
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                String key = f != null ? f.getEntryPoint().toString()
                                       : "data:" + r.getFromAddress().toString();
                callers.merge(key, 1, Integer::sum);
                n++;
            }
            println("   total xrefs: " + n);
            int shown = 0;
            for (Map.Entry<String, Integer> e : callers.entrySet()) {
                println("   " + e.getKey() + "  (x" + e.getValue() + ")");
                if (++shown >= 25) {
                    println("   …");
                    break;
                }
            }
        }
    }
}
