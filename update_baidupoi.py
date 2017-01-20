#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, urllib, urllib2, time
import ctypes, socket, threading, json, Queue, sqlite3
from threading import Thread

# 1. 输入一个范围参数 tid, minX maxX, minY, maxY, zoom
# 2. 计算出总任务数 加入线程队列中 能够显示线程进度
# 3. 信息输出到数据库中, 失败信息也记录下来, 任务数不能超过10W
#    如果程序结束后没有添加任何记录, 该数据库不会被保存
# 4. 第一步获取 UID 列表


# 定义全局变量
mutex = threading.Lock()        # 线程锁
socket.setdefaulttimeout(9)     # 超时时间9秒
dbisempty = True                # 数据库为空
success = True                  # 任务是否成功
tid  = None                     # 任务ID

##########################################################################
class Worker(Thread):
    # 线程池工作线程 只支持 python 2.7 或以上版本
    worker_count = 0
    def __init__(self, workQueue, resultQueue, timeout = 0, **kwds):
       Thread.__init__(self, **kwds)
       self.id = Worker.worker_count
       Worker.worker_count += 1
       self.setDaemon(True)
       self.workQueue = workQueue
       self.resultQueue = resultQueue
       self.timeout = timeout
       self.start()
     
    def run(self):
        ''' the get-some-work, do-some-work main loop of worker threads '''
        while True:
            try:
                callable, args, kwds = self.workQueue.get(timeout=self.timeout)
                res = callable(*args, **kwds)
                #print "worker[%2d]: %s" % (self.id, str(res))
                self.resultQueue.put(res)
            except Queue.Empty:
                break
            except :
                print 'worker[%2d]' % self.id, sys.exc_info()[:2]

class WorkerPool:
    # 线程池
    def __init__(self, num_of_workers=10, timeout = 1):
        self.workQueue = Queue.Queue()
        self.resultQueue = Queue.Queue()
        self.workers = []
        self.timeout = timeout
        self._recruitThreads(num_of_workers)
    def _recruitThreads(self, num_of_workers):
        for i in range(num_of_workers): 
            worker = Worker(self.workQueue, self.resultQueue, self.timeout)
            self.workers.append(worker)
    def wait_for_complete(self):
        # ...then, wait for each of them to terminate:
        while len(self.workers):
            worker = self.workers.pop()
            worker.join()
            if worker.isAlive() and not self.workQueue.empty():
                self.workers.append(worker)
        #print "All jobs are are completed."
    def add_job(self, callable, *args, **kwds):
        self.workQueue.put((callable, args, kwds))
    def get_result(self, *args, **kwds):
        return self.resultQueue.get(*args, **kwds)
    

##########################################################################

