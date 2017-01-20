#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, urllib, urllib2, time
import ctypes, socket, threading, json, Queue, sqlite3
from threading import Thread

# 定义全局变量
mutex = threading.Lock()        # 锁
socket.setdefaulttimeout(5)     # 超时时间5秒

# 1. ok 经纬度坐标转栅格 X Y
# 2. ok 计算矩形范围包含多少个小方格
# 3. ok 下载栅格里的POI点的UID
# 4. ok 获取UID里的信息
# 5. ok 信息保存到数据库中
# 6. 保存一个工程进度文件 可以中断和继续下载 保存过程数据 按照文件夹存放
# 7. ok 保存日志文件
# 8. 多线程处理 可以显示进度
# 9. 能够更换IP或使用代理

# 参考 GMap.Net & 百度兴趣点提取工具
# 涉及到的坐标系: 经纬度 > 整张瓦片的坐标 > 瓦片的小方格坐标

# http://online1.map.bdimg.com/js/?qt=vQuest&styles=pl&x=11311&y=3488&z=16&v=085&fn=MPC_Mgr.getPoiDataCbk
# http://online1.map.bdimg.com/js/?qt=vQuest&styles=pl&x=11311&y=3488&z=16&v=068&fn=MPC_Mgr.getPoiDataCbk
# http://map.baidu.com/?qt=inf&uid=1d326df167106ca6f82213c4
# http://api.map.baidu.com/place/v2/eventdetail?uid=1fcb5ffeafa825f18d77273e&output=json&ak=6cb3f458a482fcd009414370808ea219 获取信息Good http://developer.baidu.com/map/index.php?title=webapi/guide/webservice-placeapi
# http://api.map.baidu.com/place/v2/detail?uid=1fcb5ffeafa825f18d77273e&ak=M034idvG2MFv63UnDBvCHWq9&output=json&scope=2
# http://map.baidu.com/detail?qt=ninf&uid=1fcb5ffeafa825f18d77273e


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

