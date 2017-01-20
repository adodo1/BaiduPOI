#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, urllib, urllib2, time
import ctypes, socket, threading, json, Queue, sqlite3
from threading import Thread


if __name__ == '__main__':
    minX = 63743                    # 最左边X号索引 单位是百度的瓦片索引坐标
    maxX = 117887                   # 最右边X号索引 单位是百度的瓦片索引坐标
    minY = 15871                    # 最下面Y号索引 单位是百度的瓦片索引坐标
    maxY = 55167                    # 最上面Y号索引 单位是百度的瓦片索引坐标

    num = 1
    for x in range(minX, maxX):
        xmin = x
        xmax = x+1
        ymin = minY
        ymax = maxY
        tid = num

        while True:
            num = 0
            files = os.listdir('.')
            for f in files:
                name, ext = os.path.splitext(f)
                if (ext=='.lock'): num += 1
            if (num >= 10):
                time.sleep(10)
                continue
            else: break
        os.popen('python baidupoi.py {0} {1} {2} {3} {4} > {0}.log'.format(tid, xmin, xmax, ymin, ymax))
        time.sleep(2)
        num += 1
