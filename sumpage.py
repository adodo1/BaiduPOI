#!/usr/bin/env python
# encoding: utf-8

import os, sys, sqlite3, fnmatch

def GetCount(conn, dbfile):
    sql = r'select count(*) as SUM from POIDATA'
    cu = conn.cursor()
    cu.execute(sql)
    record = cu.fetchall()
    if len(record) > 0:
        count = int(record[0][0])
        if (count <= 23): print '{0}: {1}'.format(count, dbfile)
        return count
    else:
        print '{0}: {1}'.format(0, dbfile)
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
        count = GetCount(conn, dbfile)
        sumuid += count
        path, name = os.path.split(dbfile)
        #print '{0}共: {1}'.format(name, count)
        conn.close()

    print u'总共: {0}'.format(sumuid)