class GMap:
    # 地图辅助类
    def __init__(self):
        self.MinLatitude = -85.05112878     # 最小纬度
        self.MaxLatitude = 85.05112878      # 最大纬度
        self.MinLongitude = -180            # 最小经度
        self.MaxLongitude = 180             # 最大经度
        self.TileSizeWidth = 256            # 瓦片宽度
        self.TileSizeHeight = 256           # 瓦片高度

    def GetTileMatrixMinXY(self, zoom):
        return 0, 0

    def GetTileMatrixMaxXY(self, zoom):
        xy = (1 << zoom)
        return xy - 1, xy - 1

    def GetTileMatrixSizePixel(self, zoom):
        sMin = self.GetTileMatrixMinXY(zoom)
        sMax = self.GetTileMatrixMaxXY(zoom)
        width = (sMax[0] - sMin[0] + 1) * self.TileSizeWidth
        height = (sMax[1] - sMin[1] + 1) * self.TileSizeHeight
        return width, height

    def FromCoordinateToPixel(self, lat, lng, zoom):
        # 通过经纬度获取瓦片"像素点"  经纬度 > 整张瓦片的像素点
        # lat: 纬度
        # lng: 经度
        # zoom: 缩放级别 3~19

        # 核心算法
        # x=(y + 180) / 360
        # y = 0.5 - log((1 + sin(x * 3.1415926 / 180)) / (1 - sin(x * 3.1415926 / 180))) / (4 * π)
        # y = (1 - (log(tan(x * 3.1415926 / 180) + sec(x * 3.1415926 / 180)) / π)) / 2
        lat = min(max(lat, self.MinLatitude), self.MaxLatitude)
        lng = min(max(lng, self.MinLongitude), self.MaxLongitude)

        x = (lng + 180) / 360
        y = 0.5 - math.log((1 + math.sin(lat * math.pi / 180)) / (1 - math.sin(lat * math.pi / 180))) / (4 * math.pi)

        mapSizeX, mapSizeY = self.GetTileMatrixSizePixel(zoom)
        pixelX = min(max(x * mapSizeX + 0.5, 0), mapSizeX - 1)
        pixelY = min(max(y * mapSizeY + 0.5, 0), mapSizeY - 1)
        
        return int(pixelX), int(pixelY)

    def FromCoordinateToTileXY(self, lat, lng, zoom):
        # 通过经纬度获取瓦片的"索引"  经纬度 > 瓦片块坐标
        # lat: 纬度
        # lng: 经度
        # zoom: 缩放级别 3~19
        pixelX, pixelY = self.FromCoordinateToPixel(lat, lng, zoom)
        tileX, tileY = self.FromPixelToTileXY(pixelX, pixelY)
        return tileX, tileY

    def FromPixelToTileXY(self, pixelX, pixelY):
        # 整张瓦片的像素坐标转瓦片块的索引 像素坐标 > 瓦片块坐标
        tileX = int(pixelX / self.TileSizeWidth)
        tileY = int(pixelY / self.TileSizeHeight)
        return tileX, tileY

    def GetAreaTileList(self, min_lat, min_lng, max_lat, max_lng, zoom):
        # 计算范围里所有小方格
        # min_lat, min_lng, max_lat, max_lat: 最小纬度 最小经度 最大纬度 最大经度
        # / top left bottom right
        # / y轴: 纬度 从上到下 90度 ~ -90度
        # / x轴: 经度 从左到右 -180度 ~ 180度
        # zoom: 缩放级别 3~19
        left, top = self.FromCoordinateToTileXY(min_lat, min_lng, zoom)
        right, bottom = self.FromCoordinateToTileXY(max_lat, max_lng, zoom)

        result = []     #结果
        for x in range(left, right+1):
            for y in range(top, bottom+1):
                result.append([x, y])
        
        return result

    def GetBaiduTileXY(self, tileX, tileY, zoom):
        # 百度的瓦片计算方法 X轴向左偏移 Y轴上下颠倒并且偏移
        # 百度瓦片是有做过偏移，左上角的索引值并不是 (0, 0) 所以需要做偏移
        # tileX: 瓦片的X索引 第几块瓦片 左上角为(x:0, y:0)点 右下角为(pow(4, zoom-1), pow(4, zoom-1))
        # tileY: 瓦片的Y索引 第几块瓦片 左上角为(x:0, y:0)点 右下角为(pow(4, zoom-1), pow(4, zoom-1))
        offsetX = math.pow(2, zoom - 1)
        offsetY = offsetX - 1

        numX = tileX - offsetX
        numY = -tileY + offsetY

        baiduTileX = str(int(numX)).replace('-', 'M')
        baiduTileY = str(int(numY)).replace('-', 'M')
        return baiduTileX, baiduTileY

    def GetBaiduAreaTileList(self, min_lat, min_lng, max_lat, max_lng, zoom):
        tiles = self.GetAreaTileList(min_lat, min_lng, max_lat, max_lng, zoom)
        baiduTiles = []
        for tile in tiles:
            baiduTiles.append(self.GetBaiduTileXY(tile[0], tile[1], zoom))
        return baiduTiles

##########################################################################

