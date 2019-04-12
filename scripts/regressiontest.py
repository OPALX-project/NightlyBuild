import sys
import subprocess
import glob
import datetime
import os
import time
import sys
import shutil
import pathlib
import threading
import hashlib

from reporter import Reporter
from reporter import TempXMLElement

from tools import genplot
from tools import readfile
from tools import check_md5sum

import stattest
import outtest
import lbaltest
import losstest

class RegressionTest:

    def __init__(self, dir, simname, args, resultdir):
        self.dirname = dir
        self.simname = simname
        self.args = args
        self.resultdir = resultdir
        self.jobnr = -1
        self.totalNrTests = 0
        self.totalNrPassed = 0
        self.queue = ""
        self.validateReferenceFiles()

    """
    This method checks if all files in the reference directory are present
    and if their md5 checksums still concure with the ones stored after
    the simulation run
    """
    def validateReferenceFiles(self):
        rep = Reporter()
        olddir = os.getcwd()
        os.chdir(self.dirname)
        os.chdir("reference")
        allok = True

        for suffix in  [".stat", ".out", ".lbal"]:
            fname = self.simname + suffix
            fname_md5 = fname + ".md5"
            if not os.path.isfile(fname):
                rep_string = "\t Reference file %s is missing!\n % (fname)"
                allok = False
            if not os.path.isfile(fname_md5):
                rep_string = "\t Reference file %s is missing!\n % (fname_md5)"
                allok = False
            chksum_ok = check_md5sum(fname_md5)
            rep.appendReport("\t Checksum for reference %s %s \n" % (
                fname, ('OK' if chksum_ok else 'FAILED')))
            allok = allok and chksum_ok

        for loss_file in glob.glob("*.loss"):
            loss_ok = check_md5sum (loss_file + '.md5')
            allok = allok and loss_ok
            rep.appendReport("\t Checksum for reference %s %s\n" % (loss_file, ('OK' if loss_ok else 'FAILED')))
        os.chdir(olddir)
        return allok

    """
    cleanup all OLD job files if there are any
    """
    def cleanup(self):
        for p in pathlib.Path(".").glob(self.simname + "-RT.*"):
            p.unlink()

        for p in pathlib.Path(".").glob(self.simname + "*.png"):
            p.unlink()

        for p in pathlib.Path(".").glob("*.loss"):
            p.unlink()

        if os.path.isfile(self.simname + ".stat"):
            os.remove (self.simname + ".stat")

        if os.path.isfile (self.simname + ".lbal"):
            os.remove (self.simname + ".lbal")

        if os.path.isfile (self.simname + ".out"):
            os.remove (self.simname + ".out")

        
    def run(self, root, run_local, q):

        basedir = os.getcwd()
        os.chdir(self.dirname)
        self.queue = q
        self.cleanup()

        rep = Reporter()
        rep.appendReport("\t run simulation\n")
            
        # run test
        if run_local:
            exit_code = self.mpirun()
        else:
            self.submitToSGE()
            self.waitUntilCompletion()
            
        # copy to out file
        if os.path.isfile (self.simname + "-RT.o"):
            shutil.copy (self.simname + "-RT.o", self.simname + ".out")

        self.performTests(root, exit_code)

        # move plots to plot dir
        d = datetime.date.today()
        plotdir = os.path.join (basedir, "results", d.isoformat(), "plots")
        pathlib.Path(plotdir).mkdir(parents=True, exist_ok=True)
        for p in pathlib.Path(".").glob("*.png"):
            shutil.copy (p, plotdir)

        #move tests to result folder
        dstdir = os.path.join (basedir, self.resultdir)
        if os.path.isfile (self.simname + ".stat"):
            shutil.copy (self.simname + ".stat", dstdir)
        if os.path.isfile (self.simname + ".lbal"):
            shutil.copy (self.simname + ".lbal", dstdir)
        if os.path.isfile (self.simname + ".out"):
            shutil.copy (self.simname + ".out",  dstdir)
        os.chdir(basedir)

    def mpirun(self):
        if not os.access (self.simname+".local", os.X_OK):
            rep = Reporter ()
            rep.appendReport ("Error: "+self.simname+".local file could not be executed\n")

        cmd = [ "./" + self.simname + ".local" ]
        cmd += self.args
        exit_code = 0
        with open(self.simname + "-RT.o", "wb") as f:
            try:
                print ("Running test: " + cmd[0])
                sys.stdout.flush ()
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                out, err = proc.communicate (timeout=600)
                print (out.decode ('utf-8'))
                print (err.decode ('utf-8'))
                f.write (out)
                f.write (err)
            except subprocess.TimeoutExpired:
                print ("%s timed out!!!" % (cmd))
                exit_code = 256
            except subprocess.CalledProcessError as e:
                print ("%s exited with code %d" % (cmd, e.returncode))
                exit_code = e.returncode
        self.jobnr = 0
        return exit_code

    def submitToSGE(self):
        # FIXME: we could create a sge file on the fly if no sge is specified
        # for a give test ("default sge")
        qsub_command = "qsub " + self.queue + " " + self.simname + ".sge"
        qsub_command += "-v REG_TEST_DIR=" + self.dirname + ",OPAL_EXE_PATH=" + os.getenv("OPAL_EXE_PATH")
        submit_out = subprocess.getoutput(qsub_command)
        self.jobnr = str.split(submit_out, " ")[2]

    def waitUntilCompletion(self):
        username = subprocess.getoutput("whoami")
        qstatout = subprocess.getoutput("qstat -u " + username + " | grep \"" + self.jobnr + "\"")
        while len(qstatout) > 0:
            #we only check every 30 seconds if job has finished
            time.sleep(30)
            qstatout = subprocess.getoutput("qstat -u " + username + " | grep \"" + self.jobnr + "\"")

    def performTests(self, root, exit_code):
        rep = Reporter()
        tests = readfile(self.simname + ".rt")
        description = tests[0].lstrip("\"").rstrip("\"")
        if exit_code == 256:
            description += ". Test timed out!"
        elif exit_code != 0:
            description += ". Test failed with exit code %d" % (exit_code)
        root.addAttribute("description", description)

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
                    ("Test broken: didn't succeed to parse %s.rt file line %d\n"
                     "%s\n"
                     "Python reports\n"
                     "%s\n\n") % (self.simname, i+2, test, exc_info[1])
                )
                #sys.exc_clear() in python 3 not supported any more


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
            rtest = stattest.StatTest(var, params[0], float(params[1]), self.simname)
        elif "out" in test:
            rtest = outtest.OutTest(var, params[0], float(params[1]), self.simname)
        elif "lbal" in test:
            rtest = lbaltest.LbalTest(var, params[0], float(params[1]), self.simname)
        elif test.split()[0][-4:] == "loss":
            rtest = losstest.LossTest(var, params[0], float(params[1]), test.split()[0])
        else:
            rep = Reporter()
            rep.appendReport("Error: unknown test type %s\n" % nameparams[0])
            return False

        return rtest.performTest(root)

