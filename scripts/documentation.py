import os
import sys
if sys.version_info < (3,0):
    import commands as subprocess
else:
    import subprocess

class OpalDocumentation:

    #FIXME: check for LATEX
    def __init(self):
        self.build()

    """
    build doc
    building docs and doxygen should not be part of the regression tests
    """
    def build():
        curdir = os.getcwd()
        os.chdir("/gpfs/homefelsim/l_felsimsvn/work/opal-doc/doc/OPAL/user_guide")
        subprocess.getoutput("svn update")
        subprocess.getoutput("make")
        subprocess.getoutput("makeindex opal_user_guide")
        subprocess.getoutput("make")
        subprocess.getoutput("cp opal_user_guide.pdf /afs/psi.ch/project/amas/www/docs/opal/develop.pdf")
        os.chdir(curdir)


class OpalDoxygen:

    #FIXME: check for doxygen
    def __init__(self):
        self.build()

    """
    build doxygen
    building docs and doxygen should not be part of the regression tests
    """
    def build(self):
        curdir = os.getcwd()
        os.chdir("/gpfs/homefelsim/l_felsimsvn/work/opal/")
        subprocess.getoutput("doxygen")
        subprocess.getoutput("cp -r doc/html /afs/psi.ch/project/amas/www/docs/opal/")
        os.chdir(curdir)
