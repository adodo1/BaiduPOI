#!/usr/bin/env python
# encoding: utf-8

import os, sys, sqlite3, fnmatch

def GetCount(conn):
    sql = r'select count(*) as SUM from UIDS'
    cu = conn.cursor()
    cu.execute(sql)
    record = cu.fetchall()
    if len(record) > 0:
        return int(record[0][0])
    return 0

def iterfindfiles(path, fnexp):
    result = []
    for root, dirs, files in os.walk(path):
        for filename in fnmatch.filter(files, fnexp):
            result.append(os.path.join(root, filename))
            
    return result
 


if __name__ == '__main__':
    # 统计数量
    # 1. 递归找到所有db文件
    # 2. 统计uids表的记录数
    files = iterfindfiles(r'./', '*.db')
    sumuid = 0
    for dbfile in files:
        conn = sqlite3.connect(dbfile)
        count = GetCount(conn)
        sumuid += count
        path, name = os.path.split(dbfile)
        #print '{0}共: {1}'.format(name, count)
        conn.close()

    print u'总共: {0}'.format(sumuid)

