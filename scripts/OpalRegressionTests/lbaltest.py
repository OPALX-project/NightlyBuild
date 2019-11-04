
class LbalTest:

    def __init__(self, var, quant, eps, dir, simname):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.dir = dir
        self.simname = simname


    def readLbalFile(self, fname):

        lbal = []
        with open(fname+".lbal", "r") as infile:
            lines = [line.rstrip('\n') for line in infile][1::]

        for line in lines:
            vals = str.split(line, "\t")
            lbal.append(vals)

    """
    method performs a test for "var" with reference file in a specific
    mode ("quant") for a specific accuracy ("eps")
    """
    def checkResult(self, root):

        readvar_sim = readLbalFile(simname)
        readvar_ref = readLbalFile("reference/" + simname)

        if len(readvar_sim) != len(readvar_ref):
            print ("Error: size does not agree!")

        if quant == "all":
            for i in range(len(readvar_sim)):
                #TODO: what delta?
                print ("calc some delta")

        else:
            return "Error: please only use all for lbal files!"

        return False
