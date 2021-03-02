#!/usr/bin/env python2
"""Deploy CollectD on localhost for monitoring with mist.io"""

import os
import sys
import shutil
import tempfile
import subprocess

from urlparse import urljoin

VENV_VERSION = "1.11.6"
ANSIBLE_VERSION = "1.9.3"
PYPI_URL = "https://pypi.python.org/packages/source/"
PLAYBOOK_PATH = "ansible/enable.yml"
DEPLOY_COLLETD_BRANCH = "u2m"


def shellcmd(cmd, exit_on_error=True, verbose=True):
    """Run a command using the shell"""
    if verbose:
        print "Running:", cmd
    return_code = subprocess.call(cmd, shell=True)
    if exit_on_error and return_code:
        sys.exit("ERROR: Command '%s' exited with return code %d."
                 % (cmd, return_code))
    return return_code


def parse_args():
    try:
        import argparse
        parser = argparse.ArgumentParser(
            description="Deploy mist.io CollectD on localhost.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument("uuid", help="Machine uuid assigned by mist.io.")
        parser.add_argument("password",
                            help="Machine password assigned by mist.io, "
                                 "used to sign/encrypt CollectD data.")
        parser.add_argument("-m", "--monitor-server",
                            default="collectd.up2metric.com",
                            help="Remote CollectD server to send data to.")
        parser.add_argument("-p", "--port", default=25827, type=int,
                            help="Remote CollectD server port.")
        parser.add_argument(
            "--no-check-certificate", action='store_true',
            help="Don't verify SSL certificates when "
                 "fetching dependencies from HTTPS."
        )
        args = parser.parse_args()

    except ImportError:
        # Python 2.6 does not have argparse
        import optparse
        parser = optparse.OptionParser("usage: %prog [options] uuid password")
        parser.add_option("-m", default="collectd.up2metric.com",
                          dest="monitor_server")
        parser.add_option("-p", "--port", default=25826, type=int)
        parser.add_option("--no-check-certificate", action="store_true",
                          default=False)
        (args, list_args) = parser.parse_args()
        args.uuid = list_args[0]
        args.password = list_args[1]
    return args


def main():
    """Deploy CollectD on localhost for monitoring with mist.io"""

    args = parse_args()
    python = sys.executable
    # check if deploy_collectd repo is locally available
    playbook_path = ""
    if __file__ != '<stdin>':
        self_dir = os.path.dirname(os.path.realpath(__file__))
        playbook_path = os.path.join(self_dir, PLAYBOOK_PATH)
        if not os.path.exists(playbook_path):
            playbook_path = ""

    tmp_dir = tempfile.mkdtemp()
    print "*** Will work in '%s' ***" % tmp_dir
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)
    os.chdir(tmp_dir)
    if not shellcmd("command -v wget", False, False):
        # use wget
        get_url = "wget"
        if args.no_check_certificate:
            get_url += " --no-check-certificate"
    elif not shellcmd("command -v curl", False, False):
        # use curl
        get_url = "curl -L -O"
        if args.no_check_certificate:
            get_url += " -k"
    else:
        sys.exit("ERROR: Neither 'curl' nor 'wget' found, exiting.")

    print "*** Fetching virtualenv tarball ***"
    url = urljoin(PYPI_URL, "v/virtualenv/virtualenv-%s.tar.gz" % VENV_VERSION)
    shellcmd("%s %s" % (get_url, url))

    print "*** Extracting virtualenv tarball ***"
    shellcmd("tar -xzf virtualenv-%s.tar.gz" % VENV_VERSION)

    print "*** Creating virtualenv ***"
    shellcmd("%s virtualenv-%s/virtualenv.py env" % (python, VENV_VERSION))

    print "*** Installing virtualenv in virtualenv :) ***"
    shellcmd("env/bin/pip install virtualenv-%s.tar.gz" % VENV_VERSION)

    print "*** Fetching ansible tarball ***"
    url = urljoin(PYPI_URL, "a/ansible/ansible-%s.tar.gz" % ANSIBLE_VERSION)
    shellcmd("%s %s" % (get_url, url))

    print "*** Extracting ansible tarball ***"
    shellcmd("tar -xzf ansible-%s.tar.gz" % ANSIBLE_VERSION)

    print "*** Removing pycrypto from ansible requirements ***"
    shellcmd("sed -i \"s/, 'pycrypto[^']*'//\" ansible-%s/setup.py"
             % ANSIBLE_VERSION)

    print "*** Removing paramiko from ansible requirements ***"
    shellcmd("sed -i \"s/'paramiko[^']*', //\" ansible-%s/setup.py"
             % ANSIBLE_VERSION)

    print "*** Installing ansible in virtualenv ***"
    shellcmd("env/bin/pip install ansible-%s/" % ANSIBLE_VERSION)

    print "*** Generate ansible inventory file for localhost ***"
    with open("inventory", "w") as fobj:
        fobj.write("localhost ansible_connection=local "
                   "ansible_python_interpreter=%s\n" % python)

    print "*** Generate ansible.cfg ***"
    with open("ansible.cfg", "w") as fobj:
        fobj.write("[defaults]\n"
                   "hostfile = inventory\n"
                   "nocows = 1\n")

    if playbook_path:
        print "*** CollectD deployment playbook is locally available ***"
    else:
        print "*** Fetching mistio/deploy_collectd repo tarball ***"
        base_url = "https://github.com/ananos/deploy_collectd"
        shellcmd("%s %s/archive/%s.tar.gz" % (get_url, base_url,
                                              DEPLOY_COLLETD_BRANCH))

        print "*** Extracting mistio/deploy_collectd tarball ***"
        shellcmd("tar -xzf %s.tar.gz" % DEPLOY_COLLETD_BRANCH)

        playbook_path = "deploy_collectd-%s/%s" % (DEPLOY_COLLETD_BRANCH,
                                                   PLAYBOOK_PATH)

    print "*** Running CollectD deployment playbook against localhost ***"
    params = "uuid=%s password=%s monitor=%s port=%s" % (
        args.uuid, args.password, args.monitor_server, args.port
    )
    shellcmd("env/bin/ansible-playbook %s -e '%s'" % (playbook_path, params))

    print "*** CollectD deployment playbook completed successfully ***"
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
