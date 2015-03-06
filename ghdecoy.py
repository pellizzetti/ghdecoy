#!/usr/bin/env python

import getopt
import sys
import os
import urllib2
import re
import random
import math
import subprocess


def usage():
    print """Usage: ghdecoy.ph [-hn] [--help] [-d DIR] [-u USER] [-r REPO] COMMAND

  -h|--help : display this help message
  -n        : just create the decoy repo but don't push it to github
  -d DIR    : directory to craft the the fake repository in
  -u USER   : use the username USER instead of the current unix user
  -r REPO   : use the repository REPO instead of the default 'decoy'

  COMMAND   : one of the following:
              fill   : fill all occurrences of 3 or more days in a row
                       without commits with random noise
              append : same as fill, but only fills the blank space
                       after the last existing commit
"""


def get_calendar(user):
    url = 'https://github.com/users/' + user + '/contributions'
    try:
        page = urllib2.urlopen(url)
    except (urllib2.HTTPError, urllib2.URLError) as err:
        print "There was a problem fetching data from {0}".format(url)
        print err
        return None
    return page.readlines()


def get_factor(data):
    max_val = 0
    for entry in data:
        if entry['count'] > max_val:
            max_val = entry['count']

    factor = max_val / 4.0
    if factor == 0:
        return 1
    factor = math.ceil(factor)
    factor = int(factor)
    return factor


def cal_scale(scale_factor, data_out):
    for entry in data_out:
        entry['count'] *= scale_factor


def parse_args(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "hnd:r:u:", ["help"])
    except getopt.GetoptError as err:
        print str(err)
        usage()
        sys.exit(2)

    if len(args) != 1:
        usage()
        sys.exit(1)

    conf = {
        'dryrun': False,
        'repo': 'decoy',
        'user': os.getenv("USER"),
        'wdir': '/tmp'
    }
    if args[0] in ("append", "fill"):
        conf['action'] = args[0]
    else:
        print "Invalid command: {}".format(args[0])
        sys.exit(1)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif opt == "-n":
            conf['dryrun'] = True
        elif opt == "-d":
            conf['wdir'] = arg
        elif opt == "-r":
            conf['repo'] = arg
        elif opt == "-u":
            conf['user'] = arg

    if not conf['user']:
        print "Could not determine username; please use -u"
        sys.exit(1)

    return conf


def create_dataset(data_in):
    ret = []
    idx_start = -1
    idx_cur = 0
    idx_max = len(data_in) - 1
    random.seed()

    for entry in data_in:
        if entry['count'] or idx_cur == idx_max:
            if idx_start > -1:
                for i in range(idx_start,
                               idx_cur if entry['count'] else idx_cur + 1):
                    ret.append({'date': data_in[i]['date'],
                                'count': random.randint(0, 4)})
                idx_start = -1
        elif idx_start == -1:
            idx_start = idx_cur
        idx_cur += 1

    cal_scale(get_factor(data_in), ret)
    return ret


def main():
    conf = parse_args(sys.argv)

    print "{} {} {}".format(conf['user'], conf['repo'], conf['action'])

    cal = get_calendar(conf['user'])
    if not cal:
        sys.exit(1)

    data_in = []
    for line in cal:
        match = re.search(r'data-count="(\d+)".*data-date="(\d+-\d+-\d+)"',
                          line)
        if not match:
            continue
        data_in.append({'date': match.group(2) + "T12:00:00",
                        'count': int(match.group(1))})

    data_out = create_dataset(data_in)

    template = ('#!/bin/bash\n'
                'REPO={0}\n'
                'git init $REPO\n'
                'cd $REPO\n'
                'touch decoy\n'
                'git add decoy\n'
                '{1}\n'
                'git remote add origin git@github.com:{2}/$REPO.git\n'
                'git pull\n')
    if not conf['dryrun']:
        template = ''.join([template, 'git push -f -u origin master\n'])

    fake_commits = []
    for entry in data_out:
        for i in range(entry['count']):
            fake_commits.append(
                'echo {1} >> decoy\nGIT_AUTHOR_DATE={0} GIT_COMMITTER_DATE={0} git commit -a -m "ghdecoy" > /dev/null\n'.format(
                    entry['date'], i))

    script_name = ''.join([conf['wdir'], '/ghdecoy.sh'])
    script_fo = open(script_name, "w")
    script_fo.write(template.format(conf['repo'], ''.join(fake_commits), conf['user']))
    script_fo.close()

    os.chdir(conf['wdir'])
    subprocess.call(['sh', './ghdecoy.sh'])


if __name__ == '__main__':
    main()