class Spider:
    # 爬虫
    def __init__(self, conn):
        self.POI_URL = 'http://online{0}.map.bdimg.com/js/?qt=vQuest&styles=pl&x={1}&y={2}&z={3}&v=088&fn=MPC_Mgr.getPoiDataCbk'      # 获取POI列表
        self.INFO_URL = 'http://map.baidu.com/?qt=inf&uid={0}'                                                                      # 根据POI的UID得到具体信息
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
        except: return None
        
    def DownloadUidList(self, x, y, zoom):
        # 下载POI列表UID
        url = self.POI_URL.format(self.num % 10, x, y, zoom)

        # 读取数据
        html = self.GetHtml(url)
        if (html==None):
            # 失败
            error = 'Get poi {%s, %s, %s} list error' % (x, y, zoom)
            ShowInfo(error, 'e', True)
            return []
        else:
            # 写入文件 并解析返回uids
            self.num += 1
            if (self.num % 1000 == 0):
                ShowInfo('Downloaded poi list %s' % self.num)
                mutex.acquire()
                self.conn.commit()
                mutex.release()

            uids = self.GetUids(html)
            if (uids==None):
                error = error = 'Decode json {%s, %s, %s} error' % (x, y, zoom)
                #ShowInfo(error, 'e', True)
                return None
            else:
                # 插入数据库 注意加锁 否则会有问题
                mutex.acquire()
                cursor = self.conn.cursor()
                args = (x, y, zoom, html, int(time.time()))
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
        if (uids == None): return
        for uid in uids:
            self.uidList.append([uid, x, y, zoom])
            
    # 解析POI =============================================================
    def GetPois(self, html):
        # 解析出POI信息
        pass

    def DownloadPoiList(self, uid, x, y, zoom):
        # 下载POI列表
        url = self.INFO_URL.format(uid)
        # 读取数据
        html = self.GetHtml(url)
        if (html==None):
            # 失败
            error = 'Get info {%s, %s, %s, %s} list error' % (uid, x, y, zoom)
            ShowInfo(error, 'e', True)
        else:
            # 插入数据库
            self.num += 1
            if (self.num % 1000 == 0):
                ShowInfo('Downloaded poi list %s' % self.num)
                mutex.acquire()
                self.conn.commit()
                mutex.release()
                
            # 插入数据库 注意加锁 否则会有问题
            mutex.acquire()
            cursor = self.conn.cursor()
            args = (uid, html, int(time.time()))
            cursor.execute('insert into POIS values(?,?,?)', args)
            #self.conn.commit()
            mutex.release()

    # 多线程控制 =============================================================
    def Work(self, maxThreads, baiduTiles, zoom):
        # 爬取数据
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
            ShowInfo('共获得UID {0} 个'.format(len(self.uidList)))
            
        if (True):
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

# -----------------------颜色代码开始-------------------------------------
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12
 
# 字体颜色定义 ,关键在于颜色编码，由2位十六进制组成，分别取0~f，前一位指的是背景色，后一位指的是字体色
# 由于该函数的限制，应该是只有这16种，可以前景色与背景色组合。也可以几种颜色通过或运算组合，组合后还是在这16种颜色中
 
# Windows CMD命令行 字体颜色定义 text colors
FOREGROUND_BLACK = 0x00         # black.
FOREGROUND_DARKBLUE = 0x01      # dark blue.
FOREGROUND_DARKGREEN = 0x02     # dark green.
FOREGROUND_DARKSKYBLUE = 0x03   # dark skyblue.
FOREGROUND_DARKRED = 0x04       # dark red.
FOREGROUND_DARKPINK = 0x05      # dark pink.
FOREGROUND_DARKYELLOW = 0x06    # dark yellow.
FOREGROUND_DARKWHITE = 0x07     # dark white.
FOREGROUND_DARKGRAY = 0x08      # dark gray.
FOREGROUND_BLUE = 0x09          # blue.
FOREGROUND_GREEN = 0x0a         # green.
FOREGROUND_SKYBLUE = 0x0b       # skyblue.
FOREGROUND_RED = 0x0c           # red.
FOREGROUND_PINK = 0x0d          # pink.
FOREGROUND_YELLOW = 0x0e        # yellow.
FOREGROUND_WHITE = 0x0f         # white.

