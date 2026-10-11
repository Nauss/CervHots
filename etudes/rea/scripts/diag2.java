// diag2.java — test de xrefs sur des chaînes SÛRES (libcurl) vs chaînes moteur.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class diag2 extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] tests = {
            "Can't complete SOCKS4 connection",
            "Last-Modified: %s",
            "replay.tracker.events",
            "c_classIdCTalent",
        };
        for (String t : tests) {
            Address a = findLiteral(t);
            if (a == null) {
                println(String.format("%-34s chaine absente", t));
                continue;
            }
            int n = 0;
            StringBuilder who = new StringBuilder();
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(a);
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                if (who.length() < 120) {
                    who.append(f != null ? f.getEntryPoint().toString() : "data:" + r.getFromAddress()).append(" ");
                }
                n++;
            }
            println(String.format("%-34s @%s xrefs=%d  %s", t, a, n, who.toString()));
        }
    }

    private Address findLiteral(String s) {
        try {
            byte[] needle = s.getBytes("US-ASCII");
            for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
                if (!b.isInitialized()) continue;
                Address hit = currentProgram.getMemory().findBytes(b.getStart(), needle, null, true, monitor);
                if (hit != null && b.contains(hit)) return hit;
            }
        } catch (Exception e) {
        }
        return null;
    }
}
