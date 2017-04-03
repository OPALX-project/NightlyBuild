#!/usr/bin/python
import sys
if sys.version_info < (3,0):
    import commands
import subprocess
import os
import datetime
import re
import pprint

"""
parse linefile into list and strip newline
char at the end
"""
def readfile(fname):
    list = []
    infile = open(fname,"r")
    #TODO: TRY
    #list = open(fname, "r").readlines()
    while infile:
        line = infile.readline()
        if not line: break
        list.append(line.rstrip('\n'))
    infile.close()
    return list

"""
sends the "protocol" of "nrtest" tests to all addresses in "addresses"
"""
def sendmails(addresses, protocol, nrtest):
    d = datetime.date.today()
    failedtests = protocol.count("failed")
    brokentests = protocol.count("broken")

    MAIL = "/usr/sbin/sendmail"
    p = os.popen("%s -t" % MAIL, "w")
    for adr in addresses:
        p.write("To: %s \n" % adr)
    p.write("Subject: [Regression Tests] BROKEN %d/%d | FAILED %d/%d tests on %s" % (brokentests,nrtest,failedtests,nrtest,d.isoformat()))
    p.write("\n")
    p.write(protocol)
    sts = p.close()
    if sts != 0:
        print ("Mail Sent")


"""
simulates a "module load" by reading the new and to append environment variables
from the "module show" output
"""
def module_load(module):
    moduleout = ""
    if sys.version_info < (3,0):
        moduleout = commands.getoutput("source /opt/Modules/init/bash && module show " + module)
    else:
        moduleout = subprocess.getoutput("source /opt/Modules/init/bash && module show " + module)
    lines = str.split(moduleout, "\n")
    for line in lines:
        if line.startswith("setenv"):
            sete = str.split(line, "\t")[2].lstrip().rstrip()
            env = str.split(sete, " ")
            #print ("export " + env[0] + "=" + env[1])
            #os.putenv(env[0], env[1])
            os.environ[env[0]] = env[1]

        elif line.startswith("prepend-path"):
            sete = str.split(line, "\t")[1].lstrip().rstrip()
            envadd = str.split(sete, " ")
            #print ("export " + envadd[0] + "=" + envadd[1] + ":" + envadd[0])
            if os.getenv(envadd[0]):
                #os.putenv(envadd[0], envadd[1] + ":" + os.getenv(envadd[0]))
                os.environ[envadd[0]] = envadd[1] + ":" + os.getenv(envadd[0])
            else:
                #os.putenv(envadd[0], envadd[1])
                os.environ[envadd[0]] = envadd[1]

"""
parse header of .stat file (ASCII SDDS format)
"""
def readStatHeader(simname):
    header = {'number of lines': 0,
              'columns': {},
              'parameters': {}
              }
    numColumns = 0
    numScalars = 0
    readLines = 0
    lines = readfile(simname)
    length = len(lines)

    for i in range(length):
        line = lines[i]

        if "&column" in line:
            j = i
            column = ""
            while not "&end" in line:
                column += line
                j += 1
                line = lines[j]
            column += line

            name = str.split(column, "name=")[1]
            name = str.split(name, ",")[0]
            unit = str.split(column, "units=")[1]
            unit = str.split(unit, ",")[0]

            header['columns'][name] = {'units': unit, 'column': len(header['columns'])}
            numColumns += 1

        elif "&parameter" in line:
            j = i
            parameter = ""
            while not "&end" in line:
                parameter += line
                j += 1
                line = lines[j]
            parameter += line

            name = str.split(parameter, "name=")[1]
            name = str.split(name, ",")[0]

            header['parameters'][name] = {'row': len(header['parameters'])}


        elif "&data" in line:
            j = i
            while not "&end" in line:
                j += 1
                readLines += 1
                line = lines[j]

            readLines += 1
            break

        readLines += 1

    header['number of lines'] = readLines

    return header