class Spider:
    # 爬虫
    def __init__(self, conn):
        self.POI_URL = 'http://online{0}.map.bdimg.com/js/?qt=vQuest&styles=pl&x={1}&y={2}&z={3}&v=085&fn=MPC_Mgr.getPoiDataCbk'        # 获取POI列表
        self.INFO_URL = 'http://map.baidu.com/?qt=inf&uid={0}'                                                                          # 根据POI的UID得到具体信息
        self.conn = conn            # 数据库连接
        self.uidList = []           # 获取的UID列表
        self.num = 0

    def GetHtml(self, url):
        # 下载网页数据 在这里可以处理链接超时 404 等错误
        # 同时这里可以设置代理或构造数据头 页面编码等
        try:
            return urllib.urlopen(url).read().decode('utf-8')
        except:
            try:
                return urllib.urlopen(url).read().decode('utf-8')
            except:
                try:
                    return urllib.urlopen(url).read().decode('utf-8')
                except:
                    try:
                        return urllib.urlopen(url).read().decode('utf-8')
                    except:
                        global success
                        success = False
                        return None

    # 解析UID =============================================================
    def GetUids(self, html):
        # 解析出UID
        try:
            strjson = html[22:-2]
            decodejson = json.loads(strjson)
            error_no = int(decodejson['content'][0]['error_no'])
            if (error_no != 0): return None
            uid_num = int(decodejson['content'][0]['uid_num'])
            uids = []
            for item in decodejson['content'][0]['uids']:
                uids.append(item['uid'])
            return uids
        except:
            global success
            success = False
            return None
        
    def DownloadUidList(self, x, y, zoom):
        # 下载POI列表UID
        url = self.POI_URL.format(self.num % 10, x, y, zoom)
        global success
        global dbisempty
        global tid
        
        # 读取数据
        html = self.GetHtml(url)
        if (html !=None and html.startswith('MPC')==False): html = self.GetHtml(url)

        if (html==None or html.startswith('MPC')==False):
            # 失败
            error = 'Get uid html {%s, %s, %s, %s} error' % (tid, x, y, zoom)
            ShowInfo(error, 'e', True)
            success = False
            return []
        else:
            # 写入文件 并 解析 返回uids
            self.num += 1
            if (self.num % 1000 == 0):
                ShowInfo('Downloaded poi list %s: %s' % (tid, self.num))
                mutex.acquire()
                self.conn.commit()
                mutex.release()

            uids = self.GetUids(html)
            if (uids==None):
                error = 'Decode json {%s, %s, %s, %s} error' % (tid, x, y, zoom)
                ShowInfo(error, 'e', True)
                success = False
                return []
            else:
                # 插入数据库 注意加锁 否则会有问题
                mutex.acquire()
                cursor = self.conn.cursor()
                args = (x, y, zoom, html, int(time.time()))
                if (len(uids) > 0):
                    dbisempty = False
                    cursor.execute('insert into POIDATA values(?,?,?,?,?)', args)
                    for uid in uids:
                        args = (x, y, zoom, uid, int(time.time()))
                        cursor.execute('insert into UIDS values(?,?,?,?,?)', args)
                #self.conn.commit()
                mutex.release()
                
                return uids


    def UidThread(self, x, y, zoom):
        # 跑UID的线程
        uids = self.DownloadUidList(x, y, zoom)
        for uid in uids:
            self.uidList.append([uid, x, y, zoom])
            
    def DownloadPoiList(self, uid, x, y, zoom):
        # 下载POI列表
        global tid
        global dbisempty

        url = self.INFO_URL.format(uid)
        # 读取数据
        html = self.GetHtml(url)
        if (html!=None and html.startswith('{')==False): html = self.GetHtml(url)

        if (html==None):
            # 失败
            error = 'Get info {%s, %s, %s, %s, %s} list error' % (tid, uid, x, y, zoom)
            ShowInfo(error, 'e', True)
        else:
            # 插入数据库
            self.num += 1
            if (self.num % 1000 == 0):
                ShowInfo('Downloaded poi info list %s: %s' % (tid, self.num))
                mutex.acquire()
                self.conn.commit()
                mutex.release()
                
            # 插入数据库 注意加锁 否则会有问题
            mutex.acquire()
            cursor = self.conn.cursor()
            args = (uid, html, int(time.time()))
            dbisempty = False
            cursor.execute('insert into POIS values(?,?,?)', args)
            #self.conn.commit()
            mutex.release()

    # 多线程控制 =============================================================
    def Work(self, maxThreads, baiduTiles, zoom):
        # 爬取数据
        global tid
        if (True):
            # UID的收集
            self.num = 0
            wp = WorkerPool(maxThreads)                 # 线程数量
            for baiduTile in baiduTiles:
                x = baiduTile[0]
                y = baiduTile[1]
                wp.add_job(self.UidThread, x, y, zoom)  # 添加工作
            wp.wait_for_complete()                      # 等待完成
            self.conn.commit()
            ShowInfo('{0} Got UID {1} !!!!!!!!!!!!!!!!!!!!'.format(tid, len(self.uidList)))
            
        if (False):
            # POI信息收集
            self.num = 0
            wp = WorkerPool(maxThreads)                             # 线程数量
            for item in self.uidList:
                uid = item[0]
                x = item[1]
                y = item[2]
                wp.add_job(self.DownloadPoiList, uid, x, y, zoom)   # 添加工作
            wp.wait_for_complete()                                  # 等待完成
            self.conn.commit()
            pass
        
        pass


