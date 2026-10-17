// Explore native Galaxy bindings in the existing decrypted program, read-only.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class NativeBindings extends GhidraScript {
    private final String[] names = {
        "PlayerGetPropertyInt", "PlayerGetPropertyFixed", "UnitGetPropertyInt",
        "UnitGetPropertyFixed", "UnitGetOwner", "UnitIsAlive", "UnitGetType",
        "GameGetMissionTime", "PlayerGroupAll", "UnitGroupCount",
        "TimerGetElapsed", "UnitRevive", "UnitGetPosition"
    };
    private String quote(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("output directory required");
        File output = new File(args[0]); output.mkdirs();
        Set<String> exported = new HashSet<>();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        StringBuilder json = new StringBuilder("[\n");
        boolean first = true;
        try {
            for (String name : names) {
                Address string = currentProgram.getMemory().findBytes(
                    currentProgram.getMinAddress(), (name + "\0").getBytes("US-ASCII"), null, true, monitor);
                if (!first) json.append(",\n"); first = false;
                json.append("{\"name\":").append(quote(name));
                if (string == null) { json.append(",\"absent\":true}"); continue; }
                json.append(",\"string\":").append(quote(string.toString())).append(",\"refs\":[");
                boolean firstRef = true;
                Set<Function> functions = new LinkedHashSet<>();
                for (Reference reference : getReferencesTo(string)) {
                    Address source = reference.getFromAddress();
                    if (!firstRef) json.append(','); firstRef = false;
                    json.append(quote(source.toString()));
                    Function function = getFunctionContaining(source);
                    if (function != null) functions.add(function);
                    else {
                        for (int delta = -48; delta <= 48; delta += 8) {
                            try {
                                long pointer = currentProgram.getMemory().getLong(source.add(delta));
                                Address target = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(pointer);
                                Function found = getFunctionAt(target);
                                if (found != null) functions.add(found);
                            } catch (Exception ignored) { }
                        }
                    }
                }
                json.append("],\"functions\":[");
                boolean firstFunction = true;
                for (Function function : functions) {
                    String entry = function.getEntryPoint().toString();
                    if (!firstFunction) json.append(','); firstFunction = false;
                    json.append(quote(entry));
                    if (exported.size() >= 32 || !exported.add(entry)) continue;
                    DecompileResults result = decompiler.decompileFunction(function, 40, monitor);
                    if (result.decompileCompleted()) {
                        String code = result.getDecompiledFunction().getC();
                        try (Writer writer = new OutputStreamWriter(new FileOutputStream(
                                new File(output, entry + ".c")), StandardCharsets.UTF_8)) {
                            writer.write(code);
                        }
                        println("EXPORTED " + name + " " + entry + " chars=" + code.length());
                    } else println("FAILED " + entry + " " + result.getErrorMessage());
                }
                json.append("]}");
                println("ANCHOR " + name + " " + string + " functions=" + functions.size());
            }
        } finally { decompiler.dispose(); }
        json.append("\n]\n");
        try (Writer writer = new OutputStreamWriter(new FileOutputStream(new File(output, "index.json")), StandardCharsets.UTF_8)) {
            writer.write(json.toString());
        }
        println("NATIVE_BINDINGS_DONE unique_functions=" + exported.size());
    }
}
