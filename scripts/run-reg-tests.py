#!/usr/bin/env python

import sys
import os
import shutil
import argparse

import OpalRegressionTests

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
    return sorted(tests)



def main(argv):
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
                        dest='opal_args', nargs='*', action='append',
                        help='arguments passed to OPAL',
			default=[])

    args = parser.parse_args()

    args.opal_args = [item for sublist in args.opal_args for item in sublist]
    print (args.opal_args)

    # get directory where regression tests are installed
    if args.base_dir:
        base_dir = os.path.abspath(args.base_dir)
    else:
        base_dir = os.getcwd()
    if not os.path.isdir (base_dir):
        print ("%s - regression tests base directory does not exist!" %
               (base_dir))
        sys.exit(1)
    
    # set target directory for results
    publish_dir = None
    if args.publish_dir:
        publish_dir = os.path.abspath(args.publish_dir)
    elif os.getenv("REGTEST_WWW"):
        publish_dir = os.getenv("REGTEST_WWW")

    if publish_dir and not os.path.exists(publish_dir):
        os.makedirs(publish_dir)

    # get directory where opal should be in and test whether opal exists or not
    try:
        if args.opal_exe_path:
            os.environ['OPAL_EXE_PATH'] = args.opal_exe_path
        elif os.getenv("OPAL_EXE_PATH"):
            args.opal_exe_path = os.getenv("OPAL_EXE_PATH")
        else:
            args.opal_exe_path = os.path.dirname(shutil.which("opal"))
            os.environ['OPAL_EXE_PATH'] = args.opal_exe_path

        opal = os.path.join(args.opal_exe_path, "opal")
        if not (os.path.isfile(opal) and os.access(opal, os.X_OK)):
            raise FileNotFoundError
    except:
        print ("opal - not found or not an executablet!")
        sys.exit(1)

    tests = scan_for_tests(base_dir)
    if args.tests:
        for test in args.tests:
            if not test in tests:
                print("%s - unknown test!" % (test))
                sys.exit(1)
        tests = sorted(args.tests)

    print ("Running the follwing regression tests:")
    for test in tests:
        print ("    {}".format(test))

    rt = OpalRegressionTests.OpalRegressionTests(base_dir, tests, args.opal_args, publish_dir)
    rt.run()

if __name__ == "__main__":
    main(sys.argv[1:])
