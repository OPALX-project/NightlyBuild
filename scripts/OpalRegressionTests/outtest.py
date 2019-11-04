import os

from OpalRegressionTests.reporter import Reporter
from OpalRegressionTests.reporter import TempXMLElement

class OutTest:

    def __init__(self, var, quant, eps, dir, simname):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.dir = dir
        self.simname = simname

    """
    method parses an out-file and returns found variables as tuples
    """
    def readOutVariable(self, fname):
        vars = []
        nrCol = 0
        numScalars = 0
        fname += ".out"
        with open(fname, "r") as infile:
            lines = [line.rstrip('\n') for line in infile]

        for line in lines:
            if self.var in line:
                # split line containing variable at all equal signs
                varline = str.split(line, "=")
                value = ""
                for i in range (len(varline)):
                    if self.var in varline[i]:
                        # ok our value is in element i+1
                        value = varline[i+1].lstrip().rstrip()
                        if self.valueIsVector(value):
                            vars.append(self.parseVector(value))
                        else:
                            # parsed_value = str.split(value, " ")[0]
                            # parsed_value = parsed_value.lstrip().rstrip()
                            vars.append((self.parseScalar(value),)) #(float(parsed_value),))

                        break;
        return vars

    def valueIsVector(self, str):
        return str.startswith("(")


    def parseVector(self, value_str):
        # remove vector brackets
        value_str = value_str.split("(")[1]
        rest = value_str
        value_str = value_str.split(")")[0]
        values = value_str.lstrip().rstrip()

        factor = self.getUnitConversion(rest)

        vector_values = values.split(",")
        x = float(vector_values[0].lstrip().rstrip()) * factor
        y = float(vector_values[1].lstrip().rstrip()) * factor
        z = float(vector_values[2].lstrip().rstrip()) * factor

        parsed_value = (x, y, z)
        return parsed_value

    def parseScalar(self, value_str):
        parsed_value_str = str.split(value_str, " ")[0]
        parsed_value = float(parsed_value_str.lstrip().rstrip())

        parsed_value *= self.getUnitConversion(value_str)

        return parsed_value

    def parseUnits(self, units_str):
        split_str = str.split(units_str, "]")
        if len(split_str) > 1:
            parsed_units = str.split(split_str[0], "[")[1]
            parsed_units = parsed_units.lstrip().rstrip()
            return parsed_units

        return ""

    def getUnitConversion(self, unit_str):
        unit_conversion = {'eV': 1e-3,
                           'keV': 1,
                           'MeV': 1e3,
                           'um': 1e-6,
                           'mm': 1e-3,
                           'm': 1,
                           'fs': 1e-6,
                           'ps': 1e-3,
                           'ns': 1,
                           'us': 1e3,
                           'ms': 1e6,
                           's': 1e9,
                           'pC': 1e-3,
                           'nC': 1,
                           'uC': 1e3,
                           'mC': 1e6,
                           'C': 1e9,
                           '%': 1,
                           'beta gamma': 1}

        parsed_units = self.parseUnits(unit_str)

        if parsed_units in unit_conversion:
            return unit_conversion[parsed_units]

        return 1

    """
    method performs a test for "var" with reference file in a specific mode ("quant") for a specific accuracy ("eps")
    """
    def checkResult(self, root):
        rep = Reporter()
        val = list()
        passed = True

        #report stuff
        root.addAttribute("type", "out")
        root.addAttribute("var", self.var)
        root.addAttribute("mode", self.quant)
        passed_report = TempXMLElement("state")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")

        if not os.path.isfile(self.simname + ".out"):
            rep.appendReport("ERROR: no outfile %s \n" % self.simname)
            rep.appendReport("\t Test %s(%s) broken\n" % (self.var,self.quant))
            passed_report.appendTextNode("broken")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        #get ref and sim variable values
        readvar_sim = self.readOutVariable(self.simname)
        readvar_ref = self.readOutVariable("reference/" + self.simname)

        if len(readvar_sim) == 0 or len(readvar_ref) == 0:
            rep.appendReport("Error: unknown variable (%s) selected for out test\n" % self.var)
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("broken")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        if len(readvar_sim) != len(readvar_ref):
            rep.appendReport("Error: size of out variables (%s) dont agree!\n" % self.var)
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("broken")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        if self.quant == "last":
            for i in range (len(readvar_sim[0])):
                val.append( abs(readvar_sim[len(readvar_sim) -1][i] - readvar_ref[len(readvar_sim) -1][i]) )

            for i in range (len(readvar_sim[0])):
                passed = passed and (val[i] < self.eps)

        elif self.quant == "avg":
            if len(readvar_sim) != len(readvar_ref):
                rep.appendReport("Error: size of stat variables dont agree!\n")
                return

            for j in range (len(readvar_sim[0])): #number of components
                sum = 0.0
                for i in range(len(readvar_sim)): #number of entries
                    sum += (readvar_sim[i][j] - readvar_ref[i][j])**2

                val.append((sum)**(0.5) / len(readvar_sim))

            for i in range (len(readvar_sim[0])):
                passed = passed and (val[i] < self.eps)

        elif self.quant == "error":
            rep.appendReport("TODO: error norm\n")

        elif self.quant == "all":
            rep.appendReport("TODO: graph/all\n")

        else:
            rep.appendReport("Error: unknown quantity %s \n" % self.quant)

        #result generation
        if passed:
            rep.appendReport("Test %s(%s) passed: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("passed")
        else:
            rep.appendReport("Test %s(%s) failed: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("failed")

        if len(val) == 1:
            delta_report.appendTextNode("%s" % val[0])
        else:
            delta_report.appendTextNode("%s" % val)
        eps_report.appendTextNode("%s" % self.eps)

        root.appendChild(passed_report)
        root.appendChild(eps_report)
        root.appendChild(delta_report)

        return passed
