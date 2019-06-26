#!/usr/bin/env python

import datetime
import sys
import subprocess
import os
import shutil
import re
import argparse
import hashlib

from reporter import Reporter
from reporter import TempXMLElement
from regressiontest import RegressionTest

from tools import readfile
from tools import sendmails
from tools import getRevisionTests
from tools import getRevisionOpal

#FIXME: ugly global variables
totalNrTests = 0
totalNrPassed = 0

opal_args = ""

"""
Scan given directory for regression tests. Regression tests are stored
in sub-directories whereby the name the directory has the same name as
the regression test.

Regression tests must follow the following directory-layouts:

    DIR Structure:
    name/name.in
         name.rt
         name.local
         name.sge
         reference/name.lbal
         reference/name.out
         reference/name.stat
         reference/name.lbal.md5
         reference/name.out.md5
         reference/name.stat.md5

Please make sure you use this naming scheme!
"""
def scan_for_tests (dir):
    os.chdir (dir)

    tests = set ()
    with os.scandir ('.') as it:
        for entry in it:
            if entry.name.startswith('.') or not entry.is_dir():
                continue
            # check if all files required are available
            test = entry.name
            basename = os.path.join (test, test)
            if not (os.path.isfile(basename + ".in") and
                    os.path.isfile(basename + ".rt") and
                    os.path.isdir(os.path.join (test, "reference"))):
                continue
            if os.path.isfile(os.path.join(test, "disabled")):
                continue
            tests.add (test)
            print("Found test %s" % (test))
    return tests


"""
Run a single regression test
"""

def run_regression_test (base_dir, simname, run_local = True, queue_name = ''):

    global totalNrPassed
    global totalNrTests

    rep = Reporter()
    d = datetime.date.today()
    resultdir = os.path.join (base_dir, "results", d.isoformat(), simname)
    if not os.path.isdir(resultdir):
        os.makedirs (resultdir)

    simulation_report = TempXMLElement("Simulation")
    simulation_report.addAttribute("name", simname)
    simulation_report.addAttribute("date", "%s" % d)

    rt = RegressionTest (base_dir, simname, opal_args, resultdir)
    rt.run (simulation_report, run_local, queue_name)
    totalNrTests += rt.totalNrTests
    totalNrPassed += rt.totalNrPassed
    rep.appendReport("\n\n")

def bailout():
    rep = Reporter()
    rep.appendReport("\n==========================================================\n")
    rep.appendReport("Finished Regression Test on %s \n" % datetime.datetime.today())

    #send/print report
    print (rep.getReport())

def addDate(rep):
    date_report = TempXMLElement("Date")
    startDate_report = TempXMLElement("start")
    d = datetime.datetime.today()
    now = "%02d-%02d-%02d %02d:%02d:%02d" % (d.year, d.month, d.day, d.hour, d.minute, d.second)
    startDate_report.appendTextNode (now)
    date_report.appendChild(startDate_report)
    rep.appendChild(date_report)

def addRevisionStrings(rep):
    revision_report = TempXMLElement("Revisions")

    revisionCode = getRevisionOpal()
    code_report = TempXMLElement("code")
    code_report.appendTextNode(revisionCode[0:7])
    revision_report.appendChild(code_report)

    full_code_report = TempXMLElement("code_full")
    full_code_report.appendTextNode(revisionCode)
    revision_report.appendChild(full_code_report)

    revisionTests = getRevisionTests()
    tests_report = TempXMLElement("tests")
    tests_report.appendTextNode(revisionTests[0:7])
    revision_report.appendChild(tests_report)

    full_tests_report = TempXMLElement("tests_full")
    full_tests_report.appendTextNode(revisionTests)
    revision_report.appendChild(full_tests_report)

    rep.appendChild(revision_report)

"""
publish results
"""
def publish_results (rundir, publish_dir):
    rep = Reporter ()

    d = datetime.date.today()
    webfilename = "results_" + d.isoformat() + ".xml"
    shutil.copy ("results.xml", os.path.join (publish_dir, webfilename))

    # copy plots to publish directory
    srcdir = os.path.join ("results", d.isoformat(), "plots")
    dstdir = os.path.join (publish_dir, "plots_" + d.isoformat())
    subprocess.getoutput("cp -rf " + srcdir + " " + dstdir)

    # copy 'index.html' if it does not exist in the publish directory
    index_fname = os.path.join (publish_dir, "index.html")
    if not os.path.exists(index_fname):
        shutil.copy (os.path.join (rundir, "index.html"), index_fname)

    # update 'index.html'
    indexhtml = open(index_fname).readlines()

    # search for the string 'insert here'
    for line in range(len(indexhtml)):
        if "insert here" in indexhtml[line]:
            m = re.search(webfilename, indexhtml[line + 1])
            fmt="<a href=\"%s\">%s.%s.%s</a> [passed:%d | broken:%d | failed:%d | total:%d] <br/>\n"
            text = fmt % (webfilename,
                          d.day, d.month, d.year,
                          totalNrPassed, rep.NrBroken(), rep.NrFailed(), totalNrTests)

            if m != None:
                # result for today already exist, replace it
                indexhtml[line+1] = text
            else:
                # first run
                indexhtml.insert(line+1, text)
            break
    # write new 'index.html' back
    indexhtmlout = open(index_fname, "w")
    indexhtmlout.writelines(indexhtml)
    indexhtmlout.close()

    # update various files to publish directory
    shutil.copy (os.path.join (rundir, "ok.png"), publish_dir);
    shutil.copy (os.path.join (rundir, "nok.png"), publish_dir);
    shutil.copy (os.path.join (rundir, "results.xslt"), publish_dir)
    shutil.copy (os.path.join (rundir, "accordion.js"), publish_dir)


