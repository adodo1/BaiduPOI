#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, json, re, requests

_EXT_CHARS = ["=", ".", "-", "*"]
_CODES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
_MAX_DELTA = 1 << 23

class BaiduGeo:
    # 百度路径解析
    def char2num(self, ch):
        # BASE64转10进制
        return _CODES.index(ch)

    def decode_6byte(self, e, t):
        # 解析6BYTE
        o = 0
        a = 0
        n = 0
        for i in range(0, 6):
            n = self.char2num(e[i + 1 : i + 2])
            if (n < 0) : return -1 - i
            o += n << 6 * i
            n = self.char2num(e[i + 7 : i + 8])
            if (n < 0): return -7 - i
            a += n << 6 * i
        t.append(o)
        t.append(a)
        return 0

    def decode_4byte(self, e, t):
        # 解析4BYTE
        o = len(t)
        if (o < 2): return -1
        a = 0
        n = 0
        i = 0
        for r in range(0, 4):
            i = self.char2num(e[r : r+1])
            if (i < 0): return -1 - r
            a += i << 6 * r
            i = self.char2num(e[r + 4 : r+ 5])
            if (i < 0): return -5 - r
            n += i << 6 * r
        
        if (a > _MAX_DELTA): a = _MAX_DELTA - a
        if (n > _MAX_DELTA): n = _MAX_DELTA - n
        t.append(t[o - 2] + a)
        t.append(t[o - 1] + n)
        return 0
        

    def decode_type(self, ch):
        # 解析类型
        if (ch == _EXT_CHARS[1]): return 'GEO_TYPE_POINT'
        elif (ch == _EXT_CHARS[2]): return 'GEO_TYPE_LINE'
        elif (ch == _EXT_CHARS[3]): return 'GEO_TYPE_AREA'
        else: return 'GEO_TYPE_UNKNOW'

    def decode_geo_diff(self, txt):
        # 解析具体的GEO字符串
        geo_type = self.decode_type(txt[0])
        subtxt = txt[1:]
        index = 0
        size = len(subtxt)
        ppp = []
        geo = []
        rarr = 0

        while (size > index):
            if (subtxt[index: index+1] == _EXT_CHARS[0]):
                if (13 > size - index): return 0
                rarr = self.decode_6byte(subtxt[index : index + 13], ppp)
                if (rarr < 0): return 0
                index += 13
            elif (subtxt[index] == ';'):
                geo.append(ppp[0:])
                ppp = []
                index += 1
            else:
                if (8 > size - index): return 0
                rarr = self.decode_4byte(subtxt[index : index + 8], ppp)
                if (rarr < 0): return 0
                index += 8
        # 结果分组
        # 原始结果 [[1217774785, 277399466, 1217772452, 277398723, 1217757002, 277393778, 1217741770, 277388976, 1217738545, 277388480]]
        # 分组结果 [[1217774785, 277399466], [1217772452, 277398723], [1217757002, 277393778], [1217741770, 277388976], [1217738545, 277388480]]
        newgeo = []
        for item in range(0, len(geo)):
            xy = []
            for point in range(0, len(geo[item])):
                geo[item][point] /= 100.0
                xy.append(geo[item][point])
                if (len(xy) == 2):
                    newgeo.append(xy)
                    xy = []
            # 默认只为双数单数直接舍掉

        return {'type':geo_type, 'geo':newgeo}
        

    def parse2Geo(self, txt, t):
        # 解析路径
        if (t < 0.25): t = 0
        elif (0.25 < t and t < 1): t = 1
        elif (t > 32): t = 32

        txts = txt.split('|')
        if (len(txts) == 1):
            g = self.decode_geo_diff(txts[0])
            return {'type': g['type'], 'bound':'', 'points':g['goe']}

        if (len(txts) > 1):
            n = txt.split(';.=')
            bounds = []
            paths = []
            p = len(n)
            for d in range(0, p):
                chrs = n[d]
                if (p > 1):
                    if (d == 0): chrs += ';'
                    if (d > 0 and p -1 > d): chrs = '.=' + chrs + ';'
                    if (d == p - 1): chrs = '.=' + chrs
                # 拆分字符串 前两个是边界 第三个是路径
                f = chrs.split('|')
                bound1 = self.decode_geo_diff(f[0])
                bound2 = self.decode_geo_diff(f[1])
                bounds.append(bound1['geo'])
                bounds.append(bound2['geo'])
                # 关键路径
                path = self.decode_geo_diff(f[2])
                paths.append(path['geo'])
                
                # 原代码的意思是将得到的坐标分组 两个两个一组
                pass
                
        # 简化一下 只取paths的结果 不要边框
        return paths

