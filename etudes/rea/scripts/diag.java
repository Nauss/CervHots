// diag.java — contrôle de santé de la base Ghidra : fonctions et références.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.Reference;

public class diag extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("programme      : " + currentProgram.getName());
        println("fonctions      : " + currentProgram.getFunctionManager().getFunctionCount());
        println("defined data   : " + currentProgram.getListing().getNumDefinedData());
        println("instructions   : " + currentProgram.getListing().getNumInstructions());

        Address entry = currentProgram.getImageBase();
        Function f = getFunctionContaining(entry);
        println("fonction @base : " + f);

        // une fonction quelconque et ses appels entrants
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        Function any = it.next();
        if (any != null) {
            int nIns = 0;
            ghidra.program.model.symbol.ReferenceIterator ins =
                    currentProgram.getReferenceManager().getReferencesTo(any.getEntryPoint());
            while (ins.hasNext()) {
                ins.next();
                nIns++;
            }
            println("func test      : " + any.getEntryPoint() + " refs entrantes=" + nIns);

            Reference[] outs = currentProgram.getReferenceManager().getReferencesFrom(any.getEntryPoint());
            println("refs sortantes : " + outs.length);
        }
    }
}
