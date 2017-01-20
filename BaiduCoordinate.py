#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, urllib, json, sqlite3, threading, time, socket, logging, Queue
from threading import Thread

# 百度纠偏数据库生成
# 参考:
# http://developer.baidu.com/map/index.php?title=webapi/guide/changeposition
# http://map.sogou.com/api/documentation/javascript/api2.5/interface_translate.html#late_intro < 百度坐标转火星墨卡托坐标


# 定义全局变量
MAX_THREADS = 20                        # 最大线程数
APP_KEY = 'M034idvG2MFv63UnDBvCHWq9'    # 百度的APPKEY
FROM = 1                                # 源坐标类型
TO = 5                                  # 目的坐标类型
SCALE = 1000000                         # 经纬度取整 乘以1000000
GET_URL = 'http://api.map.baidu.com/geoconv/v1/?coords={0}&from={1}&to={2}&ak={3}'

mutex = threading.Lock()                # 锁
socket.setdefaulttimeout(5)             # 超时时间5秒


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

def GetHtml(url):
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
                return None

def GetBDCoord(strcoords):
    # 获取百度坐标
    url = GET_URL.format(strcoords, FROM, TO, APP_KEY)
    html = GetHtml(url)
    if (html == None):
        logging.error(strcoords + '\n')
        return
    # 其他
    decodejson = json.loads(html)
    status = int(decodejson['status'])
    if (status != 0):
        logging.error('status:{0} {1}'.format(status, strcoords))
        return
    oldcoords = StrToCoords(strcoords)
    newcoords = JsonToCoords(decodejson)

    for index in range(len(oldcoords)):
        oldlng, oldlat = oldcoords[index]
        newlng, newlat = newcoords[index]
        offsetlng = (newlng - oldlng) * SCALE
        offsetlat = (newlat - oldlat) * SCALE
        print '{0}  {1}  {2}  {3}'.format(oldlng, oldlat, offsetlng, offsetlat)
    
    

def InitDB(conn):
    # 初始化数据库
    pass

def Init():
    logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='coordinate.log',
                filemode='a')
    #定义一个StreamHandler，将INFO级别或更高的日志信息打印到标准错误，并将其添加到当前的日志处理对象#
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def CoordsToStr(coords):
    # 坐标数组转字符串
    strcoords = None
    for coord in coords:
        lng, lat = coord
        if (strcoords == None): strcoords = '{0},{1}'.format(lng, lat)
        else: strcoords += ';{0},{1}'.format(lng, lat)
    return strcoords

def StrToCoords(strcoords):
    # 字符串组转坐标组
    coords = []
    for item in strcoords.split(';'):
        lng, lat = item.split(',')
        coords.append((float(lng), float(lat)))
    return coords

def JsonToCoords(decodejson):
    # 从JSON字符串解析坐标值
    coords = []
    for item in decodejson['result']:
        lng = float(item['x'])
        lat = float(item['y'])
        coords.append((lng, lat))
    return coords

if __name__=='__main__':
    #
    xmin = 73.5         # 左上角 经度lng 单位度
    xmax = 74.0         # 右下角 经度lng 单位度
    ymin = 18.0         # 左上角 纬度lat 单位度
    ymax = 19.0         # 右下角 纬度lat 单位度
    start = 1           # 任务开始偏移量 包含该项目 从1开始
    count = 10          # 总任务数量 每次任务数量不能太多否则会 OOM 的
    precision = 0.01    # 数据精度 0.1 0.01 0.001

    
    
    Init()
    dbpath = './output/'
    dbfile = './output/[{0},{1},{2},{3}_{4}][{5}].db'.format(xmin, xmax, ymin, ymax, start, precision)
    # 创建数据库 sqlite不能工作在多线程里 否则会出问题 但是可以在线程里加锁解决
    if (os.path.exists(dbpath)==False):
        os.makedirs(dbpath)
    conn = sqlite3.connect(dbfile, check_same_thread = False)
    InitDB(conn)

    # 
    wp = WorkerPool(MAX_THREADS)                 # 线程数量
    
    #
    coords = []
    num = 0
    lng = xmin
    lat = ymin
    while (lng < xmax):
        if (count <= 0): break          # 执行完足够数量的任务
        lat = ymin
        while (lat < ymax):
            if (count <= 0): break      # 执行完足够数量的任务
            num += 1
            if (num < start):
                lat += precision
                continue                # 跳过指定数量
            count -= 1

            # ====================================
            # 处理逻辑在这里
            coords.append((lng, lat))
            # 每隔100个提交一次任务
            if (len(coords) == 100):
                strcoords = CoordsToStr(coords)
                wp.add_job(GetBDCoord, strcoords)
                coords = []
            # ====================================
            
            lat += precision
        lng += precision

    # ====================================
    # 提交剩余任务
    if (len(coords) > 0):
        strcoords = CoordsToStr(coords)
        wp.add_job(GetBDCoord, strcoords)
        coords = []
    # ====================================

    wp.wait_for_complete()              # 等待完成
    
    print 'OK'
    
    