class BaiduNva:
    # 只解析了URL里部分参数 其他参数以后解析 比如翻页的参数
    # http://map.baidu.com/?newmap=1&qt=nav&c=305&sn=1$$$$12183065,2773415$$我的位置$$0$$$$&en=0$$4ea03fc1b9cc600b6d476049$$12177373.16,2773805.09$$中铁二十五局集团第六工程有限公司$$0$$$$&version=4
    def QRoute(self, city, slat, slng, elat, elng):
        # 查询路径
        params = self.BuildParameters(city, slat, slng, elat, elng) # 构造参数列表
        html = self.GetHtml('http://map.baidu.com/', params)        # 查询
        self.EvalJson(html)                                         # 解析查询结果
    
    def BuildParameters(self, city, slat, slng, elat, elng):
        # 构造参数
        # 计算百度墨卡托坐标
        baiduMercator = BaiduMercator()
        baiduCoor = BaiduCoor()

        s_malat, s_malng = baiduCoor.GPS2Mars(slat, slng)           # WGS转火星
        s_bdlat, s_bdlng = baiduCoor.BD_encrypt(s_malat, s_malng)   # 火星转百度
        s_x, s_y = baiduMercator.LngLatToMercator(s_bdlng, s_bdlat) # 百度转墨卡托

        e_malat, e_malng = baiduCoor.GPS2Mars(elat, elng)           # WGS转火星
        e_bdlat, e_bdlng = baiduCoor.BD_encrypt(e_malat, e_malng)   # 火星转百度
        e_x, e_y = baiduMercator.LngLatToMercator(e_bdlng, e_bdlat) # 百度转墨卡托
        
        params = {}
        params['newmap'] = 1
        params['qt'] = 'nav'
        params['c'] = city
        params['sn'] = '1$$$${0},{1}$$$$0$$$$'.format(s_x, s_y)
        params['en'] = '0$$$${0},{1}$$$$0$$$$'.format(e_x, e_y)
        params['version'] = 4
        return params

    def GetHtml(self, url, params):
        # Get请求网页
        response = requests.get(url, params=params, stream=True)
        #data = response.raw.read()
        data = response.text
        return data

    def EvalJson(self, html):
        # 解析百度的结果
        data = json.loads(html)
        self.PrintRoute(data)

        oid = 0
        baiduGeo = BaiduGeo()
        records = []
        for step in data['content']['steps']:
            record = step
            record['shape'] = baiduGeo.parse2Geo(step['path'], 0)
            if (record.has_key('path')): del record['path']             # 删掉path字段否则出错
            record['oid'] = oid                                         # 添加一个oid字段
            oid += 1
            records.append(record)
            
        esriJson = self.WriteEsriJson(records, 3857)
        
        # 保存结果 百度墨卡托坐标
        f = open('baidu_nav_bd.json', 'w')
        f.write(json.dumps(esriJson))
        f.close()

        # 坐标转换 百度墨卡托转经纬度
        baiduMercator = BaiduMercator()
        baiduCoor = BaiduCoor()
        #bdlng, bdlat = baiduMercator.MercatorToLngLat(0, 0)     # 百度墨卡托转百度经纬度
        #gglat, gglng = baiduCoor.BD_decrypt(bdlat, bdlng)       # 百度经纬度转火星经纬度
        #wglat, wglng = baiduCoor.Mars2GPS(gglat, gglng)         # 火星经纬度转WGS84

        for feature in esriJson['features']:
            newpaths = []
            for path in feature['geometry']['paths']:
                newpath = []
                for point in path:
                    x = point[0]
                    y = point[1]
                    bdlng, bdlat = baiduMercator.MercatorToLngLat(x, y)     # 百度墨卡托转百度经纬度
                    gglat, gglng = baiduCoor.BD_decrypt(bdlat, bdlng)       # 百度经纬度转火星经纬度
                    wglat, wglng = baiduCoor.Mars2GPS(gglat, gglng)         # 火星经纬度转WGS84
                    newx, newy = wglng, wglat
                    newpath.append([newx, newy])
                newpaths.append(newpath)
            # 赋新值
            feature['geometry']['paths'] = newpaths
        # 坐标系
        esriJson['spatialReference']['wkid'] = 4326
        
        # 保存结果 WGS84坐标
        f = open('baidu_nav_wgs.json', 'w')
        f.write(json.dumps(esriJson))
        f.close()

    def PrintRoute(self, data):
        # 打印路线方案
        print u'共有方案: {0} 条'.format(len(data['content']['routes']))
        print u'共有路径: {0} 段'.format(len(data['content']['steps']))
        index = 1
        roads = []
        for route in data['content']['routes']:
            index += 1
            road = []
            for step in route['legs'][0]['stepis']:
                s = step['s']
                n = step['n']
                for r in range(s, s+n):
                    road.append(r)
            roads.append(road)
            
        print u'方案详情: ' + str(roads)
        print '---------------------------------'
        
    def WriteEsriJson(self, records, wkid):
        # 保存数据 规定SHAPE字段保存图形
        # 例子:
        #records = [
        #    {'name': 'a', 'id': 1, 'shape': [[[1,1], [2,2], [3,5]]]},
        #    {'name': 'b', 'id': 2, 'shape': [[[1.5,2], [2,6], [6,5]], [[3,1],[2,7],[4,2]]]}
        #          ]

        if (len(records) == 0): return {}
        # 构造字段
        fields = []
        for field in records[0]:
            # 设置字段全部为文本
            if (field.lower() == 'shape'): continue
            fields.append({'name': field, 'type': 'esriFieldTypeString', 'alias': field, 'length': 200})
        # 填写记录
        features = []
        for record in records:
            # 构造
            attributes = {}
            paths = []
            feature = {'attributes': attributes,
                       'geometry': {'paths': paths}
                      }
            # 填写具体信息
            for attr in record:
                if (attr.lower() == 'shape'):
                    # 图形 先分段 段里再到点集合
                    paths.extend(record[attr])
                else:
                    # 普通属性
                    value = record[attr]
                    if (isinstance(value, unicode)): value = value.encode('utf8')
                    attributes[attr] = str(value)
            features.append(feature)
            
        data = {
            'geometryType': 'esriGeometryPolyline',
            'spatialReference': {'wkid': wkid},
            'fields': fields,
            'features': features
               }

        return data
        


