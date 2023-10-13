import sys
import subprocess
import glob
import datetime
import os
import time
import shutil
import pathlib
import re
import hashlib

from OpalRegressionTests.reporter import Reporter
from OpalRegressionTests.reporter import TempXMLElement

import OpalRegressionTests.stattest as stattest
import OpalRegressionTests.outtest as outtest
import OpalRegressionTests.lbaltest as lbaltest
import OpalRegressionTests.losstest as losstest

class OpalRegressionTests:
    def __init__(self, base_dir, tests, opal_args, publish_dir = None, timestamp = None):
        self.base_dir = base_dir
        self.tests = tests
        self.opal_args = opal_args
        self.publish_dir = publish_dir
        self.totalNrPassed = 0
        self.totalNrTests = 0
        self.rundir = sys.path[0]
        self.today = datetime.datetime.today()
        self.timestamp = timestamp

    def run(self):
        rep = Reporter()
        rep.appendReport("Start Regression Test on %s \n" % self.today.isoformat())
        rep.appendReport("==========================================================\n")

        if not self.timestamp:
            self.timestamp = self.today.strftime("%Y-%m-%d")

        # clean old results if exist
        plot_dir = None
        if self.publish_dir:
            plot_dir = os.path.join(self.publish_dir, "plots_" + self.timestamp)
            if os.path.isdir(plot_dir):
                shutil.rmtree(plot_dir)

        self._addDate(rep)
        for test in self.tests:
            rt = RegressionTest(self.base_dir, test, self.opal_args)
            rt.run()
            self.totalNrTests += rt.totalNrTests
            self.totalNrPassed += rt.totalNrPassed
            rt.publish(plot_dir)

        self._addRevisionStrings(rep)

        if self.publish_dir:
            results_file = os.path.join(self.publish_dir, "results_" + self.timestamp + ".xml")
            if os.path.isfile(results_file):
                os.remove (results_file)
            rep.dumpXML(results_file, "plots_" + self.timestamp)
            self._publish_results()

        rep.appendReport("\nSummary: {passed} / {total} tests passed \n".format(
            passed = self.totalNrPassed,
            total  = self.totalNrTests))

        rep.appendReport("\n==========================================================\n")
        rep.appendReport("Finished Regression Test on %s \n" %
                         datetime.datetime.today().isoformat())
        print (rep.getReport())

    def _getRevisionTests(self):
        if sys.version_info < (3,0):
            return commands.getoutput("git rev-parse HEAD")
        else:
            return subprocess.getoutput("git rev-parse HEAD")

    def _getRevisionOpal(self):
        exe = os.getenv("OPAL_EXE_PATH") + "/opal"
        if sys.version_info < (3,0):
            return commands.getoutput(exe + " --git-revision")
        else:
            return subprocess.getoutput(exe + " --git-revision")

    def _addDate(self, rep):
        date_report = TempXMLElement("Date")
        startDate_report = TempXMLElement("start")
        startDate_report.appendTextNode (self.today.isoformat())
        date_report.appendChild(startDate_report)
        rep.appendChild(date_report)

    def _addRevisionStrings(self, rep):
        revision_report = TempXMLElement("Revisions")

        revisionCode = self._getRevisionOpal()
        code_report = TempXMLElement("code")
        code_report.appendTextNode(revisionCode[0:7])
        revision_report.appendChild(code_report)

        full_code_report = TempXMLElement("code_full")
        full_code_report.appendTextNode(revisionCode)
        revision_report.appendChild(full_code_report)

        revisionTests = self._getRevisionTests()
        tests_report = TempXMLElement("tests")
        tests_report.appendTextNode(revisionTests[0:7])
        revision_report.appendChild(tests_report)

        full_tests_report = TempXMLElement("tests_full")
        full_tests_report.appendTextNode(revisionTests)
        revision_report.appendChild(full_tests_report)

        rep.appendChild(revision_report)

    def _publish_results (self):
        rep = Reporter ()

        webfilename = "results_" + self.timestamp + ".xml"

        index_fname = os.path.join (self.publish_dir, "index.html")
        if not os.path.exists(index_fname):
            shutil.copy (os.path.join (self.rundir, os.path.join("html", "index.html")), index_fname)

        # update 'index.html'
        indexhtml = open(index_fname).readlines()

        # search for the string 'insert here'
        for line in range(len(indexhtml)):
            if "insert here" in indexhtml[line]:
                m = re.search(webfilename, indexhtml[line + 1])
                fmt="<a href=\"%s\">%04d-%02d-%02d %02d:%02d</a> [passed:%d | broken:%d | failed:%d | total:%d] <br/>\n"
                text = fmt % (webfilename,
                              self.today.year, self.today.month, self.today.day,
                              self.today.hour, self.today.minute,
                              self.totalNrPassed, rep.NrBroken(), rep.NrFailed(),
                              self.totalNrTests)

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
        shutil.copy (os.path.join (self.rundir, "html", "ok.png"), self.publish_dir);
        shutil.copy (os.path.join (self.rundir, "html", "nok.png"), self.publish_dir);
        shutil.copy (os.path.join (self.rundir, "html", "results.xslt"), self.publish_dir)
        shutil.copy (os.path.join (self.rundir, "html", "accordion.js"), self.publish_dir)

