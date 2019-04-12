#!/usr/bin/python3

import os

from reporter import Reporter
from reporter import TempXMLElement

import tools

class StatTest:

    def __init__(self, var, quant, eps, dir, name):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.dir = dir
        self.name = name

    """
    method parses a stat-file and returns found variable
    """
    def readStatVariable(self, filename):
        vars = []
        nrCol = -1
        filename += ".stat"
        header = tools.readStatHeader(filename)
        readLines = header['number of lines']
        numScalars = len(header['parameters'])

        if self.var in header['columns']:
            varData = header['columns'][self.var]
            nrCol = varData['column']

        lines = tools.readfile(filename)

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
        passed_report = TempXMLElement("state")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")
        plot_report = TempXMLElement("plot")

        if not os.path.isfile(os.path.join(self.dir, self.name + ".stat")):
            rep.appendReport("ERROR: no statfile %s \n" % self.name)
            rep.appendReport("\t Test %s(%s) broken \n" % (self.var,self.quant))
            passed_report.appendTextNode("broken")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        readvar_sim = self.readStatVariable(os.path.join(self.dir, self.name))
        readvar_ref = self.readStatVariable(os.path.join(self.dir, "reference", self.name))

        plotfilename = tools.genplot(self.dir, self.name, self.var)

        if readvar_sim == [] or readvar_ref == []:
            rep.appendReport("Error: unknown variable (%s) selected for stat test\n" % self.var)
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("broken")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.eps)

            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        if len(readvar_sim) != len(readvar_ref):
            rep.appendReport("Error: size of stat variables (%s) dont agree!\n" % self.var)
            rep.appendReport("       size reference: %d, size simulation: %d\n" % (
                len(readvar_ref), len(readvar_sim)))
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (
                self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("broken")
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
            passed_report.appendTextNode("passed")
            passed = True
        else:
            rep.appendReport("Test %s(%s) failed: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            passed_report.appendTextNode("failed")

        delta_report.appendTextNode("%s" % val)
        eps_report.appendTextNode("%s" % self.eps)

        root.appendChild(passed_report)
        root.appendChild(eps_report)
        root.appendChild(delta_report)

        if plotfilename != "":
            plot_report.appendTextNode(plotfilename)
            root.appendChild(plot_report)

        return passed

