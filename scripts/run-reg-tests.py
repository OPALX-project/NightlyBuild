#!/usr/bin/python
import datetime
import sys
if sys.version_info < (3,0):
    import commands as subprocess
else:
    import subprocess
import os
import shutil
import re
import argparse

from reporter import Reporter
from reporter import TempXMLElement

from regressiontest import RegressionTest

from tools import readfile
from tools import module_load
from tools import sendmails
from tools import getRevisionTests
from tools import getRevisionOpal

#FIXME: ugly global variables
totalNrTests = 0
totalNrPassed = 0

opal_args = ""

"""
This method traverses the directory tree. It will check and execute regression tests for the following directory-layouts:

    DIR Structure:
    name/name.in
         name.rt
         run
         run-parallel
         *.T7
         reference/name.lbal
         reference/name.out
         reference/name.stat
         reference/name.lbal.md5
         reference/name.out.md5
         reference/name.stat.md5

Please make sure you use this naming scheme!
"""
def callback(arg, dirname, fnames):

    global totalNrPassed
    global totalNrTests

    if "reference" in dirname:
        return   #exclude svn and reference dirs

    dir = str.split(dirname, "/")
    simname = dir[len(dir)-1]

    # check if all files required are available
    if not (os.path.isfile(dirname + "/" + simname + ".in") and \
       os.path.isfile(dirname + "/" + simname + ".rt") and \
       os.path.isfile(dirname + "/" + simname + ".sge") and \
       os.path.isdir(dirname + "/" + "reference")):
        return

    rep = Reporter()
    rep.appendReport("Found valid test in %s \n" % dirname)

    # check if we really want to run this test
    # empty list = run all
    runtests = arg[0]
    if runtests:
        if not simname in runtests:
            rep.appendReport("User decided to skip regression test %s \n" % simname)
            rep.appendReport("\n\n")
            return

    d = datetime.date.today()
    resultdir = "results/" + d.isoformat() + "/" + simname
    if not os.path.isdir(resultdir):
        os.makedirs (resultdir)

    simulation_report = TempXMLElement("Simulation")
    simulation_report.addAttribute("name", simname)
    simulation_report.addAttribute("date", "%s" % d)

    rt = RegressionTest(dirname, simname, opal_args, resultdir)
    rt.run(simulation_report, arg[1], arg[2])
    totalNrTests += rt.totalNrTests
    totalNrPassed += rt.totalNrPassed
    rep.appendReport("\n\n")

    if runtests:
        if simname in runtests:
            runtests.remove(simname)
            runtests.append("DONE")

def bailout():
    rep = Reporter()
    d = datetime.date.today()
    rep.appendReport("==========================================================\n")
    rep.appendReport("Finished Regression Test on %s \n" % datetime.datetime.today())

    #send/print report
    print (rep.getReport())

def addDate(rep):
    date_report = TempXMLElement("Date")
    startDate_report = TempXMLElement("start")
    d = datetime.datetime.today()
    startDate_report.appendTextNode("%02d-%02d-%02d %02d:%02d:%02d" % (d.year, d.month, d.day, d.hour, d.minute, d.second))
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