"""
generate stat plot with gnuplot
returns fileame
"""
def genplot(simname, var):
    simnames = simname + ".stat"
    reference = "reference/" + simnames

    name = "name=" + var
    vars = []
    numberColumns = 0
    varCol = -1
    varUnit = ''
    varParts = str.split(var, "_")
    prettyVar = varParts[0]
    if len(varParts) == 2:
        prettyVar = varParts[0] + "(" + varParts[1] + ")"
    opalRevision = ''
    refRevision = 'reference'

    header = readStatHeader(simnames)
    readLines = header['number of lines']
    revLine = header['parameters']['revision']['row']
    numScalars = len(header['parameters'])
    sCol = header['columns']['s']['column']

    if header['columns'].has_key(var):
        varData = header['columns'][var]
        varCol = varData['column']
        varUnit = varData['units']

    lines = readfile(simnames)

    m = re.search('(.* git rev\. [A-Za-z0-9]{7})[A-Za-z0-9]*', lines[readLines + revLine]);

    if (m != None):
        opalRevision = m.group(1)
    else:
        opalRevision = lines[readLines + revLine]

    # a simple paste in gnuplot does not work since the
    # headers of the files do not necessarily have to have
    # the same length. therefore copy the data in temporary
    # files, delete them in the end
    if varCol > -1:
        data1 = open('data1.dat','w')
        for line in lines[(readLines + numScalars):]:
            values = line.split()
            data1.write(values[sCol] + "\t" + values[varCol] + "\n")
        data1.close()

    varCol = -1

    header = readStatHeader(reference)
    readLines = header['number of lines']
    revLine = header['parameters']['revision']['row']
    numScalars = len(header['parameters'])
    sCol = header['columns']['s']['column']

    if header['columns'].has_key(var):
        varData = header['columns'][var]
        varCol = varData['column']
        varUnit = varData['units']

    lines = readfile(reference)

    m = re.search('(.* git rev\. [A-Za-z0-9]{7})[A-Za-z0-9]*', lines[readLines + revLine]);

    if (m != None):
        refRevision = m.group(1)
    else:
        m = re.search('(.* svn rev\. [A-Za-z0-9]{7})[A-Za-z0-9]*', lines[readLines + revLine]);
        if (m != None):
            refRevision = 'reference: ' + m.group(1)
        else:
            refRevision = 'reference: ' + lines[readLines + revLine]

    if varCol > -1:
        data2 = open('data2.dat','w')
        for line in lines[(readLines + numScalars):]:
            values = line.split()
            data2.write(values[sCol] + "\t" + values[varCol] + "\n")
        data2.close()

    filename = ""
    d = datetime.date.today()
    if varCol > -1:
        filename = simname + "_" + var + "_" + str(d.day) + "_" + str(d.month) + "_" + str(d.year)
        plotcmd = "set terminal post enh col 20\n"
        plotcmd += "set output '" + filename + ".ps'\n"
        plotcmd += "set title '" + simname + "'\n"
        plotcmd += "set key below\n"
        plotcmd += "set ytics nomirror\n"
        plotcmd += "set y2tics\n"
        plotcmd += "set ylabel '" + prettyVar + " [" + varUnit + "]' font 'Helvetica-Bold,20'\n"
        plotcmd += "set y2label '{/Symbol D}" + prettyVar + " [" + varUnit + "]' font 'Helvetica-Bold,20'\n"
        plotcmd += "set xlabel 's [m]' font 'Helvetica-Bold,20'\n"
        plotcmd += "plot 'data1.dat' u 1:2 w l lw 2 t '" + opalRevision + "', "
        plotcmd += "'data2.dat' u 1:2 w l lw 2 t '" + refRevision + "', "
        plotcmd += "\"< paste data1.dat data2.dat\" u 1:($2-$4) w l lw 2 axis x1y2 t 'difference'" + ";\n"
        plot = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)

        if sys.version_info < (3,0):
            plot.communicate(plotcmd)
            os.system("convert -rotate 90 " + filename + ".ps " + filename + ".png")
            commands.getoutput("rm " + filename + ".ps data1.dat data2.dat")
        else:
            plot.communicate(bytes(plotcmd, "UTF-8"))
            os.system("convert -rotate 90 " + filename + ".ps " + filename + ".png")
            subprocess.getoutput("rm " + filename + ".ps data1.dat data2.dat")
    else:
        print ("Error in genplot: Cannot find stat variable!")

    return "plots_" + d.isoformat() + "/" + filename + ".png"

def getRevisionTests():
    if sys.version_info < (3,0):
        revision = commands.getoutput("git rev-parse HEAD")
    else:
        revision = subprocess.getoutput("git rev-parse HEAD")

    return revision

def getRevisionOpal():
    fh = open("testRevision.in","w")
    fh.write("WHAT, GITREVISION;\nQUIT;")
    fh.close()
    exe = os.getenv("OPAL_EXE_PATH") + "/opal"
    if sys.version_info < (3,0):
        output = commands.getoutput(exe + " testRevision.in 1>/dev/null")
        commands.getoutput("rm testRevision.in")
    else:
        output = subprocess.getoutput(exe + " testRevision.in 1>/dev/null")
        subprocess.getoutput("rm testRevision.in")

    revRe = re.search('GITREVISION="(.{40})";$',output)
    if (revRe != None):
        return (revRe.group(1))
    else:
        return ""