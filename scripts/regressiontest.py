import sys
if sys.version_info < (3,0):
    import commands as subprocess
else:
    import subprocess
import glob
import datetime
import os
import time
import sys

from reporter import Reporter
from reporter import TempXMLElement

from tools import genplot
from tools import readfile
from tools import readStatHeader

class RegressionTest:

    def __init__(self, dir, simname, resultdir):
        self.dirname = dir
        self.simname = simname
        self.resultdir = resultdir
        self.jobnr = -1
        self.totalNrTests = 0
        self.totalNrPassed = 0
        self.queue = ""

    def submitToSGE(self):
        #FIXME: we could create a sge file on the fly if no sge is specified for a give test ("default sge")
        qsub_command = "qsub " + self.queue + " " + self.simname + ".sge -v REG_TEST_DIR=" + self.dirname + ",OPAL_EXE_PATH=" + os.getenv("OPAL_EXE_PATH")
        submit_out = subprocess.getoutput(qsub_command)
        self.jobnr = str.split(submit_out, " ")[2]

    def waitUntilCompletion(self):
        username = subprocess.getoutput("whoami")
        qstatout = subprocess.getoutput("qstat -u " + username + " | grep \"" + self.jobnr + "\"")
        while len(qstatout) > 0:
            #we only check every 30 seconds if job has finished
            time.sleep(30)
            qstatout = subprocess.getoutput("qstat -u " + username + " | grep \"" + self.jobnr + "\"")

    def performTests(self, root):
        rep = Reporter()
        tests = readfile(self.simname + ".rt")
        root.addAttribute("description", tests[0].lstrip("\"").rstrip("\""))
        rep.appendChild(root)

        tests = tests[1::] #strip first line
        for i, test in enumerate(tests):
            try:
                self.totalNrTests += 1
                test_root = TempXMLElement("Test")
                passed = self.checkTest(test, test_root)
                if passed:
                    self.totalNrPassed += 1
                root.appendChild(test_root)
            except Exception:
                exc_info = sys.exc_info()
                sys.excepthook(*exc_info)
                rep.appendReport(
                    "Error: failed to parse "+self.simname+".rt file line "+\
                    str(i+2)+"\n    "+str(test)+"\nPython reports\n  "+\
                    str(exc_info[1])+"\n\n"
                )
                sys.exc_clear()


    def mpirun(self):
        if not os.access(self.simname+".local", os.X_OK):
            rep = Reporter()
            rep.appendReport("Error: "+self.simname+".local file could not be executed\n")
        run = "./" + self.simname + ".local | tee " + self.simname + "-RT.o"
        print(subprocess.getoutput(run))
        self.jobnr = 0


    """
    handler for comparison of various output files with reference files

    Note that we do something different for loss tests as the file name in
    general is not <simname>.loss, rather it is <element_name>.loss
    """
    def checkTest(self, test, root):
        nameparams = str.split(test,"\"")
        var = nameparams[1]
        params = str.split(nameparams[2].lstrip(), " ")
        rtest = 0
        if "stat" in test:
            rtest = StatTest(var, params[0], float(params[1]), self.simname)
        elif "out" in test:
            rtest = OutTest(var, params[0], float(params[1]), self.simname)
        elif "lbal" in test:
            rtest = LbalTest(var, params[0], float(params[1]), self.simname)
        elif test.split()[0][-4:] == "loss":
            rtest = LossTest(var, params[0], float(params[1]), test.split()[0])
        else:
            rep = Reporter()
            rep.appendReport("Error: unknown test type %s\n" % nameparams[0])
            return False

        return rtest.performTest(root)

    def run(self, root, run_local, q):

        curd = os.getcwd()
        os.chdir(self.dirname)

        isValid = self.validateReferenceFiles()

        self.queue = q

        if isValid:
            rep = Reporter()
            rep.appendReport("\t run simulation\n")
            os.environ["REG_TEST_DIR"] = self.dirname

            # ADA cleanup all OLD job files if there are any
            subprocess.getoutput("rm -rf " + self.simname + "-RT.* " + self.simname + "*.png")
            if not run_local:
                self.submitToSGE()
                self.waitUntilCompletion()
            else:
                self.mpirun()

            # copy o to out file
            subprocess.getoutput("cp -rf " + self.simname + "-RT.o* " + self.simname + ".out")

            self.performTests(root)

            # move plots to plot dir
            d = datetime.date.today()
            plotdir = "results/" + d.isoformat() + "/plots"

            subprocess.getoutput("mkdir " + curd + "/" + plotdir)
            subprocess.getoutput("cp -rf *.png " + curd + "/" + plotdir)

            #move tests to result folder
            subprocess.getoutput("cp -rf " + self.simname + ".stat " + curd + "/" + self.resultdir)
            subprocess.getoutput("cp -rf " + self.simname + ".lbal " + curd + "/" + self.resultdir)
            subprocess.getoutput("cp -rf " + self.simname + ".out " + curd + "/" + self.resultdir)
        os.chdir(curd)

    """
    This method checks if all files in the reference directory are present
    and if their md5 checksums still concure with the ones stored after
    the simulation run
    """
    def validateReferenceFiles(self):
        rep = Reporter()
        olddir = os.getcwd()
        os.chdir("reference")
        allok = False

        if os.path.isfile(self.simname + ".stat") and \
           os.path.isfile(self.simname + ".stat.md5") and \
           os.path.isfile(self.simname + ".out") and \
           os.path.isfile(self.simname + ".out.md5") and \
           os.path.isfile(self.simname + ".lbal") and \
           os.path.isfile(self.simname + ".lbal.md5"):

            statout = subprocess.getoutput("md5sum --check " + self.simname + ".stat.md5")
            outout = subprocess.getoutput("md5sum --check " + self.simname + ".out.md5")
            lbalout = subprocess.getoutput("md5sum --check " + self.simname + ".lbal.md5")

            rep.appendReport("\t Checksum for reference %s \n" % statout)
            rep.appendReport("\t Checksum for reference %s \n" % outout)
            rep.appendReport("\t Checksum for reference %s \n" % lbalout)
            allok = statout == self.simname + ".stat: OK" and outout == self.simname + ".out: OK" and lbalout == self.simname + ".lbal: OK"

        else:
            rep_string = "\t Error: reference dir for "+self.simname+" is incomplete!\n"
            for file_suffix in [".stat", ".stat.md5",
                                ".out", ".out.md5",
                                ".lbal", ".lbal.md5"]:
                file_name = self.simname+file_suffix
                rep_string += "\t\t "+file_name+" "+str(os.path.isfile(file_name))+"\n"
            rep.appendReport(rep_string)
        for loss_file in glob.glob("*.loss"):
            lossout = subprocess.getoutput("md5sum --check " + loss_file+".md5")
            rep.appendReport("\t Checksum for reference %s \n" % lossout)
            allok = allok and lossout == loss_file+": OK"
        os.chdir(olddir)
        return allok