################################################################################################################
################################################################################################################
################################################################################################################
# 百度坐标转换代码开始
################################################################################################################
################################################################################################################
################################################################################################################
class BaiduCoor:
    # 百度坐标转换
    PI              = 3.14159265358979324
    EARTH_RADIUS    = 6378245.0
    EE              = 0.00669342162296594323
    X_PI            = 3.14159265358979324 * 3000.0 / 180.0

    def OutOfChina(self, lat, lng):
        # 坐标是否在中国外
        if (lng < 72.004 or lng > 137.8347):
            return True
        if (lat < 0.8293 or lat > 55.8271):
            return True
        return False

    def TransformLat(self, x, y):
        # 纬度转换
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * self.PI) + 20.0 * math.sin(2.0 * x * self.PI)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * self.PI) + 40.0 * math.sin(y / 3.0 * self.PI)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * self.PI) + 320 * math.sin(y * self.PI / 30.0)) * 2.0 / 3.0
        return ret

    def TransformLng(self, x, y):
        # 经度转换
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * self.PI) + 20.0 * math.sin(2.0 * x * self.PI)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * self.PI) + 40.0 * math.sin(x / 3.0 * self.PI)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * self.PI) + 300.0 * math.sin(x / 30.0 * self.PI)) * 2.0 / 3.0
        return ret

    def GPS2Mars(self, wglat, wglng):
        # 地球坐标转换为火星坐标
        # wglat WGS纬度
        # wglng WGS经度
        # 返回近似火星坐标系
        if (self.OutOfChina(wglat, wglng)):
            return wglat, wglng
        dlat = self.TransformLat(wglng - 105.0, wglat - 35.0)
        dlng = self.TransformLng(wglng - 105.0, wglat - 35.0)
        radlat = wglat / 180.0 * self.PI
        magic = math.sin(radlat)
        magic = 1 - self.EE * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat = (dlat * 180.0) / ((self.EARTH_RADIUS * (1 - self.EE)) / (magic * sqrtmagic) * self.PI)
        dlng = (dlng * 180.0) / (self.EARTH_RADIUS / sqrtmagic * math.cos(radlat) * self.PI)
        mglat = wglat + dlat
        mglng = wglng + dlng
        return mglat, mglng

    def Mars2GPS(self, gclat, gclng):
        # 采用二分法 火星坐标反算地球坐标
        # gclat 火星坐标纬度
        # gclng 火星坐标经度
        initDelta = 0.01
        threshold = 0.000000001
        dlat = initDelta
        dlng = initDelta
        mlat = gclat - dlat
        mlng = gclng - dlng
        plat = gclat + dlat
        plng = gclng + dlng
        wgslat = 0
        wgslng = 0
        i = 0
        while (True):
            wgslat = (mlat + plat) / 2.0
            wgslng = (mlng + plng) / 2.0
            tmplat, tmplng = self.GPS2Mars(wgslat, wgslng)
            dlat = tmplat - gclat
            dlng = tmplng - gclng

            if ((abs(dlat)<threshold) and (abs(dlng)<threshold)):
                break
            if (dlat > 0): plat = wgslat
            else: mlat = wgslat
            if (dlng > 0): plng = wgslng
            else: mlng = wgslng

            i += 1
            if (i>10000): break
        return wgslat, wgslng

        
    def BD_encrypt(self, gglat, gglng):
        # 火星坐标转换为百度坐标
        # gglat 火星纬度
        # gglng 火星经度
        x = gglng
        y = gglat
        z = math.sqrt(x*x + y*y) + 0.00002 * math.sin(y * self.X_PI)
        theta = math.atan2(y, x) + 0.000003 * math.cos(x * self.X_PI)
        bdlng = z * math.cos(theta) + 0.0065
        bdlat = z * math.sin(theta) + 0.006
        return bdlat, bdlng

    def BD_decrypt(self, bdlat, bdlng):
        # 百度坐标转火星坐标
        x = bdlng - 0.0065
        y = bdlat - 0.006
        z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y * self.X_PI)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * self.X_PI)
        gglng = z * math.cos(theta)
        gglat = z * math.sin(theta)
        return gglat, gglng
    
