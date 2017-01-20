#!/usr/bin/env python
# encoding: utf-8

import os, sys, json, sqlite3


if __name__ == '__main__':
    # 结果生成CSV文件
    # 更新数据库的cla字段
    conn = sqlite3.connect('./output/unionpoi.db')
    sql = 'select uid, cla from POIS'
    cu = conn.cursor()
    cu.execute(sql)

    connUpdate = sqlite3.connect('./output/unionpoi_new.db')
    cuUpdate = connUpdate.cursor()
    
    num = 0
    row = cu.fetchone()
    while (row != None):
        num += 1

        if (num % 10000 == 0):
            print num

        uid = row[0]
        value = row[1]

        if (value == '[]'): value = ''
        try:
            if (value.startswith('[[')):
                value = value.decode('unicode_escape').replace('u\'', '\'').replace('\'', '"')
                value = value.replace('<font color="#c60a00">', '').replace('</font>', '')
                clas = json.loads(value)
                valstr = ''
                for cla in clas:
                    if (valstr == ''): valstr += '{0},{1}'.format(cla[0], cla[1])
                    else: valstr += ';{0},{1}'.format(cla[0], cla[1])
                value = valstr
        except :
            pass

        # 又碰到编码问题
        #value = encrypt(value)
        if (value == None): value = ''
        value = value.encode('utf-8').decode('utf-8')
        args = (value, uid)
        cuUpdate.execute('update POIS set cla=? where uid=?', args)
        

        row = cu.fetchone()
    

    conn.close()
    connUpdate.commit()
    connUpdate.close()
    
    
    print u'OK'

