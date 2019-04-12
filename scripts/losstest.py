#import subprocess
#import glob
#import datetime
import os
#import time
#import sys
#import shutil
#import pathlib
#import threading
#import hashlib

from reporter import Reporter
from reporter import TempXMLElement

#from tools import genplot
#from tools import readfile

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
        if (not os.path.isfile(self.file_name) or
            not os.path.isfile("reference/" + self.file_name)):

            if not os.path.isfile(self.file_name):
                self.rep.appendReport("ERROR: no loss file %s \n" % self.file_name)
            if not os.path.isfile("reference/" + self.file_name):
                self.rep.appendReport("ERROR: no reference file %s \n" % ("reference" + self.file_name))

            self.rep.appendReport("\t Test %s(%s) broken \n" % (self.variable,self.mode))
            passed_report = TempXMLElement("state")
            eps_report = TempXMLElement("eps")
            delta_report = TempXMLElement("delta")
            plot_report = TempXMLElement("plot")

            passed_report.appendTextNode("broken")
            delta_report.appendTextNode("-")
            eps_report.appendTextNode("%s" % self.tolerance)

            root.addAttribute("type", "loss")
            root.addAttribute("var", self.variable)
            root.addAttribute("mode", self.mode)
            root.appendChild(passed_report)
            root.appendChild(eps_report)
            root.appendChild(delta_report)
            return False

        test_result = self.test(self) # note test() is a function pointer set at
                                      # initialisation
        self.report(root, *test_result)
        return (True if test_result[1] == 'passed' else False)

    def report(self, root, state, delta):
        """
        Add an entry to the XML document corresponding to the test result
            - root node in an XML document tree? Not sure
            - state indicating whether the test passed, failed or is broken
            - delta ?
        """
        root.addAttribute("type", "loss")
        root.addAttribute("var", self.variable)
        root.addAttribute("mode", self.mode)
        passed_report = TempXMLElement("state")
        eps_report = TempXMLElement("eps")
        delta_report = TempXMLElement("delta")
        plot_report = TempXMLElement("plot")

        passed_report.appendTextNode(state)
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
                state = ('success' if (test_pass and \
                                       test_data == 'end_of_file' and\
                                       ref_data == 'end_of_file') else 'failed')

                return (state, str(sum_squares**0.5/n))
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