class BaiduMercator:
    # 百度墨卡托坐标
    EARTHRADIUS = 6370996.81
    MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
    LLBAND = [75, 60, 45, 30, 15, 0]
    MC2LL = [
        [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331, 200.9824383106796, -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
        [ - 7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289, 96.32687599759846, -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86], 
        [ - 3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616, 59.74293618442277, 7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
        [ - 1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591, 40.31678527705744, 0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
        [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062, 23.10934304144901, -0.00023663490511, -0.6321817810242, -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4],
        [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8, 7.47137025468032, -0.00000353937994, -0.02145144861037, -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5]
    ]
    LL2MC = [
        [ - 0.0015702102444, 111320.7020616939, 1704480524535203, -10338987376042340, 26112667856603880, -35149669176653700, 26595700718403920, -10725012454188240, 1800819912950474, 82.5],
        [0.0008277824516172526, 111320.7020463578, 647795574.6671607, -4082003173.641316, 10774905663.51142, -15171875531.51559, 12053065338.62167, -5124939663.577472, 913311935.9512032, 67.5],
        [0.00337398766765, 111320.7020202162, 4481351.045890365, -23393751.19931662, 79682215.47186455, -115964993.2797253, 97236711.15602145, -43661946.33752821, 8477230.501135234, 52.5],
        [0.00220636496208, 111320.7020209128, 51751.86112841131, 3796837.749470245, 992013.7397791013, -1221952.21711287, 1340652.697009075, -620943.6990984312, 144416.9293806241, 37.5],
        [ - 0.0003441963504368392, 111320.7020576856, 278.2353980772752, 2485758.690035394, 6070.750963243378, 54821.18345352118, 9540.606633304236, -2710.55326746645, 1405.483844121726, 22.5],
        [ - 0.0003218135878613132, 111320.7020701615, 0.00369383431289, 823725.6402795718, 0.46104986909093, 2351.343141331292, 1.58060784298199, 8.77738589078284, 0.37238884252424, 7.45]
    ]


    def PixelToPoint(sefl, point, zoom, center, bounds):
        # 像素到坐标
        zoomUnits = self.GetZoomUnits(zoom)
        mercatorx = center.lng + zoomUnits * (point.x - bounds.width / 2)
        mercatory = center.lat - zoomUnits * (point.y - bounds.height / 2)
        return self.MercatorToLngLat(mercatorx, mercatory)

    def PointToPixel(self, coord, zoom, center, bounds):
        # 坐标到像素
        point = self.LngLatToMercator(coord)
        units = self.GetZoomUnits(zoom)
        x = round((point.lng - center.lng) / units + bounds.width / 2)
        y = round((center.lat - point.lat) / units + bounds.height / 2)
        return BDPoint(x, y)

    def GetZoomUnits(self, zoom):
        # 获取分辨率
        return pow(2, (18-zoom))



##################################################################################################
    def MercatorToPixel(self, x, y, zoom):
        # 墨卡托坐标转像素坐标
        pixelX = math.floor(x * math.pow(2, zoom - 18))
        pixelY = math.floor(y * math.pow(2, zoom - 18))
        return pixelX, pixelY

    def PixelToTile(self, pixelX, pixelY):
        # 像素坐标转瓦片XY 图块坐标
        tileX = int(math.floor(pixelX / 256))
        tileY = int(math.floor(pixelY / 256))
        return tileX, tileY
    
    def MercatorToLngLat(self, x, y):
        # 墨卡托坐标转经纬度
        # x: X坐标 (经度)
        # y: Y坐标 (纬度)
        # return: lng, lat 经度, 纬度
        mc = None
        absx = abs(x)
        absy = abs(y)
        for i in range(0, len(self.MCBAND)):
            if (absy >= self.MCBAND[i]):
                mc = self.MC2LL[i]
                break
        lng, lat = self.Convertor(x, y, mc)
        lng = round(lng, 6)
        lat = round(lat, 6)
        return lng, lat

    def LngLatToMercator(self, lng, lat):
        # 经纬度转墨卡托坐标
        # lng: 经度
        # lat: 纬度
        # return: X, Y 墨卡托平面坐标XY
        mc = None
        lng = self.GetLoop(lng, -180, 180)
        lat = self.GetRange(lat, -74, 74)

        for i in range(0, len(self.LLBAND)):
            if lat > self.LLBAND[i]:
                mc = self.LL2MC[i]
                break
        if mc == None:
            for i in range(len(self.LLBAND)-1, -1, -1):
                if (lat <= -self.LLBAND[i]):
                    mc =  self.LL2MC[i]
                    break
        x, y = self.Convertor(lng, lat, mc)
        x = round(x, 2)
        y = round(y, 2)
        return x, y

    def GetLoop(self, lng, a, b):
        # 经度范围
        while (lng > b):
            lng -= b - a
        while (lng < a):
            lng += b - a
        return lng

    def GetRange(self, lat, a, b):
        # 纬度范围
        lat = max(lat, a)
        lat = min(lat, b)
        return lat

    def Convertor(self, xlng, ylat, mc):
        # 数据转换
        # xlng:     X 或者 经度
        # ylat:     Y 或者 纬度
        # mc:       转换对照表
        # return:   经纬度 或 XY
        newxlng = mc[0] + mc[1] * abs(xlng)
        c = abs(ylat) / mc[9]
        newylat = mc[2] + mc[3] * c + mc[4] * c * c + mc[5] * c * c * c + mc[6] * c * c * c * c + mc[7] * c * c * c * c * c + mc[8] * c * c * c * c * c * c
        if(xlng < 0): newxlng *= -1
        if(ylat < 0): newylat *= -1
        return newxlng, newylat




################################################################################################################
################################################################################################################
################################################################################################################
# 百度坐标转换代码结束
################################################################################################################
################################################################################################################
################################################################################################################


    
    
                    

    


if __name__ == '__main__':
    #
    print '[==DoDo==]'
    print 'Baidu eval nav.'
    print 'Encode: %s' %  sys.getdefaultencoding()

    # 参考:
    # http://webmap0.map.bdstatic.com/wolfman/static/common/pkg/init-pkg_d0fbac8.js
    # https://github.com/liuhui244671426/dx/blob/b79ea459cb9847735ff6a124edaed4066fd19e31/template/2013-03-30/eis_y_car/map/bpack.js
    # 关键字:
    # decode_geo_diff parse2Geo
    

    
    #print '.=BTclIBqeMiQA;'[1:]

    #print decode_6byte('=fifmIBvt7hQA', [])
    #print decode_4byte("BTAgRZBg", [1218308502, 277371708, 1218307397, 277365510])
    # t = [1218302746, 277342654, 1218303965, 277346668]
    #ee = '-=sWcnIBSH8hQAwDBgFJAAn5BgsbAAmYBgpfAAevCgobBAowAgKaAA8nAgiUAAD7Ag9bAAdkAg9MAAS5Ag9IAAcFBgCFAA3FDgSPAgWHCg9KAg9WCgOLAg53CgiPAgboDgIUAgVRAgOAAg5BBgmGAg3NAgFCAg/FFgOhAg08BgZLAgnrCg/PAgyUAgOCAg7UBg9IAgyUAgOCAgh+BglLAgtrDgGVAggKBg/GAgTTCg+NAgwwCgjOAgYkAgcEAgkDBgBFAg2NAgJCAgMODg+SAgZfCgISAg3ICg8NAg;'
    #ee = '-=aMdnIB+m+hQADTAAu+AAvuAASLDA2NAAz8AAeWAAW9BAKMAg2BAA;'
    #ee = '.=sWcnIBJ47hQA;|.=WmenIB8sFiQA;|-=WmenIB8sFiQARRAg2gBgBTAgRZBguuAgRLDgm8AgOgDgOFAAJPAg;'
    #ee = '.=VacnIBKp0hQA;|.=7bcnIBJ47hQA;|-=7bcnIBJ47hQAlBAg5VCgEAAAMGBgFAAAYVBgBAAAERAgFAAARXBgDAAAH1Ag;'
    #print decode_geo_diff(ee)

    #ee = '.=VacnIBKp0hQA;|.=7bcnIBJ47hQA;|-=7bcnIBJ47hQAlBAg5VCgEAAAMGBgFAAAYVBgBAAAERAgFAAARXBgDAAAH1Ag;'
    #ee = '.=fifmIBvt7hQA;|.=sWcnIB6MAiQA;|-=sWcnIBSH8hQAwDBgFJAAn5BgsbAAmYBgpfAAevCgobBAowAgKaAA8nAgiUAAD7Ag9bAAdkAg9MAAS5Ag9IAAcFBgCFAA3FDgSPAgWHCg9KAg9WCgOLAg53CgiPAgboDgIUAgVRAgOAAg5BBgmGAg3NAgFCAg/FFgOhAg08BgZLAgnrCg/PAgyUAgOCAg7UBg9IAgyUAgOCAgh+BglLAgtrDgGVAggKBg/GAgTTCg+NAgwwCgjOAgYkAgcEAgkDBgBFAg2NAgJCAgMODg+SAgZfCgISAg3ICg8NAg;'
    #ee = '.=6/wlIB0K7hQA;|.=bLamIB1aFiQA;|-=bLamIB0K7hQAqIAgvBAAMFAgzBAAyuAgNQAAMJEgAYBA7gAgxKAAZKAgmDAAyuAgUOAA76AgyTAAdrBg9jAAQyAgKQAAZMCg3sAA7gAgyKAAerBg6lAAhWAgMHAA3nAgeOAA4BBgSbAAubAgGHAAyUAgbDAAlPAgoBAAlpAgEDAAaMCgBaAAIMAglDAAWqFgnJBAEtAg3GAAuBAg4BAAZKAgvBAAmPAgpBAA7GAgyBAAr8AgaKAAF/EgB0AAoDBgSMAAdYBgmTAAAaAgVFAAyPBg3RAA6BBgROAAmKBgEQAAmPAgmDAA9gAgQFAAd+AgRQAA;'
    #parse2Geo(ee, 0)

    # 百度路径解析
    #path = '.=tcTlIB8yJiQA;|.=BTclIBqeMiQA;|-=BTclIBqeMiQAdkAgnLAgaxDgRNBgAuDgCLBgZyAgwHAg;'
    #bdGeo = BaiduGeo()
    #print bdGeo.parse2Geo(path, 0)

    # ESRI JSON 导出测试
    #records = [
    #    {'name': 'a', 'id': 1, 'shape': [[[12177747.85, 2773994.66], [12177724.52, 2773987.23], [12177570.02, 2773937.78], [12177417.7, 2773889.76], [12177385.45, 2773884.8]]]},
    #    {'name': 'b', 'id': 2, 'shape': [[[1.5,2], [2,6], [6,5]], [[3,1],[2,7],[4,2]]]}
    #          ]
    #print json.dumps(writeEsriJson(records, 3857))
    
    bdNav = BaiduNva()
    #params = bdNav.BuildParameters(305, 0,0,0,0)
    #html = bdNav.GetHtml('http://map.baidu.com/', params)
    #bdNav.EvalJson(html)
    #39°54′27″,东经116°23′17″
    slat, slng = 24.305676, 109.430193          # 起始坐标 WGS84坐标
    elat, elng = 39.907500, 116.388055          # 结束坐标 WGS84坐标
    city = 305                                  # 城市代码 在 有效城市代码.txt 查找
    bdNav.QRoute(city, slat, slng, elat, elng)
    print 'OK.'
    