def main(argv):
    rundir = sys.path[0]   # get absolute path name of this script

    global totalNrPassed
    global totalNrTests
    global opal_args
    totalNrTests = 0
    totalNrPassed = 0

    parser = argparse.ArgumentParser(description='Run regression tests.')
    parser.add_argument('tests',
                        metavar='tests', type=str, nargs='*', default = '',
                        help='a regression test to run')
    parser.add_argument('--base-dir',
                        dest='base_dir', type=str,
                        help='base directory with regression tests')
    parser.add_argument('--publish-dir',
                        dest='publish_dir', type=str,
                        help='publish directory')
    parser.add_argument('--opal-exe-path',
                        dest='opal_exe_path', type=str,
                        help='directory where OPAL binary is stored')
    parser.add_argument('--opal-args',
                        dest='opal_args', type=str,
                        help='arguments passed to OPAL')
    parser.add_argument('--dont-publish', dest='publish_results',
                        action='store_false', default='True',
                        help='do not publish results')

    args = parser.parse_args()
    runtests = args.tests

    # get directory where regression tests are installed
    if args.base_dir:
        base_dir = os.path.abspath(args.base_dir)
    else:
        base_dir = os.getcwd()
    if not os.path.isdir (base_dir):
        print ("%s - regression tests base directory does not exist!" %
               (base_dir))
        sys.exit(1)
    
    # get directory where to store results
    if args.publish_dir:
        publish_dir = args.publish_dir
    elif os.getenv("REGTEST_WWW"):
        publish_dir = os.getenv("REGTEST_WWW")
    else:
        publish_dir = base_dir

    if (args.publish_results and not os.path.exists(publish_dir)):
        os.mkdir(base_dir)

    # get directory with OPAL binary
    if args.opal_exe_path:
        os.environ['OPAL_EXE_PATH'] = args.opal_exe_path
    elif os.getenv("OPAL_EXE_PATH"):
        args.opal_exe_path = os.getenv("OPAL_EXE_PATH")
    if args.opal_exe_path:
        opal_exec = os.path.join(args.opal_exe_path, "opal")
        if not (os.path.isfile(opal_exec) and os.access(opal_exec, os.X_OK)):
            print ("%s - does not exist or is not executablet!" %
                   (opal_exec))
            sys.exit(1)
    else:
        opal_exec = shutil.which("opal")
        args.opal_exe_path = os.path.dirname(opal_exec)
        os.environ['OPAL_EXE_PATH'] = args.opal_exe_path

    # done with the arguments

    # clean old results
    d = datetime.date.today()
    srcdir = os.path.join (base_dir, "results", d.isoformat(), "plots")

    if os.path.isdir(srcdir):
        shutil.rmtree(srcdir)
    if publish_dir:
        dstdir = os.path.join (publish_dir, "plots_" + d.isoformat())
        if os.path.isdir(dstdir):
            shutil.rmtree(dstdir)

    ####
    # scan for valid tests in specified directory and
    # check whether the requested tests are valid tests

    regression_tests = scan_for_tests (base_dir)
    if runtests:
        for test in runtests:
            if not test in regression_tests:
                print ("%s - unknown test!" %
                       (test))
                sys.exit(1)

    else:
        runtests = regression_tests

    ####
    # start regression tests
    rep = Reporter()
    rep.appendReport("Start Regression Test on %s \n" % datetime.datetime.today())
    rep.appendReport("==========================================================\n")
    addDate(rep)

    os.chdir(base_dir)

    for test in sorted(regression_tests):
        if test in runtests:
            dir = os.path.join (base_dir, test)
            run_regression_test (base_dir, test)
        else:
            rep.appendReport("User decided to skip regression test %s \n" % test)

    addRevisionStrings(rep)
    rep.dumpXML("results.xml")

    if args.publish_results:
        publish_results (rundir, publish_dir)

    bailout()

if __name__ == "__main__":
    main(sys.argv[1:])
