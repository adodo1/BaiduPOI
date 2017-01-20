#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, urllib, urllib2, json, sqlite3, threading, time, socket, logging, Queue
from threading import Thread

# 百度POI信息采集 根据UID
# 参考:
# http://map.baidu.com/?qt=inf&uid=1d326df167106ca6f82213c4


# 定义全局变量
MAX_THREADS = 30                                    # 最大线程数
GET_URL = 'http://map.baidu.com/?qt=inf&uid={0}'    # POI信息请求地址

mutex = threading.Lock()                            # 锁
socket.setdefaulttimeout(15)                        # 超时时间15秒
success = 0                                         # 已经完成的数量

#reload(sys)
#sys.setdefaultencoding('utf-8')


##########################################################################
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
##########################################################################

    

def GetHtml(url):
    # 下载网页数据 在这里可以处理链接超时 404 等错误
    # 同时这里可以设置代理或构造数据头 页面编码等
    try:
        html = urllib.urlopen(url).read().decode('utf-8')
    except:
        try:
            html = urllib.urlopen(url).read().decode('utf-8')
        except:
            try:
                html = urllib.urlopen(url).read().decode('utf-8')
            except:
                try:
                    html = urllib.urlopen(url).read().decode('utf-8')
                except:
                    try:
                        html = urllib.urlopen(url).read().decode('utf-8')
                    except Exception as ex:
                        return None
    # 解码
    return html



def Run(conn, uid, taskname):
    # 工作线程
    url = GET_URL.format(uid)
    html = GetHtml(url)
    if (html==None):
        # 失败
        logging.error('{0} - {1}'.format(taskname, uid))
    else:
        # 获取成功
        mutex.acquire()
        global success
        success += 1
        cursor = conn.cursor()
        args = (uid, html, int(time.time()))
        cursor.execute('insert into POIS values(?,?,?)', args)
        if (success % 100 == 0):
            logging.info('{0} - {1}'.format(taskname, success))
            conn.commit()
        mutex.release()

def ReadUids(conndata, start, count):
    # 读取指定数量的UID
    sql = 'select id, uid from UIDS where id >= {0} order by id limit {1}'.format(start, count)
    cursor = conndata.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()      # 读取全部结果
    uids = []
    for row in result:
        uid = row[1]
        uids.append(uid)
    return uids

def InitDB(conn):
    # 初始化数据库
    cu = conn.cursor()
    try:
        # 创建POIS表
        cu.execute(
            """create table if not exists POIS(
                   uid varchar(25),     -- UID值
                   context text,        -- json内容
                   time number)         -- 时间戳
            """)
    except: pass


def Init(fname):
    # 初始化日志
    logging.basicConfig(level=logging.DEBUG,
                format=r'%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt=r'%m/%d %H:%M:%S',
                filename=fname,
                filemode='a')
    # 定义一个StreamHandler，将INFO级别或更高的日志信息打印到标准错误，并将其添加到当前的日志处理对象#
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


if __name__=='__main__':
    #
    start = 1           # 任务开始偏移量 包含该项目 从1开始
    count = 1000       # 总任务数量 每次任务数量不能太多否则会 OOM 的

    print sys.getdefaultencoding()
    html = urllib2.urlopen('http://map.baidu.com/?qt=inf&uid=01524377f818704b047ce883').read()
    print html

    #html = html.decode('utf8')
    #print html

    '''
    if (len(sys.argv) == 3):
        start = int(sys.argv[1])
        count = int(sys.argv[2])
    
    taskname = 'task_{0}_{1}'.format(start, count)
    dbpath = './output/'
    dbfile = '{0}{1}.db'.format(dbpath, taskname)
    logfile = '{0}{1}.log'.format(dbpath, taskname)
    Init(logfile)
    # 创建数据库 sqlite不能工作在多线程里 否则会出问题 但是可以在线程里加锁解决
    if (os.path.exists(dbpath)==False):
        os.makedirs(dbpath)

    
    conn = sqlite3.connect(dbfile, check_same_thread = False)
    InitDB(conn)

    # 连接UIDS数据库
    datadb = './data/UIDS.db'
    conndata = sqlite3.connect(datadb, check_same_thread = False)
    
    # 读取足够数量的UID
    uids = ReadUids(conndata, start, count)
    conndata.close()
    
    # 设置多线程数量
    wp = WorkerPool(MAX_THREADS)                 # 线程数量

    for uid in uids:
        wp.add_job(Run, conn, uid, taskname)

    wp.wait_for_complete()              # 等待完成
    conn.commit()
    conn.close()

    print 'OK'
    '''

    
    
    
