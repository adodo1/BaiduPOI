#!/usr/bin/env python
# encoding: utf-8

import os, sys, time

if __name__ == '__main__':
    tid = sys.argv[1]
    for i in range(10):
        print 'task: {0}, time: {1}'.format(tid, i+1)
        time.sleep(0.1)