class StatTest:

    def __init__(self, var, quant, eps, simname):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.simname = simname

    """
    method parses a stat-file and returns found variable
    """
    def readStatVariable(self, filename):
        vars = []
        nrCol = -1

        header = readStatHeader(filename + ".stat")
        readLines = header['number of lines']
        numScalars = len(header['parameters'])

        if header['columns'].has_key(self.var):
            varData = header['columns'][self.var]
            nrCol = varData['column']

        lines = readfile(filename + ".stat")

        if nrCol > -1:
            for line in lines[(readLines + numScalars):]:
                values = line.split()
                vars.append(float(values[nrCol]))

        return vars

    """
    method performs a test for a stat-file variable "var"
    """
    def performTest(self, root):

        rep = Reporter()
        val = 0

        root.addAttribute("type", "stat")
        root.addAttribute("var", self.var)
        root.addAttribute("mode", self.quant)
        passed_report = TempXMLElement("passed")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")
        plot_report = TempXMLElement("plot")

        if not os.path.isfile(self.simname + ".stat"):
            rep.appendReport("ERROR: no statfile %s \n" % self.simname)
            rep.appendReport("\t Test %s(%s) broken \n" % (self.var,self.quant))
            passed_report.appendTextNode("false")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        readvar_sim = self.readStatVariable(self.simname)
        readvar_ref = self.readStatVariable("reference/" + self.simname)

        plotfilename = genplot(self.simname, self.var)

        if readvar_sim == [] or readvar_ref == []:
            rep.appendReport("Error: unknown variable (%s) selected for stat test\n" % self.var)
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("false")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        if len(readvar_sim) != len(readvar_ref):
            rep.appendReport("Error: size of stat variables (%s) dont agree!\n" % self.var)
            rep.appendReport("       size reference: %d, size simulation: %d\n" % (len(readvar_ref), len(readvar_sim)))
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("false")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        if self.quant == "last":
            val = abs(readvar_sim[len(readvar_sim) -1] - readvar_ref[len(readvar_sim) -1])

        elif self.quant == "avg":
            sum = 0.0
            for i in range(len(readvar_sim)):
                sum += (readvar_sim[i] - readvar_ref[i])**2
            val = (sum)**(0.5) / len(readvar_sim)

        elif self.quant == "error":
            rep.appendReport("TODO: error norm\n")

        elif self.quant == "all":
            rep.appendReport("TODO: graph/all\n")

        else:
            rep.appendReport("Error: unknown quantity %s \n" % self.quant)

        #result generation
        passed = False
        if val < self.eps:
            rep.appendReport("Test %s(%s) passed: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("true")
            passed = True
        else:
            rep.appendReport("Test %s(%s) failed: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("false")

        delta_report.appendTextNode("%s" % val)
        eps_report.appendTextNode("%s" % self.eps)

        root.appendChild(passed_report)
        root.appendChild(eps_report)
        root.appendChild(delta_report)

        if plotfilename != "":
            plot_report.appendTextNode(plotfilename)
            root.appendChild(plot_report)

        return passed


class OutTest:

    def __init__(self, var, quant, eps, simname):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.simname = simname

    """
    method parses an out-file and returns found variables as tuples
    """
    def readOutVariable(self, filename):
        vars = []
        nrCol = 0
        numScalars = 0
        lines = readfile(filename + ".out")

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

        if unit_conversion.has_key(parsed_units):
            return unit_conversion[parsed_units]

        return 1

    """
    method performs a test for "var" with reference file in a specific mode ("quant") for a specific accuracy ("eps")
    """
    def performTest(self, root):
        rep = Reporter()
        val = list()
        passed = True

        #report stuff
        root.addAttribute("type", "out")
        root.addAttribute("var", self.var)
        root.addAttribute("mode", self.quant)
        passed_report = TempXMLElement("passed")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")

        if not os.path.isfile(self.simname + ".out"):
            rep.appendReport("ERROR: no outfile %s \n" % self.simname)
            rep.appendReport("\t Test %s(%s) broken\n" % (self.var,self.quant))
            passed_report.appendTextNode("false")
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
            passed_report.appendTextNode("false")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        if len(readvar_sim) != len(readvar_ref):
            rep.appendReport("Error: size of out variables (%s) dont agree!\n" % self.var)
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("false")
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
            passed_report.appendTextNode("true")
        else:
            rep.appendReport("Test %s(%s) failed: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("false")

        if len(val) == 1:
            delta_report.appendTextNode("%s" % val[0])
        else:
            delta_report.appendTextNode("%s" % val)
        eps_report.appendTextNode("%s" % self.eps)

        root.appendChild(passed_report)
        root.appendChild(eps_report)
        root.appendChild(delta_report)

        return passed


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
    method performs a test for "var" with reference file in a specific mode ("quant") for a specific accuracy ("eps")
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

class LossTest:
    """
    A regression test based on .loss type files, specifically for PROBE elements
    Member data:
        - variable: the variable to be checked. Options are "x",  "y",  "z",
                    "px",  "py",  "pz", "track_id", "turn",  "time"
        - quantity: string that defines how the variable should be handled.
          Options are "all" (other options not implemented)
          + "all" test fails if any particles in any plane in the loss
            file have variable - variable_(ref) > tolerance
        - tolerance: floating point tolerance (absolute)
        - file_name: name of the loss file to be checked
    Note that
        - Output in the loss file is assumed to be that of a PROBE element.
        - If a line of output is not compatible with PROBE output, test
          will ignore the line (not fail).
        - Test will always fail if no valid data was found in the loss file
          or the loss file could not be opened.
        - Particles are grouped into plane according to a unique combination
          of <Turn id> and <Element id>
    """

    def __init__(self, variable, quantity, tolerance, loss_file_name):
        """
        Initialise the test
        """
        self.rep = Reporter()
        self.variable = variable
        if self.variable in self.variable_list.keys():
            self.variable_int = self.variable_list[self.variable]
        else:
            raise KeyError(str(self.variable)+\
                  " is not a valid variable type for loss file tests."+\
                  " Try one of "+str(self.variable_list.keys()))
        self.mode = quantity
        self.test = None
        if self.mode in self.mode_list.keys():
            self.test = self.mode_list[self.mode]
        else:
            raise KeyError("Did not recognise LossTest mode "+str(self.mode)+\
                           " Try one of "+str(self.mode_list.keys()))
        self.tolerance = tolerance
        self.file_name = loss_file_name

    def performTest(self, root):
        """
        Run the test and add output to the report
        """
        test_result = self.test(self) # note test() is a function pointer set at
                                      # initialisation
        self.report(root, *test_result)

    def report(self, root, has_passed, delta):
        """
        Add an entry to the XML document corresponding to the test result
            - root node in an XML document tree? Not sure
            - has_passed bool indicating whether the test passed or failed
            - delta ?
        """
        root.addAttribute("type", "loss")
        root.addAttribute("var", self.variable)
        root.addAttribute("mode", self.mode)
        passed_report = TempXMLElement("passed")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")
        plot_report = TempXMLElement("plot")

        passed_report.appendTextNode(str(has_passed).lower())
        delta_report.appendTextNode(str(delta))
        eps_report.appendTextNode(str(self.tolerance))

        root.appendChild(passed_report)
        root.appendChild(delta_report)


    def testAll(self):
        """
        Read line-by-line through the loss file and check reference data against
        test data

        Return is a tuple like if data is out of tolerance
        """
        test = open(self.file_name)
        ref = open("reference/"+self.file_name)
        n = 1.
        sum_squares = 0.
        test_pass = True
        while True:
            test_data, ref_data = 'parse_error', 'parse_error'
            while test_data == 'parse_error':
                test_data = self.readOneLine(test.readline())[2]
            while ref_data == 'parse_error':
                ref_data = self.readOneLine(ref.readline())[2]
            # if any file ends, both files must end (or we fail)
            if test_data == 'end_of_file' or ref_data == 'end_of_file':
                return (test_pass and \
                        test_data == 'end_of_file' and\
                        ref_data == 'end_of_file', str(sum_squares**0.5/n))
            else:
                test_value = abs(test_data - ref_data)
                sum_squares += test_value**2
                n += 1.
                test_pass = test_pass and test_value < self.tolerance


    def testLast(self):
        raise NotImplementedError("LossTest.testLast not implemented yet")

    def testError(self):
        raise NotImplementedError("LossTest.testError not implemented yet")

    def testMean(self):
        raise NotImplementedError("LossTest.testMean not implemented yet")

    def readOneLine(self, line):
        """
        Parse one line of the loss file.

        Assume data format like element_id x y z px py pz track_id turn time

        Returns a tuple like (element, turn, variable), 'end_of_file' if the
        file ended or 'parse_error' if the line could not be parsed.
        """
        if line == '':
            return (0, 0, 'end_of_file')
        try:
            words = line.rstrip('\n').split(' ')
            words = [x for x in words if x != '']
            dynamic_variable = words[self.variable_int]
            output = (words[0], int(words[8]), float(dynamic_variable))
            return output
        except Exception:
            return (0, 0, 'parse_error')

    variable_list = {"x":1, "y":2, "z":3, "px":4, "py":5, "pz":6,
                     "track_id":7, "turn":8, "time":9}
    mode_list = {"last":testLast, "all":testAll, "error":testError,
                     "avg":testMean}