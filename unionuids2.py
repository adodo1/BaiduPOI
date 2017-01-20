#!/usr/bin/env python
# encoding: utf-8

import os, sys, sqlite3, fnmatch

def UnionUIDS(fname, connUnion):
    # 合并
    cuUnion = connUnion.cursor()
    f = open(fname, 'r')
    line = f.readline()
    while line != '':
        if (line.find('ERROR')>0):
            index = line.find('-')
            uid = line[index+2:]
            args = (0, uid)
            cuUnion.execute('insert into UIDS values(?,?)', args)
        line = f.readline()
    f.close()

def iterfindfiles(path, fnexp):
    # 递归文件
    result = []
    for root, dirs, files in os.walk(path):
        for filename in fnmatch.filter(files, fnexp):
            result.append(os.path.join(root, filename))
    return result

def InitDB(conn):
    # 创建UIDS表
    cu = conn.cursor()
    cu.execute(
        """create table if not exists UIDS(
                   id number,            -- ID
                   uid varchar(25))      -- UID值
        """)

if __name__ == '__main__':
    # 第二步，合并失败的UID

    connUnion = sqlite3.connect('./union_uids.db')
    InitDB(connUnion)

    files = iterfindfiles(r'./', '*.log')

    num = 0
    for fname in files:
        num += 1
        print '{0}/{1}: {2}'.format(num, len(files), fname)
        UnionUIDS(fname, connUnion)

    connUnion.commit()
    connUnion.close()
    print u'OK'

