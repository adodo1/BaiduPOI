#!/usr/bin/env python
# encoding: utf-8

import os, sys, sqlite3


if __name__ == '__main__':
    # 合并两个最终成果

    conn1 = sqlite3.connect('./1.db')
    conn2 = sqlite3.connect('./2.db')
    
    sql1 = 'select uid, name, alias, x, y, zoom, lat, lng, bdlat, bdlng, tel, cla, addr, state, city, town, street, code, area, description, time from POIS'
    sql2 = 'insert into POIS(uid, name, alias, x, y, zoom, lat, lng, bdlat, bdlng, tel, cla, addr, state, city, town, street, code, area, description, time) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'

    cu1 = conn1.cursor()
    cu2 = conn2.cursor()
    cu1.execute(sql1)

    num = 0
    row = cu1.fetchone()
    while (row != None):
        num += 1
        cu2.execute(sql2, row)
        if (num % 5000 == 0):
            conn2.commit()
            print num
        row = cu1.fetchone()
    
    conn2.commit()
    conn1.close()
    conn2.close()
    
    print u'OK'