def main(argv):
    rep = Reporter()
    d = datetime.date.today()
    rep.appendReport("Results: http://amas.web.psi.ch/regressiontests/results_%s_%s_%s.xml \n\n" % (d.day, d.month, d.year))

    # tests are one level up starting from directory of this script
    rundir = sys.path[0]   # get absolute path name of this script
    regdir = os.path.dirname (rundir)

    global totalNrPassed
    global totalNrTests
    global opal_args
    totalNrTests = 0
    totalNrPassed = 0
    runtests = list()
    run_with_tests = True
    run_local = True

    parser = argparse.ArgumentParser(description='Run regression tests.')
    parser.add_argument('tests', metavar='tests', type=str, nargs='+',
                    help='a regression test to run')
    parser.add_argument('--dont-publish', dest='publish_results', action='store_false',
			default='True', help='do not publish results to web')
    parser.add_argument('--regtests-dir', dest='regdir', type=str,
			help='base directory with regression tests')
    parser.add_argument('--regtests-www', dest='regtest_www', type=str,
			help='publish directory')
    parser.add_argument('--opal-exe-path', dest='opal_exe_path', type=str,
			help='directory where OPAL binary is stored')
    parser.add_argument('--use-dks', dest='use_dks', action='store_true',
			default='False', help='use dynamic kernel scheduler')

    args = parser.parse_args()
    print args

    runtests = args.tests

    # get directory where regression tests are installed
    if args.regdir:
        regdir = args.regdir

    # get directorx where to store results
    if args.regtest_www:
        www_folder = args.regtest_www
    else:
        www_folder = os.getenv("REGTEST_WWW")

    if args.publish_results == True and www_folder is None:
        rep.appendReport("Error: REGTEST_WWW not set")
        bailout()
        return

    # get directory whith OPAL binary
    if args.opal_exe_path:
        os.environ['OPAL_EXE_PATH'] = args.opal_exe_path
    if not os.getenv("OPAL_EXE_PATH"):
        rep.appendReport("Error: OPAL_EXE_PATH not set")
        bailout()
        return

    if not os.path.isfile(os.getenv("OPAL_EXE_PATH") + "/opal"):
        rep.appendReport("Error: OPAL_EXE_PATH is invalid")
        bailout()
        return

    if args.use_dks == True:
        opal_args = " --use-dks"

    # done with the arguments

    rep.appendReport("\n")
    rep.appendReport("Start Regression Test on %s \n" % datetime.datetime.today())
    rep.appendReport("==========================================================\n")

    addDate(rep)

    os.chdir(regdir)
    #walk the run dir tree
    arglist = [runtests, True, '']
    for root, dirs, files in os.walk("./"):
        callback(arglist, root, files)

    if run_with_tests and len(runtests) > 0:
        unknownExist = False
        for test in runtests:
            if test != "DONE":
                rep.appendReport(">>> NO TEST CALLED '" + test + "'\n")
                unknownExist = True
        if unknownExist:
            rep.appendReport("\n\n")

    addRevisionStrings(rep)

    rep.dumpXML("results.xml")

    #cp report to webdir and add entry in index.html
    if args.publish_results:
        failedtests = rep.NrFailed()
        brokentests = rep.NrBroken()
        webfilename = "results_" + d.isoformat() + ".xml"
        shutil.copy ("results.xml", os.path.join (www_folder, webfilename))
        srcdir = os.path.join ("results", d.isoformat(), "plots")
        dstdir = os.path.join (www_folder, "plots_" + d.isoformat())
        subprocess.getoutput("cp -rf " + srcdir + " " + dstdir)
	index_fname = os.path.join (www_folder, "index.html")
	if not os.path.exists(index_fname):
	    shutil.copy (os.path.join (rundir, "index.html"), index_fname)
	ok_sign_fname = os.path.join (www_folder, "ok.png")
        if not os.path.exists(ok_sign_fname):
            shutil.copy (os.path.join (rundir, "ok.png"), ok_sign_fname);
        nok_sign_fname = os.path.join (www_folder, "nok.png")
        if not os.path.exists(nok_sign_fname):
            shutil.copy (os.path.join (rundir, "nok.png"), nok_sign_fname);

        indexhtml = open(index_fname).readlines()
        for line in range(len(indexhtml)):
            if "insert here" in indexhtml[line]:
                m = re.search(webfilename, indexhtml[line + 1])
		fmt="<a href=\"%s\">%s.%s.%s</a> [passed:%d | broken:%d | failed:%d | total:%d] <br/>\n"
                if m != None:
                    indexhtml[line+1] = fmt % (
				webfilename,
				d.day, d.month, d.year,
				totalNrPassed, brokentests, failedtests, totalNrTests)
                else:
                    indexhtml.insert(line+1, fmt % (
				webfilename,
				d.day, d.month, d.year,
				totalNrPassed, brokentests, failedtests, totalNrTests))

                break
        indexhtmlout = open(index_fname, "w")
        indexhtmlout.writelines(indexhtml)
        indexhtmlout.close()
        #update xslt formating file
        shutil.copy (rundir + "/results.xslt", www_folder + "/")

    #move xml results to result-dir
    if os.path.isfile('results.xml'):
        resultdir = regdir + "/results/" + d.isoformat()
        if not os.path.isdir(resultdir):
            os.mkdir (resultdir)

        subprocess.getoutput("cp -rf " + "results.xml " + resultdir)

    bailout()

#call main
if __name__ == "__main__":
    main(sys.argv[1:])