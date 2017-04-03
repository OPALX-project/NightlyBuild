#!/usr/bin/python 
import datetime
import time
import subprocess
import os
import sys

"""
This method checks if all files in the reference directory are present
and if their md5 checksums still concure with the ones stored after
the simulation run
"""
def validateReferenceFiles(simname):
    allok = False

    if os.path.isfile("reference/" + simname + ".stat") and \
       os.path.isfile("reference/" + simname + ".stat.md5") and \
       os.path.isfile("reference/" + simname + ".out") and \
       os.path.isfile("reference/" + simname + ".out.md5") and \
       os.path.isfile("reference/" + simname + ".lbal") and \
       os.path.isfile("reference/" + simname + ".lbal.md5"):

        statout = subprocess.getoutput("md5sum --check reference/" + simname + ".stat.md5")
        outout = subprocess.getoutput("md5sum --check reference/" + simname + ".out.md5")
        lbalout = subprocess.getoutput("md5sum --check reference/" + simname + ".lbal.md5")

        print (statout)
        print (outout)
        print (lbalout)

        allok = statout == "reference/" + simname + ".stat: OK" and \
                outout == "reference/" + simname + ".out: OK" and \
                lbalout == "reference/" + simname + ".lbal: OK"

    return allok

"""
method to generate default rt file
"""
def writeDefaultRTFile(regtestname):
    rtfile = "\"" + regtestname + "\"\n"
    rtfile += "stat \"rms_x\" last 1E-15    #this is a comment\n"
    rtfile += "stat \"rms_y\" last 1E-15    #this is a comment\n"
    rtfile += "stat \"rms_s\" last 1E-15    #this is a comment"

    rtoutfile = open(regtestname + ".rt", "w")
    rtoutfile.writelines(rtfile)
    rtoutfile.close()

"""
method to generate sge file
"""
def writeSgeFile(regtestname):

    sgefile = "#!/bin/bash \n"
    sgefile += "#$ -cwd\n"
    sgefile += "#$ -j y\n"
    sgefile += "#$ -pe mpi 4\n"
    sgefile += "#$ -N " + regtestname + "-RT\n"
    sgefile += "#$ -v MPIHOME=/opt/mpi/openmpi-1.2.6-intel-10.0,LD_LIBRARY_PATH=/opt/intel-mkl/mkl-10.0/lib/em64t:/opt/mpi/openmpi-1.2.6-intel-10.0/lib:/opt/intel/intel-10.0/fce-10.0/lib:/opt/intel/intel-10.0/cce-10.0/lib,OPAL_EXE_PATH,REG_TEST_DIR\n"
    sgefile += "\n"
    sgefile += "MACHINE_FILE=$TMPDIR/machinefile\n"
    sgefile += "awk '/^felsim/ {print $1\" slots=\"$2}' $PE_HOSTFILE > $MACHINE_FILE\n"
    sgefile += "cp $MACHINE_FILE machinefile.last\n"
    sgefile += "\n"
    sgefile += "echo \"PE_HOSTFILE:\"\n"
    sgefile += "cat  $PE_HOSTFILE\n"
    sgefile += "echo \"MACHINE_FILE:\"\n"
    sgefile += "cat $MACHINE_FILE\n"
    sgefile += "echo \"SLOTS=$NSLOTS\"\n"
    sgefile += "\n"
    sgefile += "cd $REG_TEST_DIR\n"
    sgefile += "OPAL=\"$OPAL_EXE_PATH/opal " + regtestname + ".in --commlib mpi --info 3 --warn 0 2>&1\"\n"
    sgefile += "CMD=\"$MPIHOME/bin/mpirun -machinefile $MACHINE_FILE -np $NSLOTS  --mca ras localhost --mca pls rsh  $OPAL \"\n"
    sgefile += "$CMD"
    
    sgeoutfile = open(regtestname + ".sge", "w")
    sgeoutfile.writelines(sgefile)
    sgeoutfile.close()

"""
main method
assuming we have a running simulation in the current directory (T7's and input file)
FIXME:
    o currently cannot handle restarted simulations
    o currently just copies all T7, dat und phases files to reg test dir
"""
def main(argv):
    d = datetime.date.today()
    #chdir to path of script
    #os.chdir(sys.path[0])

    regtestname = ""
    if ".in" in argv[0]:
        #extract input file
        regtestname = (str.split(argv[0], "."))[0]
    else:
        print ("./generate-regressiontest.py RegressionTestName.in")
        return

    #check if user has already set an OPAL executable
    #if not use the one from the last build test
    env = os.getenv("OPAL_EXE_PATH")
    if env is None:
        print ("OPAL_EXE_PATH not set! Please set it to the directory containing the opal binary and rerun the script.")
        return

    print ("Starting to generate Regression Test: " + regtestname)

    #only generate regression tests if opal executable is valid
    if os.path.isfile(os.getenv("OPAL_EXE_PATH") + "/opal"):
        subprocess.getoutput("mkdir " + regtestname)
        subprocess.getoutput("cp " + regtestname + ".in " + regtestname + "/")
        subprocess.getoutput("cp *.T7 " + regtestname + "/")
        subprocess.getoutput("cp *.dat " + regtestname + "/")
        subprocess.getoutput("cp *.phases " + regtestname + "/")
        os.chdir(regtestname)
        writeSgeFile(regtestname)
        os.environ["REG_TEST_DIR"] = os.getcwd()
        runout = subprocess.getoutput("qsub " + regtestname + ".sge -v REG_TEST_DIR=" + os.getcwd() + ",OPAL_EXE_PATH=" + os.getenv("OPAL_EXE_PATH"))
        username = subprocess.getoutput("whoami")
        #wait for job to finish for now do this serially
        qstatout = subprocess.getoutput("qstat -u " + username)
        while len(qstatout) > 0:
            #we only check every minute if job has finished
            time.sleep(10)
            qstatout = subprocess.getoutput("qstat -u " + username)

        #copy o to out file
        subprocess.getoutput("mv " + regtestname + "-RT.o* " + regtestname + ".out")
        subprocess.getoutput("rm " + regtestname + "-RT.po*")
        subprocess.getoutput("mkdir reference")
        subprocess.getoutput("mv " + regtestname + ".out reference/")
        subprocess.getoutput("mv " + regtestname + ".stat reference/")
        subprocess.getoutput("mv " + regtestname + ".lbal reference/")
        subprocess.getoutput("md5sum reference/" + regtestname + ".out > reference/" + regtestname + ".out.md5")
        subprocess.getoutput("md5sum reference/" + regtestname + ".lbal > reference/" + regtestname + ".lbal.md5")
        subprocess.getoutput("md5sum reference/" + regtestname + ".stat > reference/" + regtestname + ".stat.md5")
        if validateReferenceFiles(regtestname):
            print ("Reference data verified successfully")
        else:
            print ("Reference data verification failed!")
            return
        writeDefaultRTFile(regtestname)

    else:
        print ("OPAL_EXE_PATH not set! Please set it to the directory containing the opal binary and rerun the script.")
        return
    
    print ("Finished generating Regression Test " + regtestname)
    subprocess.getoutput("rm machinefile.last")
    subprocess.getoutput("rm " + regtestname + ".h5")
    print ("Please edit the " + regtestname + ".rt file to suit your needs and cleanup the regression test directory. Once this is done move it to opal-Tests/RegressionTests/, svn add and commit.")

#call main
if __name__ == "__main__":
    main(sys.argv[1:])
