#!/usr/bin/env python
# encoding: utf-8

import os, sys, json, sqlite3


if __name__ == '__main__':
    # 结果生成CSV文件
    # 
    csvfile = open('./output/liuzhou.txt', 'w')
    conn = sqlite3.connect('./output/unionpoi_new.db')
    sql = 'select uid, name, alias, x, y, zoom, lat, lng, bdlat, bdlng, tel, cla, addr, state, city, town, street, code, area, description, time from POIS'
    cu = conn.cursor()
    cu.execute(sql)

    # 写标题
    csvfile.writelines('uid\tname\talias\tx\ty\tzoom\tlat\tlng\tbdlat\tbdlng\ttel\tcla\taddr\tstate\tcity\ttown\tstreet\tcode\tarea\tdescription\ttime\n')

    num = 0
    row = cu.fetchone()
    while (row != None):
        num += 1

        if (num % 5000 == 0):
            csvfile.flush()
            print num

        li = []
        for item in row:
            value = str(item).replace('\t', ' ')
            if (value == '[]'): value = 'None'
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
            li.append(value)
        
        csvfile.writelines('\t'.join(li)+'\n')


        row = cu.fetchone()
    

    conn.close()
    csvfile.flush()
    csvfile.close()
    
    
    print u'OK'

