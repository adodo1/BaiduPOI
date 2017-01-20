#!/usr/bin/env python
# encoding: utf-8

import os, sys, sqlite3, fnmatch, json

def GetDatas(context):
    # 解析数据
    try:
        strjson = context[22:-2]
        decodejson = json.loads(strjson)
        error_no = int(decodejson['content'][0]['error_no'])
        if (error_no != 0): return None
        uid_num = int(decodejson['content'][0]['uid_num'])
        result = []
        for item in decodejson['content'][0]['uids']:
                uid = item['uid']
                x = float(item['icon']['x'])
                y = float(item['icon']['y'])
                result.append({'uid':uid, 'mx':x, 'my':y})
        return result
    except:
        print 'Error ......'
        return []


def UnionUIDS(conn, connUnion):
    # 合并
    cu = conn.cursor()
    cuUnion = connUnion.cursor()
    sql = 'select x, y, zoom, context, time from POIDATA'
    cu.execute(sql)
    record = cu.fetchall()
    for row in record:
        x = row[0]
        y = row[1]
        zoom = row[2]
        context = row[3]
        time = row[4]
        datas = GetDatas(context)

        for data in datas:
            # 插入数据
            args = (x, y, zoom, data['mx'], data['my'], data['uid'], time)
            cuUnion.execute('insert into UIDS values(?,?,?,?,?,?,?)', args)
    

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
                   x number,            -- 百度瓦片X索引
                   y number,            -- 百度瓦片Y索引
                   zoom number,         -- 百度瓦片缩放级别
                   mx number,           -- 百度墨卡托X
                   my number,           -- 百度墨卡托Y
                   uid varchar(25),     -- UID值
                   time number)         -- 时间戳
        """)

if __name__ == '__main__':
    # 合并所有UID

    connUnion = sqlite3.connect('./union.db')
    InitDB(connUnion)

    files = iterfindfiles(r'./', '*.db')
    num = 0
    for dbfile in files:
        if (dbfile.find('union.db')>=0): continue
        conn = sqlite3.connect(dbfile)
        num += 1
        path, name = os.path.split(dbfile)
        UnionUIDS(conn, connUnion)
        conn.close()
        if (num % 1000 == 0):
            print '{0}/{1}: {2}'.format(num, len(files), name)
            connUnion.commit()
    print '{0}/{1}: {2}'.format(num, len(files), '')

    connUnion.commit()
    connUnion.close()
    print u'OK'

