
from tools import readfile

class LbalTest:

    def __init__(self, var, quant, eps, simname):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.simname = simname


    def readLbalFile(self, filename):

        lbal = []
        lines = readfile(filename + ".lbal")
        #nrprocs = int(lines[0])
        lines = lines[1::]
        for line in lines:
            vals = str.split(line, "\t")
            lbal.append(vals)

    """
    method performs a test for "var" with reference file in a specific
    mode ("quant") for a specific accuracy ("eps")
    """
    def performTest(self, root):

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
