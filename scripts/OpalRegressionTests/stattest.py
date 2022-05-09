#!/usr/bin/python3

import os
import re
import subprocess

from OpalRegressionTests.reporter import Reporter
from OpalRegressionTests.reporter import TempXMLElement

class StatTest:
    """
    A regression test based on ASCII SDDS format for beam statistics
    type files. There are two file extensions supported: ".stat" files
    of global statistical beam parameters and ".smb" files of single
    bunch statistics in multibunch simulations.
    Member data:
        - var: the variable to be checked.
        - quant: string that defines how the variable should be handled.
          Options are "last" and "avg"
        - eps: floating point tolerance (absolute)
        - name: name of the smb file to be checked
    """

    def __init__(self, var, quant, eps, prefix, name, suffix = ".stat"):
        self.var = var
        self.quant = quant
        self.eps = eps
        self.prefix = prefix
        self.name = name
        self.fname = os.path.join(self.prefix, self.name) + suffix
        self.reference_fname = os.path.join(self.prefix, "reference", self.name) + suffix
        
    def _report_broken_test(self, root):
        passed_report = TempXMLElement("state")
        passed_report.appendTextNode("broken")
        root.appendChild(passed_report)

        eps_report = TempXMLElement("eps")
        eps_report.appendTextNode("%s" % self.eps)
        root.appendChild(eps_report)

        delta_report = TempXMLElement("delta")
        delta_report.appendTextNode("-")
        root.appendChild(delta_report)
        return False
        
    def checkResult(self, root):
        """
        method performs a test for a stat-file variable "var"
        """
        rep = Reporter()
        val = 0

        root.addAttribute("type", "stat")
        root.addAttribute("var", self.var)
        root.addAttribute("mode", self.quant)
        
        if not os.path.isfile(self.fname):
            rep.appendReport("ERROR: no statfile %s \n" % self.name)
            rep.appendReport("\t Test %s(%s) broken \n" % (self.var,self.quant))
            return self._report_broken_test(root)
            
        self.opalRevision, self.path_length, self.values = self._readStatVariable(self.fname)
        self.refRevision, self.ref_path_length, self.ref_values = self._readStatVariable(self.reference_fname)

        if self.values == [] or self.ref_values == []:
            rep.appendReport("Error: unknown variable (%s) selected for stat test\n" % self.var)
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (self.var,self.quant,val,self.eps))
            return self._report_broken_test(root)

        if len(self.values) != len(self.ref_values):
            rep.appendReport("Error: size of stat variables (%s) dont agree!\n" % self.var)
            rep.appendReport("       size reference: %d, size simulation: %d\n" % (
                len(self.ref_values), len(self.values)))
            rep.appendReport("\t Test %s(%s) broken: %s (eps=%s) \n" % (
                self.var,self.quant,val,self.eps))
            return self._report_broken_test(root)


        if self.quant == "last":
            val = abs(self.values[-1] - self.ref_values[-1])

        elif self.quant == "avg":
            sum = 0.0
            for i in range(len(self.values)):
                sum += (self.values[i] - self.ref_values[i])**2
            val = (sum)**(0.5) / len(self.values)

        elif self.quant == "error":
            rep.appendReport("TODO: error norm\n")

        elif self.quant == "all":
            rep.appendReport("TODO: graph/all\n")

        else:
            rep.appendReport("Error: unknown quantity %s \n" % self.quant)

        #result generation
        passed_report = TempXMLElement("state")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")
        plot_report = TempXMLElement("plot")

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

        plotfilename = self._plot()
        if plotfilename != "":
            fname = os.path.basename(plotfilename)
            plot_report.appendTextNode("{0}/" + fname)
            root.appendChild(plot_report)

        return passed

    def _readStatHeader(self, statfile):
        """
        parse header of .stat file (ASCII SDDS format)
        """
        header = {'number of lines': 0,
                  'columns': {},
                  'parameters': {}
        }
        numColumns = 0
        numScalars = 0
        readLines = 0
        with open(statfile, "r") as infile:
            lines = [line.rstrip('\n') for line in infile]

        i = 0
        end_of_header_reached = False
        while not end_of_header_reached:
            line = lines[i]

            if "&column" in line:
                column = ""
                while True:
                    column += line
                    if "&end" in line:
                        break
                    i += 1
                    line = lines[i]

                name = str.split(column, "name=")[1]
                name = str.split(name, ",")[0]
                unit = str.split(column, "units=")[1]
                unit = str.split(unit, ",")[0]

                header['columns'][name] = {'units': unit, 'column': len(header['columns'])}
                numColumns += 1

            elif "&parameter" in line:
                parameter = ""
                while True:
                    parameter += line
                    if "&end" in line:
                        break
                    i += 1
                    line = lines[i]

                name = str.split(parameter, "name=")[1]
                name = str.split(name, ",")[0]

                header['parameters'][name] = {'row': len(header['parameters'])}

            elif "&data" in line:
                while not "&end" in line:
                    i += 1
                    line = lines[i]
                end_of_header_reached = True

            i += 1

        header['number of lines'] = i

        return header

    def _readStatVariable(self, fname):
        """
        method parses a stat-file and returns found variables
        """
        header = self._readStatHeader(fname)
        readLines = header['number of lines']
        revLine = header['parameters']['revision']['row']
        numScalars = len(header['parameters'])
        sCol = header['columns']['s']['column']
        
        varCol = -1
        if self.var in header['columns']:
            varData = header['columns'][self.var]
            varCol = varData['column']
        else:
            return []
        with open(fname,"r") as infile:
            lines = [line.rstrip('\n') for line in infile]
    
        m = re.search('(.* git rev\. )#([A-Za-z0-9]{7})[A-Za-z0-9]*', lines[readLines + revLine]);
        if m:
            revision = m.group(1) + m.group(2)
        else:
            revision = lines[readLines + revLine]

        path_length = [float(line.split()[sCol]) for line in lines[(readLines + numScalars):]]
        values = [float(line.split()[varCol]) for line in lines[(readLines + numScalars):]]
        return revision, path_length, values

    def _read_stat_file(self, stat_file, plot_file):
        header = self._readStatHeader(stat_file)
        readLines = header['number of lines']
        revLine = header['parameters']['revision']['row']
        numScalars = len(header['parameters'])
        sCol = header['columns']['s']['column']

        varCol = -1
        if self.var in header['columns']:
            varData = header['columns'][self.var]
            varCol = varData['column']
            self.var_unit = varData['units']

        if varCol == -1:
            print ("Error in genplot: Cannot find stat variable!")
            return False

        stat_data = [line.rstrip('\n') for line in open(stat_file)]

        m = re.search('(.* git rev\. )#([A-Za-z0-9]{7})[A-Za-z0-9]*', stat_data[readLines + revLine]);
        if m:
            revision = m.group(1) + m.group(2)
        else:
            revision = stat_data[readLines + revLine]

        with open(plot_file,'w') as f:
            for line in stat_data[(readLines + numScalars):]:
                values = line.split()
                f.write(values[sCol] + "\t" + values[varCol] + "\n")

        return revision

    def _plot(self):
        stat_plot_file = os.path.join(self.prefix, 'data1.dat')
        opalRevision = self._read_stat_file(self.fname, stat_plot_file)
        if not opalRevision:
            return False
        reference_plot_file = os.path.join(self.prefix, 'data2.dat')
        refRevision = self._read_stat_file(self.reference_fname, reference_plot_file)
        if not refRevision:
            return False

        varParts = str.split(self.var, "_")
        prettyVar = varParts[0]
        if len(varParts) == 2:
            prettyVar = varParts[0] + "(" + varParts[1] + ")"

        output_fname = os.path.join(self.prefix, self.name + "_" + self.var + ".png")
        plotcmd = "set terminal pngcairo\n"
        plotcmd += "set output '" + output_fname + "'\n"
        plotcmd += "set title '" + self.name + "'\n"
        plotcmd += "set key below\n"
        plotcmd += "set ytics nomirror\n"
        plotcmd += "set y2tics\n"
        plotcmd += "set ylabel '" + prettyVar + " [" + self.var_unit + "]' font 'Helvetica-Bold,20'\n"
        plotcmd += "set y2label 'delta " + prettyVar + " [" + self.var_unit + "]' font 'Helvetica-Bold,20'\n"
        plotcmd += "set xlabel 's [m]' font 'Helvetica-Bold,20'\n"
        plotcmd += "plot '" +  stat_plot_file + "' u 1:2 w l lw 2 t '" + opalRevision + "', "
        plotcmd += "'" + reference_plot_file + "' u 1:2 w l lw 2 t '" + refRevision + "', "
        plotcmd += "\"< paste " + stat_plot_file + " " + reference_plot_file + "\" u 1:($2-$4) w l lw 2 axis x1y2 t 'difference'" + ";\n"
        plot = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
        plot.communicate(bytes(plotcmd, "UTF-8"))
        os.remove(stat_plot_file)
        os.remove(reference_plot_file)
            
        return output_fname
