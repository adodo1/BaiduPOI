#!/usr/bin/env python
# encoding: utf-8

import os, sys, time, subprocess

MaxProcess = 4     # 最大20个进程

def Work(script, arg):
    # 工作线程
    process = subprocess.Popen('python {0} {1}'.format(script, arg), shell=True)
    return process

def CanStartNewProcess(processes):
    # 判断是否可以
    if (len(processes) < MaxProcess): return True
    for process in processes:
        if (process.poll()!=None):
            processes.remove(process)
            time.sleep(0.1)
            return True
    return False

if __name__ == '__main__':
    # 多进程工作

    script = 'BaiduPoiInfo.py'      # 要运行的脚本名称

    processes = []
    for i in range(1, 20000, 10000):
        print '====================================='
        print i
        print '====================================='
        args = '{0} {1}'.format(i, 10000)
        while (CanStartNewProcess(processes) == False):
            time.sleep(2)
        process = Work(script, args)
        processes.append(process)

    print 'Waitting...'
    # 等待最后的线程结束
    while (len(processes)>0):
        for process in processes:
            if (process.poll()!=None):
                processes.remove(process)
        time.sleep(2)

    print 'Finish.'