##########################################################################


def ShowInfo(text, level='i', save=False):
    # 输出信息
    # text 信息内容
    # level 信息类别 info, warning, error 
    # save 是否保存到日志里

    mutex.acquire()
    # 打印时间
    if (level==None or len(level)==0): level='i'
    stime = time.strftime(r'%m/%d %H:%M:%S')
    print stime,
    # 输出信息
    print '[{0}]:'.format(level[0]),
    print text
    # 写入日志
    if (save == True):
        open(LOG_FILE, 'a').write('{0} [{1}]: {2}\r\n'.format(stime, level[0], text))
    mutex.release()

    
def InitDB(conn):
    # 初始化数据库
    cu = conn.cursor()
    try:
        # 创建POIDATA表
        cu.execute(
            """create table if not exists POIDATA(
                   x number,            -- 百度瓦片X索引
                   y number,            -- 百度瓦片Y索引
                   zoom number,         -- 百度瓦片缩放级别
                   context text,        -- json内容
                   time number)         -- 时间戳
            """)
    except: pass
    
    try:
        # 创建UIDS表
        cu.execute(
            """create table if not exists UIDS(
                   x number,            -- 百度瓦片X索引
                   y number,            -- 百度瓦片Y索引
                   zoom number,         -- 百度瓦片缩放级别
                   uid varchar(25),     -- UID值
                   time number)         -- 时间戳
            """)
    except: pass

    try:
        # 创建POIS表
        cu.execute(
            """create table if not exists POIS(
                   uid varchar(25),     -- UID值
                   context text,        -- json内容
                   time number)         -- 时间戳
            """)
    except: pass


def GetData(dbfile, x, y, z):
    # 补录数据
    outpath = './output'                        # 输出路径
    dbfile = '%s/%s.db' % (outpath, dbfile)     # 数据库
    # 初始化
    if (os.path.exists(outpath)==False):
        os.makedirs(outpath)
    # 创建数据库 sqlite不能工作在多线程里 否则会出问题 但是可以在线程里加锁解决
    conn = sqlite3.connect(dbfile, check_same_thread = False)
    InitDB(conn)

    spider = Spider(conn)
    uids = spider.DownloadUidList(x, y, z)
    print '{0}: {1}, {2}, {3} [{4}]'.format(dbfile, x, y, z, len(uids))

    
    conn.close()
    
def ReadErrorLine(line):
    # 解析错误的记录
    indexS = line.find('{[')
    indexE = line.find(', ')
    indexF = line.find('} ')
    if (indexS < 0 or indexE < 0):
        return None

    dbfile = line[indexS+1:indexE]
    strs = line[indexE+1:indexF].split(',')
    x = int(strs[0])
    y = int(strs[1])
    z = int(strs[2])

    return dbfile, x, y, z

    

LOG_FILE = './baidupoi.log'     # 线程日志
TASK_LOG_FILE = './task.log'    # 任务日志

if __name__ == '__main__':
    # 失败数据补录
    if (os.path.exists(LOG_FILE)==True):
        logfile = open(LOG_FILE, 'r')
        num = 1
        line = logfile.readline()
        while (line != None and line != ''):
            print 'line -> %s' % num
            num += 1
            line = line.replace('\r', '')
            line = line.replace('\n', '')

            if (line != ''):
                result = ReadErrorLine(line)
                if (result != None):
                    dbfile, x, y, z = result
                    GetData(dbfile, x, y, z)

            
            line = logfile.readline()
        logfile.close()
        





    
