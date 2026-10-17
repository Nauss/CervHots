// Export functions at observed .pdata boundaries; transient analysis only.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class ExportFunctions extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) throw new IllegalArgumentException("outdir and function entries required");
        File output = new File(args[0]); output.mkdirs();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try {
            for (int i = 1; i < args.length; i++) {
                long value = Long.parseUnsignedLong(args[i].replace("0x", ""), 16);
                Address address = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
                Function function = getFunctionAt(address);
                if (function == null) {
                    disassemble(address);
                    function = createFunction(address, null);
                }
                if (function == null) { println("MISSING_FUNCTION " + address); continue; }
                DecompileResults result = decompiler.decompileFunction(function, 90, monitor);
                if (!result.decompileCompleted()) {
                    println("DECOMPILE_FAILED " + address + " " + result.getErrorMessage()); continue;
                }
                String code = result.getDecompiledFunction().getC();
                try (Writer writer = new OutputStreamWriter(new FileOutputStream(
                        new File(output, address.toString() + ".c")), StandardCharsets.UTF_8)) {
                    writer.write(code);
                }
                println("EXPORTED " + address + " chars=" + code.length());
            }
        } finally { decompiler.dispose(); }
        println("EXPORT_FUNCTIONS_DONE");
    }
}
