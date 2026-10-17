// Validate native VM cases through real instruction decoding, not byte matches.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class InspectNativeCases extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) throw new IllegalArgumentException("outdir and index:name pairs required");
        File output = new File(args[0]); output.mkdirs();
        Address base = currentProgram.getMinAddress();
        try (Writer calls = new OutputStreamWriter(new FileOutputStream(new File(output, "calls.tsv")), StandardCharsets.UTF_8)) {
            calls.write("name\tindex\tcase\tcall_target\n");
            for (int arg = 1; arg < args.length; arg++) {
                String[] item = args[arg].split(":", 2);
                int index = Integer.parseInt(item[0]);
                String name = item[1];
                int rva = currentProgram.getMemory().getInt(base.add(0x200acccL + index * 4L));
                Address start = base.add(Integer.toUnsignedLong(rva));
                disassemble(start);
                try (Writer assembly = new OutputStreamWriter(new FileOutputStream(new File(output, name + ".asm")), StandardCharsets.UTF_8)) {
                    Address cursor = start;
                    for (int count = 0; count < 48 && cursor != null; count++) {
                        Instruction instruction = getInstructionAt(cursor);
                        if (instruction == null) break;
                        assembly.write(cursor + " " + instruction + "\n");
                        if (instruction.getFlowType().isCall()) {
                            for (Address target : instruction.getFlows()) {
                                calls.write(name + "\t" + index + "\t" + start + "\t" + target + "\n");
                                println("NATIVE_CALL " + name + " " + target);
                            }
                        }
                        cursor = instruction.getFallThrough();
                    }
                }
            }
        }
        println("INSPECT_NATIVE_CASES_DONE");
    }
}
