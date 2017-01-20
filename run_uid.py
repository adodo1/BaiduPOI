#!/usr/bin/env python
# encoding: utf-8

import os, sys, time, subprocess

MaxProcess = 10     # 最大10个进程

def Work(script, arg):
    # 工作线程
    #process = subprocess.Popen('python {0} {1}'.format(script, arg), shell=True)
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

    script = 'baidupoi.py'      # 要允许的脚本名称
    minX = 98540
    maxX = 98600
    minY = 15871
    maxY = 55167

    processes = []
    for x in range(minX, maxX):
        tid = '[{0},{1}]_{2}'.format(x-minX+1, maxX-minX, x)
        # 任务ID 最小X 最大X 最小Y 最大Y
        args = '{0} {1} {2} {3} {4}'.format(tid, x, x+1, minY, maxY)
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


