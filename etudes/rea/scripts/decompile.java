// decompile.java — décompile une liste de fonctions et les écrit sur disque.
//
// Utilisé sur le projet CervHotsMem (code déchiffré) : les adresses vivantes
// des fonctions identifiées par les scripts d'ancrage.
//
// Exécution : run_mem_scripts.bat decompile.java
// Sortie : C:\Users\Nauss\ghidra-projects\decomp\<adresse>.c + extrait console.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

import java.io.*;
import java.nio.charset.StandardCharsets;

public class decompile extends GhidraScript {

    private static final String OUT_DIR = "C:\\Users\\Nauss\\ghidra-projects\\decomp";
    private static final long[] TARGETS = {
        0x7ff62d037d34L,   // consommateur table des blocs replay
        0x7ff62d04f770L,   // consommateur table des blocs replay
        0x7ff62d050211L,   // consommateur table des blocs replay
    };

    @Override
    public void run() throws Exception {
        new File(OUT_DIR).mkdirs();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);

        for (long a : TARGETS) {
            Address addr = currentProgram.getAddressFactory()
                    .getDefaultAddressSpace().getAddress(a);
            Function f = getFunctionContaining(addr);
            if (f == null) {
                println("pas de fonction @ " + Long.toHexString(a));
                continue;
            }
            monitor.setMessage("décompilation " + f.getEntryPoint());
            DecompileResults res = di.decompileFunction(f, 120, monitor);
            if (!res.decompileCompleted()) {
                println("échec décompilation @ " + f.getEntryPoint() + " : "
                        + res.getErrorMessage());
                continue;
            }
            String code = res.getDecompiledFunction().getC();
            String path = OUT_DIR + "\\" + f.getEntryPoint().toString() + ".c";
            try (Writer w = new OutputStreamWriter(
                    new FileOutputStream(path), StandardCharsets.UTF_8)) {
                w.write(code);
            }
            println("OK " + f.getEntryPoint() + " -> " + path
                    + " (" + code.length() + " car.)");
            String[] lines = code.split("\n");
            for (int i = 0; i < Math.min(40, lines.length); i++) {
                println("   | " + lines[i]);
            }
        }
    }
}