# Windows CMD命令行 背景颜色定义 background colors
BACKGROUND_BLUE = 0x10          # dark blue.
BACKGROUND_GREEN = 0x20         # dark green.
BACKGROUND_DARKSKYBLUE = 0x30   # dark skyblue.
BACKGROUND_DARKRED = 0x40       # dark red.
BACKGROUND_DARKPINK = 0x50      # dark pink.
BACKGROUND_DARKYELLOW = 0x60    # dark yellow.
BACKGROUND_DARKWHITE = 0x70     # dark white.
BACKGROUND_DARKGRAY = 0x80      # dark gray.
BACKGROUND_BLUE = 0x90          # blue.
BACKGROUND_GREEN = 0xa0         # green.
BACKGROUND_SKYBLUE = 0xb0       # skyblue.
BACKGROUND_RED = 0xc0           # red.
BACKGROUND_PINK = 0xd0          # pink.
BACKGROUND_YELLOW = 0xe0        # yellow.
BACKGROUND_WHITE = 0xf0         # white.

# get handle
std_out_handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
 
def set_cmd_text_color(color, handle=std_out_handle):
    Bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)
    return Bool
 
#reset white
def resetColor():
    set_cmd_text_color(FOREGROUND_DARKWHITE)
# -----------------------颜色代码结束-------------------------------------

LOG_FILE = './baidupoi.log'

def ShowInfo(text, level='i', save=False):
    # 输出信息
    # text 信息内容
    # level 信息类别 info, warning, error 
    # save 是否保存到日志里
    # color 文本颜色 info白色, warning绿色, error红色

    mutex.acquire()
    # 打印时间
    if (level==None or len(level)==0): level='i'
    stime = time.strftime(r'%m/%d %H:%M:%S')
    print stime,
    # 切换颜色
    if (level[0] == 'i'): set_cmd_text_color(FOREGROUND_DARKWHITE)
    elif (level[0] == 'w'): set_cmd_text_color(FOREGROUND_DARKGREEN)
    elif (level[0] == 'e'): set_cmd_text_color(FOREGROUND_DARKRED)
    else: set_cmd_text_color(FOREGROUND_DARKWHITE)
    # 输出信息
    print '[{0}]:'.format(level[0]),
    print text
    # 重置颜色
    resetColor()
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
            """create table POIDATA(
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
            """create table UIDS(
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
            """create table POIS(
                   uid varchar(25),     -- UID值
                   context text,        -- json内容
                   time number)         -- 时间戳
            """)
    except: pass
    
    

if __name__ == '__main__':
    
    minLat = 14.0906272740390       # 左上角纬度
    minLng = 67.4704742431641       # 左上角经度
    maxLat = 13.8567472346067       # 右下角纬度
    maxLng = 67.9058074951172       # 右下角经度
    zoom = 19                       # 缩放比例
    maxThreads = 50                 # 线程数量
    proxyList = []                  # 代理列表
    dbFile = './output/data.db'     # 数据库文件

    # 初始化
    path, name = os.path.split(dbFile)
    if (os.path.exists(path)==False):
        os.makedirs(path)
    # 创建数据库 sqlite不能工作在多线程里 否则会出问题 但是可以在线程里加锁解决
    conn = sqlite3.connect(dbFile, check_same_thread = False)
    InitDB(conn)

    # 创建2个对象
    gmap = GMap()
    spider = Spider(conn)

    
    # 8.9284870626655, -36.38671875, -10.8333059836425, -19.16015625, 5
    # 9.4490618268814188, -106.171875, -20.961439614096832, -72.94921875, 3
    # 13.9715383683264, 67.7056583762169, 13.9711817765103, 67.7062457799912 19     < 小范围4个方块
    # 13.9749663067391, 67.7014446258545, 13.9687090443488, 67.7095985412598 19     < 中等范围143个小方块
    # 14.0906272740390, 67.4704742431641, 13.8567472346067, 67.9058074951172 19     < 较大范围223520个小方块
    baiduTiles = gmap.GetBaiduAreaTileList(minLat, minLng, maxLat, maxLng, zoom)

    baiduTiles = []
    for x in range(94700, 95480):
        for y in range(21316, 21867):
            baiduTiles.append((x, y))
    
    ShowInfo('共找到小方块 %s 个' % len(baiduTiles), 'i', True)
    spider.Work(maxThreads, baiduTiles, zoom)
    
    ShowInfo('OK')
    