class RegressionTest:

    def __init__(self, base_dir, simname, args):
        self.dirname = os.path.join (base_dir, simname)
        self.simname = simname
        self.args = args
        self.jobnr = -1
        self.totalNrTests = 0
        self.totalNrPassed = 0
        self.queue = ""
        self.date = datetime.date.today().isoformat()

    def _check_md5sum (self, fname_md5sum):
        """
        Check MD5 sum. File content must be compatible with md5sum(1) output.

        Note: Use this function for small files only!
        """
        with open (fname_md5sum, 'r') as f:
            first_line = f.readline ()
            f.close()

        md5sum, fname = first_line.split()
        ok = md5sum == hashlib.md5(open(fname, 'rb').read()).hexdigest()
        return ok


    def _validateReferenceFiles(self):
        """
        This method checks if all files in the reference directory are present
        and if their md5 checksums still concure with the ones stored after
        the simulation run
        """
        rep = Reporter()
        os.chdir(self.dirname)
        os.chdir("reference")
        allok = True

        for suffix in  [".stat", ".out", ".lbal"]:
            fname = self.simname + suffix
            fname_md5 = fname + ".md5"
            if not os.path.isfile(fname):
                rep_string = "\t Reference file %s is missing!\n % (fname)"
                allok = False
            if os.path.islink(fname_md5):
                continue
            if not os.path.isfile(fname_md5):
                rep_string = "\t Reference file %s is missing!\n % (fname_md5)"
                allok = False
                continue
            chksum_ok =  self._reportReferenceFiles(fname_md5)
            allok = allok and chksum_ok

        for loss_file in glob.glob("*.loss"):
            chksum_ok = self._reportReferenceFiles(loss_file + '.md5')
            allok = allok and chksum_ok

        for smb_file in glob.glob("*.smb"):            
            chksum_ok = self._reportReferenceFiles(smb_file + '.md5')
            allok = allok and chksum_ok

        return allok


    def _validateOutputFiles(self):
        """
        This method checks if all output files needed to compare with
        reference files files in the reference directory are present
        """
        rep = Reporter()
        allok = True

        for suffix in ['.stat','.out','.lbal','.loss','.smb']:
            outFiles = [x for x in os.listdir(".") if x.endswith(suffix)]
            refFiles = [x for x in os.listdir("reference") if x.endswith(suffix)]
            if bool(refFiles):
                if not bool(outFiles):
                    allok = False
                    rep.appendReport("\t ERROR: Reference output file %s %s \n" % (
                        refFiles, 'FAILED'))

        return allok


    def _reportReferenceFiles (self, fname):
        rep = Reporter()
        chksum_ok = self._check_md5sum(fname)
        rep.appendReport("\t Checksum for reference %s %s \n" % (
            fname, ('OK' if chksum_ok else 'FAILED')))
        return chksum_ok

    def _cleanup(self):
        """
        cleanup all OLD job files if there are any
        """
        for p in pathlib.Path(".").glob(self.simname + "-RT.*"):
            p.unlink()

        for p in pathlib.Path(".").glob(self.simname + "*.png"):
            p.unlink()

        for p in pathlib.Path(".").glob("*.loss"):
            p.unlink()

        for p in pathlib.Path(".").glob("*.smb"):
            p.unlink()

        if os.path.isfile(self.simname + ".stat"):
            os.remove (self.simname + ".stat")

        if os.path.isfile (self.simname + ".lbal"):
            os.remove (self.simname + ".lbal")

        if os.path.isfile (self.simname + ".out"):
            os.remove (self.simname + ".out")

    def run(self, run_local = True, q = None):
        os.chdir(self.dirname)
        self.queue = q
        self._cleanup()
        self._validateReferenceFiles()

        rep = Reporter()
        rep.appendReport("Run regression test " + self.simname + "\n")
        success = False
        # for the time being run_local is always true!
        if run_local:
            success = self.mpirun()
        else:
            # :FIXME: this is broken!
            self.submitToSGE()
            self.waitUntilCompletion()

        # copy to out file
        if os.path.isfile (self.simname + "-RT.o"):
            shutil.copy (self.simname + "-RT.o", self.simname + ".out")

        success = self._validateOutputFiles()
        if success:
            rep.appendReport("Reference output files OK\n")
        else:
            return False

        simulation_report = TempXMLElement("Simulation")
        simulation_report.addAttribute("name", self.simname)
        simulation_report.addAttribute("date", "%s" % self.date)

        with open(self.simname+".rt", "r") as infile:
            tests = [line.rstrip('\n') for line in infile]

        description = tests[0].lstrip("\"").rstrip("\"")
        if not success:
            description += ". Test failed."
        simulation_report.addAttribute("description", description)

        rep.appendChild(simulation_report)
        # loop over all tests in rt file, first line is a comment, skip this line
        for i, test in enumerate(tests[1::]):
            try:
                self.totalNrTests += 1
                test_root = TempXMLElement("Test")
                passed = self.checkResult(test, test_root)
                if passed:
                    self.totalNrPassed += 1
                simulation_report.appendChild(test_root)
            except Exception:
                exc_info = sys.exc_info()
                sys.excepthook(*exc_info)
                rep.appendReport(
                    ("Test broken: didn't succeed to parse %s.rt file line %d\n"
                     "%s\n"
                     "Python reports\n"
                     "%s\n\n") % (self.simname, i+2, test, exc_info[1])
                )

    def publish(self, plots_dir):
        if not plots_dir:
            return False
        pathlib.Path(plots_dir).mkdir(parents=True, exist_ok=True)
        for p in pathlib.Path(".").glob("*.png"):
            shutil.copy (p, plots_dir)

    def mpirun(self):
        os.chdir(self.dirname)
        rep = Reporter()
        if not os.access (self.simname+".local", os.X_OK):
            rep.appendReport ("Error: "+self.simname+".local file could not be executed\n")

        cmd = [ os.path.join(".", self.simname + ".local") ]
        cmd.extend(self.args)
        with open(self.simname + "-RT.o", "wb") as f:
            try:
                print ("Running test: " + cmd[0])
                sys.stdout.flush ()
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = proc.communicate(timeout=1200)
                print (out.decode ('utf-8'))
                print (err.decode ('utf-8'))
                f.write (out)
                f.write (err)
            except subprocess.TimeoutExpired:
                msg = "%s timed out!!!" % (cmd)
                print(msg)
                rep.appendReport(msg)
                return False
            except subprocess.CalledProcessError as e:
                msg = "%s exited with code %d" % (cmd, e.returncode)
                print(msg)
                rep.appendReport(msg)
                return False

        return True

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

    def checkResult(self, test, root):
        """
        handler for comparison of various output files with reference files

        Note that we do something different for loss tests as the file name in
        general is not <simname>.loss, rather it is <element_name>.loss

        For smb tests the file name is <simname>-bunch-idBunch.smb
        """
        nameparams = str.split(test,"\"")
        var = nameparams[1]
        params = str.split(nameparams[2].lstrip(), " ")
        rtest = 0
        if "stat" in test:
            rtest = stattest.StatTest(var, params[0], float(params[1]),
                                      self.dirname, self.simname)
        elif "out" in test:
            rtest = outtest.OutTest(var, params[0], float(params[1]),
                                    self.dirname, self.simname)
        elif "lbal" in test:
            rtest = lbaltest.LbalTest(var, params[0], float(params[1]),
                                      self.dirname, self.simname)
        else:
            file_name, file_extension = os.path.splitext(test.split()[0])
            if file_extension == ".loss":
                rtest = losstest.LossTest(var, params[0], float(params[1]),
                                          self.dirname, test.split()[0])
            elif file_extension == ".smb":
                rtest = stattest.StatTest(var, params[0], float(params[1]),
                                          self.dirname, file_name, file_extension)
            else:
                rep = Reporter()
                rep.appendReport("Error: unknown test type %s\n" % nameparams[0])
                return False

        return rtest.checkResult(root)
