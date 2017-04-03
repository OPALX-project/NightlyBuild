import datetime
import time
import sys
if sys.version_info < (3,0):
    import commands as subprocess
else:
    import subprocess
import os

from reporter import Reporter
from reporter import TempXMLElement

from tools import module_load

"""
builder class currently only support GIT and SVN!
"""
class Builder:

    def __init__(self, dir, name, target, builddir):
        self.target = target
        self.name = name
        self.basedir = dir
        self.builddir = builddir
        self.revision = "0"
        self.repo = "0"
        self.log = "";
        self.setSCM()

    def setSCM(self):
        if os.path.isdir(self.basedir + "/.svn"):
            self.repo = "SVN"
        else:
            self.repo = "GIT"

    def updateSCMRevision(self):
        if self.repo == "SVN":
            self.getSVNRevision()
        else:
            self.getGitRevision()

    def getSVNRevision(self):
        curdir = os.getcwd()
        os.chdir(self.basedir)
        info = subprocess.getoutput('svn info')
        infolines = str.split(info, "\n")
        self.revision = str.split(infolines[4], ":")[1].lstrip()
        os.chdir(curdir)

    def getGitRevision(self):
        curdir = os.getcwd()
        os.chdir(self.basedir)
        info = subprocess.getoutput('git info')
        self.revision = "TODO"
        os.chdir(curdir)

    def SCMUpdate(self):
        curdir = os.getcwd()
        os.chdir(self.basedir)
        if self.repo == "SVN":
            outtext = subprocess.getoutput("svn update")
        else:
            outtext = subprocess.getoutput("git fetch")
            outtext += subprocess.getoutput("git merge origin develop")
        self.updateSCMRevision()
        os.chdir(curdir)
        return outtext

    def runCMAKE(self):
        module_load("cmake")

        outtext = self.SCMUpdate()
        curdir = os.getcwd()
        subprocess.getoutput("rm -rf " + curdir + "/build")
        subprocess.getoutput("mkdir " + curdir + "/build")
        os.chdir(curdir + "/build")

        rep = Reporter()
        passed = False
        rep.appendReport("Running cmake for %s \n" % self.name)
        outtext = subprocess.getoutput("CXX=mpicxx cmake " + self.basedir)
        if os.path.isfile("Makefile"):
            rep.appendReport("Building %s \n" % self.name)
            outtext = subprocess.getoutput("make -j 4")
        else:
            rep.appendReport("Cmake failed!\n")
            rep.appendReport(outtext + "\n")

        if os.path.isfile(self.target):
            rep.appendReport("%s (r%s) passed build test \n" % (self.name, self.revision))
            passed = True
        else:
            rep.appendReport(outtext + "\n")
            rep.appendReport("%s (r%s) failed build test \n" % (self.name, self.revision))

        os.chdir(curdir)
        return (passed, self.revision)

    def setupEnv(self):
        #export environment variables! if not set!
        if not os.environ.get('CLASSIC_ROOT'):
            os.putenv("CLASSIC_ROOT", self.basedir + "/classic/5.0")

        if not os.environ.get('OPAL_ROOT'):
            os.putenv("OPAL_ROOT", self.basedir)

        if not os.environ.get('IPPL_PREFIX'):
            os.putenv("IPPL_PREFIX", "/gpfs/homefelsim/l_felsimsvn/extlib/ippl")

        if not os.environ.get('H5hut'):
            os.putenv("H5hut", "/gpfs/homefelsim/l_felsimsvn/extlib/H5hut-1.99.6")

    def build(self):
        rep = Reporter()
        self.setupEnv()

        rep.appendReport("Start Build Test on %s \n" % datetime.datetime.today())
        rep.appendReport("==========================================================\n")

        (passed, revision) = self.runCMAKE()
        rep.appendReport("==========================================================\n")
        build_report = TempXMLElement("Build")
        build_report.addAttribute("name", "OPAL")
        build_report.addAttribute("revision", "%s" % revision)
        if passed:
            build_report.addAttribute("status", "OK")
        else:
            build_report.addAttribute("status", "FAILED")
        rep.appendChild(build_report)

        #copy opal binary to result dir
        if os.path.isfile(self.builddir + "/"  + self.target):
            d = datetime.date.today()
            resultdir = self.basedir + "/opal-Tests/RegressionTests/results/" + d.isoformat()
            if not os.path.isdir(resultdir):
                subprocess.getoutput("mkdir -p " + resultdir)

            subprocess.getoutput("cp build/src/opal " + resultdir)

        rep.appendReport("Finished Build Test on %s \n" % datetime.datetime.today())

        return passed

