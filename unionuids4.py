#!/usr/bin/env python
# encoding: utf-8

import os, sys, sqlite3, fnmatch, json, math



# 百度墨卡托坐标
# 参考:
# http://blog.163.com/ruby_study/blog/static/238680065201489103958382/
# https://gist.github.com/aisk/3735854
# http://www.4wei.cn/archives/1002008
# https://gist.github.com/chao-he/7747495

# 百度坐标转换
# GPS坐标 -> 火星坐标 -> 百度坐标
# 关键字 GCJ-02 BD-09 wgtochina_lb 二分法
# GPS坐标 -> 火星坐标 (单向不可逆 算法wgtochina_lb 逆向求解可用二分法)
# http://blog.csdn.net/xiaobaismiley/article/details/37576303
# https://on4wp7.codeplex.com/SourceControl/changeset/view/21483#353936
# http://blog.csdn.net/giswens/article/list/4
# http://www.gpsspg.com/maps.htm
# https://github.com/scateu/PyWGS84ToGCJ02 < 这里有计算距离的
# https://code.google.com/p/my-android-util/source/browse/trunk/src/com/android/util/location/Converter.java?spec=svn2&r=2 < wgtochina_lb 算法
# http://www.oschina.net/code/snippet_260395_39205


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
##################################################################################################

PI              = 3.14159265358979324
EARTH_RADIUS    = 6378245.0
EE              = 0.00669342162296594323
X_PI            = 3.14159265358979324 * 3000.0 / 180.0

class BaiduConvert:
    # 百度坐标转换
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
        ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * PI) + 320 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
        return ret

    def TransformLng(self, x, y):
        # 经度转换
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
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
        radlat = wglat / 180.0 * PI
        magic = math.sin(radlat)
        magic = 1 - EE * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat = (dlat * 180.0) / ((EARTH_RADIUS * (1 - EE)) / (magic * sqrtmagic) * PI)
        dlng = (dlng * 180.0) / (EARTH_RADIUS / sqrtmagic * math.cos(radlat) * PI)
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
        
        pass
        
    def BD_encrypt(self, gglat, gglng):
        # 火星坐标转换为百度坐标
        # gglat 火星纬度
        # gglng 火星经度
        x = gglng
        y = gglat
        z = math.sqrt(x*x + y*y) + 0.00002 * math.sin(y * X_PI)
        theta = math.atan2(y, x) + 0.000003 * math.cos(x * X_PI)
        bdlng = z * math.cos(theta) + 0.0065
        bdlat = z * math.sin(theta) + 0.006
        return bdlat, bdlng

    def BD_decrypt(self, bdlat, bdlng):
        # 百度坐标转火星坐标
        x = bdlng - 0.0065
        y = bdlat - 0.006
        z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y * X_PI)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
        gglng = z * math.cos(theta)
        gglat = z * math.sin(theta)
        return gglat, gglng

    def BDAPI(self, lat, lng):
        # 百度官方API接口
        # http://api.map.baidu.com/ag/coord/convert?from=2&to=4&mode=1&x=116.3786889372559,116.38632786853032&y=39.90762965106183,39.90795884517671
        ifrom = 1
        ito = 5
        ak = 'M034idvG2MFv63UnDBvCHWq9'
        coords = '{0},{1}'.format(lng, lat)
        url = 'http://api.map.baidu.com/geoconv/v1/?from={0}&to={1}&ak={2}&coords={3}'.format(ifrom, ito, ak, coords)
        html = urllib.urlopen(url).read().decode('utf-8')
        decodejson = json.loads(html)
        bdlng = decodejson['result'][0]['x']
        bdlat = decodejson['result'][0]['y']
        return bdlat, bdlng

# 有效城市列表
CITYS = {
        131:u'北京市',289:u'上海市',257:u'广州市',132:u'重庆市',340:u'深圳市',75:u'成都市',224:u'苏州市',315:u'南京市',
        317:u'无锡市',161:u'南通市',348:u'常州市',316:u'徐州市',223:u'盐城市',346:u'扬州市',276:u'泰州市',160:u'镇江市',
        162:u'淮安市',277:u'宿迁市',347:u'连云港市',236:u'青岛市',288:u'济南市',287:u'潍坊市',326:u'烟台市',234:u'临沂市',
        354:u'淄博市',286:u'济宁市',175:u'威海市',372:u'德州市',174:u'东营市',325:u'泰安市',353:u'菏泽市',366:u'聊城市',
        172:u'枣庄市',235:u'滨州市',173:u'日照市',124:u'莱芜市',179:u'杭州市',180:u'宁波市',178:u'温州市',333:u'金华市',
        293:u'绍兴市',244:u'台州市',334:u'嘉兴市',294:u'湖州市',243:u'衢州市',292:u'丽水市',245:u'舟山市',138:u'佛山市',
        119:u'东莞市',187:u'中山市',302:u'江门市',301:u'惠州市',140:u'珠海市',198:u'湛江市',139:u'茂名市',338:u'肇庆市',
        303:u'汕头市',259:u'揭阳市',197:u'清远市',141:u'梅州市',137:u'韶关市',199:u'阳江市',200:u'河源市',258:u'云浮市',
        201:u'潮州市',339:u'汕尾市',268:u'郑州市',153:u'洛阳市',309:u'南阳市',152:u'新乡市',214:u'信阳市',308:u'周口市',
        267:u'安阳市',155:u'许昌市',269:u'驻马店市',213:u'平顶山市',154:u'商丘市',211:u'焦作市',210:u'开封市',209:u'濮阳市',
        212:u'三门峡市',344:u'漯河市',215:u'鹤壁市',1277:u'济源市',218:u'武汉市',156:u'襄阳市',270:u'宜昌市',157:u'荆州市',
        271:u'黄冈市',216:u'十堰市',310:u'孝感市',217:u'荆门市',311:u'黄石市',373:u'恩施土家族苗族自治州',362:u'咸宁市',
        371:u'随州市',1713:u'仙桃市',1293:u'潜江市',122:u'鄂州市',2654:u'天门市',2734:u'神农架林区',300:u'福州市',
        134:u'泉州市',194:u'厦门市',255:u'漳州市',193:u'龙岩市',195:u'莆田市',133:u'南平市',192:u'宁德市',254:u'三明市',
        150:u'石家庄市',265:u'唐山市',307:u'保定市',149:u'沧州市',151:u'邯郸市',191:u'廊坊市',266:u'邢台市',264:u'张家口市',
        148:u'秦皇岛市',208:u'衡水市',207:u'承德市',167:u'大连市',58:u'沈阳市',320:u'鞍山市',282:u'丹东市',184:u'抚顺市',
        281:u'营口市',319:u'葫芦岛市',166:u'锦州市',60:u'铁岭市',351:u'辽阳市',280:u'朝阳市',228:u'盘锦市',227:u'本溪市',
        59:u'阜新市',127:u'合肥市',130:u'安庆市',129:u'芜湖市',189:u'滁州市',298:u'六安市',128:u'阜阳市',251:u'巢湖市',
        126:u'蚌埠市',250:u'淮南市',190:u'宣城市',370:u'宿州市',188:u'亳州市',252:u'黄山市',358:u'马鞍山市',253:u'淮北市',
        299:u'池州市',337:u'铜陵市',158:u'长沙市',159:u'衡阳市',222:u'株洲市',219:u'常德市',273:u'邵阳市',220:u'岳阳市',
        313:u'湘潭市',275:u'郴州市',314:u'永州市',363:u'怀化市',272:u'益阳市',221:u'娄底市',274:u'湘西土家族苗族自治州',
        312:u'张家界市',240:u'绵阳市',291:u'南充市',74:u'德阳市',369:u'达州市',79:u'乐山市',186:u'宜宾市',331:u'泸州市',
        330:u'遂宁市',242:u'资阳市',78:u'自贡市',248:u'内江市',80:u'凉山彝族自治州',329:u'广元市',241:u'广安市',239:u'巴中市',
        77:u'眉山市',81:u'攀枝花市',76:u'雅安市',185:u'阿坝藏族羌族自治州',73:u'甘孜藏族自治州',163:u'南昌市',365:u'赣州市',
        364:u'上饶市',349:u'九江市',318:u'吉安市',278:u'宜春市',226:u'抚州市',225:u'景德镇市',164:u'新余市',350:u'萍乡市',
        279:u'鹰潭市',261:u'南宁市',142:u'桂林市',305:u'柳州市',361:u'玉林市',304:u'梧州市',203:u'百色市',341:u'贵港市',
        143:u'河池市',145:u'钦州市',144:u'崇左市',295:u'北海市',202:u'来宾市',260:u'贺州市',204:u'防城港市',233:u'西安市',
        323:u'咸阳市',171:u'宝鸡市',231:u'榆林市',170:u'渭南市',352:u'汉中市',284:u'延安市',324:u'安康市',285:u'商洛市',
        232:u'铜川市',176:u'太原市',368:u'临汾市',328:u'运城市',355:u'大同市',238:u'晋中市',356:u'长治市',327:u'吕梁市',
        290:u'晋城市',367:u'忻州市',357:u'阳泉市',237:u'朔州市',104:u'昆明市',249:u'曲靖市',106:u'玉溪市',111:u'大理白族自治州',
        107:u'红河哈尼族彝族自治州',105:u'楚雄彝族自治州',336:u'昭通市',177:u'文山壮族苗族自治州',112:u'保山市',114:u'丽江市',
        108:u'普洱市',109:u'西双版纳傣族自治州',116:u'德宏傣族景颇族自治州',110:u'临沧市',113:u'怒江傈僳族自治州',
        115:u'迪庆藏族自治州',48:u'哈尔滨市',50:u'大庆市',41:u'齐齐哈尔市',49:u'牡丹江市',42:u'佳木斯市',44:u'绥化市',
        46:u'鸡西市',39:u'黑河市',45:u'双鸭山市',40:u'伊春市',43:u'鹤岗市',38:u'大兴安岭地区',47:u'七台河市',53:u'长春市',
        55:u'吉林市',54:u'延边朝鲜族自治州',56:u'四平市',165:u'通化市',52:u'松原市',57:u'白山市',183:u'辽源市',51:u'白城市',
        321:u'呼和浩特市',229:u'包头市',283:u'鄂尔多斯市',297:u'赤峰市',61:u'呼伦贝尔市',169:u'巴彦淖尔市',64:u'通辽市',
        168:u'乌兰察布市',63:u'锡林郭勒盟',123:u'乌海市',62:u'兴安盟',230:u'阿拉善盟',332:u'天津市',92:u'乌鲁木齐市',
        90:u'伊犁哈萨克自治州',86:u'巴音郭楞蒙古自治州',93:u'昌吉回族自治州',83:u'喀什地区',85:u'阿克苏地区',94:u'塔城地区',
        91:u'哈密地区',95:u'克拉玛依市',96:u'阿勒泰地区',89:u'吐鲁番地区',770:u'石河子市',88:u'博尔塔拉蒙古自治州',
        82:u'和田地区',84:u'克孜勒苏柯尔克孜自治州',731:u'阿拉尔市',789:u'五家渠市',792:u'图木舒克市',146:u'贵阳市',
        262:u'遵义市',342:u'黔东南苗族侗族自治州',306:u'黔南布依族苗族自治州',205:u'铜仁地区',263:u'安顺市',206:u'毕节地区',
        147:u'六盘水市',343:u'黔西南布依族苗族自治州',36:u'兰州市',196:u'天水市',37:u'酒泉市',135:u'庆阳市',256:u'陇南市',
        359:u'平凉市',35:u'白银市',136:u'定西市',117:u'张掖市',118:u'武威市',182:u'临夏回族自治州',34:u'金昌市',247:u'甘南藏族自治州',
        33:u'嘉峪关市',125:u'海口市',121:u'三亚市',1215:u'儋州市',2758:u'文昌市',2358:u'琼海市',2757:u'澄迈县',1216:u'万宁市',
        2634:u'东方市',1214:u'定安县',1643:u'陵水黎族自治县',1642:u'昌江黎族自治县',2032:u'乐东黎族自治县',1641:u'屯昌县',
        2359:u'白沙黎族自治县',1217:u'保亭黎族苗族自治县',2033:u'临高县',2031:u'琼中黎族苗族自治县',1644:u'五指山市',
        1218:u'西沙群岛',2912:u'香港特别行政区',360:u'银川市',335:u'石嘴山市',322:u'吴忠市',246:u'固原市',181:u'中卫市',
        66:u'西宁市',69:u'海东地区',65:u'海西蒙古族藏族自治州',68:u'海南藏族自治州',67:u'海北藏族自治州',70:u'黄南藏族自治州',
        71:u'玉树藏族自治州',72:u'果洛藏族自治州',100:u'拉萨市',102:u'日喀则地区',98:u'林芝地区',97:u'山南地区',99:u'昌都地区',
        101:u'那曲地区',103:u'阿里地区',2911:u'澳门特别行政区'
        }





def GetDatas(context):
    # 解析数据
    try:
        result = []
        decodejson = json.loads(context)
        content = decodejson.get('content', None)
        if (content == None): return []
        for item in content:
            uid = item['uid']
            mx = float(item['diPointX']) / 100.0    # 百度墨卡托X
            my = float(item['diPointY']) / 100.0    # 百度墨卡托Y
            name = item['name']
            addr = item['addr']
            area = item['area']
            cla = str(item['cla'])
            alias = item.get('alias', None)
            tel = item.get('tel', None)

            aliasstr = ''
            if (alias != None):
                aliasstr = ';'.join(alias)
                    

            # 百度墨卡托 => 百度经纬度
            baiduMC = BaiduMercator()
            bdlng, bdlat = baiduMC.MercatorToLngLat(mx, my)
            # 百度经纬度 => 火星坐标 => GPS坐标
            baiduConvert = BaiduConvert()
            hhlat, hhlng = baiduConvert.BD_decrypt(bdlat, bdlng)
            lat, lng = baiduConvert.Mars2GPS(hhlat, hhlng)
            
            result.append({
                           'uid':uid,
                           'name':name,
                           'alias':aliasstr,
                           'x':0,
                           'y':0,
                           'zoom':0,
                           'lat':lat,
                           'lng':lng,
                           'bdlat':bdlat,
                           'bdlng':bdlng,
                           'tel':tel,
                           'cla':cla,
                           'addr':addr,
                           'state':None,
                           'city':None,
                           'town':None,
                           'street':None,
                           'code':None,
                           'area':area,
                           'description':None,
                           'time':None
                         })
        return result
    except Exception as ex:
        print ex
        return []


def UnionUIDS(conn, connUnion):
    # 合并
    cu = conn.cursor()
    cuUnion = connUnion.cursor()
    sql = 'select cityid, context, time from POIDATA'
    cu.execute(sql)
    record = cu.fetchall()
    for row in record:
        # 
        cityid = row[0]
        context = row[1]
        time = row[2]
        # 
        datas = GetDatas(context)

        for data in datas:
            # 插入数据
            if (len(data)==0): continue
            data['code'] = cityid
            data['time'] = time
            data['city'] = CITYS.get(cityid, None)
            
            args = (data['uid'], data['name'], data['alias'], data['x'], data['y'], data['zoom'], data['lat'], data['lng'],
                    data['bdlat'], data['bdlng'], data['tel'], data['cla'], data['addr'], data['state'], data['city'],
                    data['town'], data['street'], data['code'], data['area'], data['description'], data['time'])
            cuUnion.execute('insert into POIS values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', args)
    

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
        """create table if not exists POIS(
                    uid varchar(25),        -- UID值
                    name text,              -- 名称
                    alias text,             -- 别名
                    x number,               -- 百度瓦片X索引
                    y number,               -- 百度瓦片Y索引
                    zoom number,            -- 百度瓦片缩放级别
                    lat number,             -- 经度
                    lng number,             -- 纬度
                    bdlat number,           -- 百度经度
                    bdlng number,           -- 百度纬度
                    tel varchar(100),       -- 电话
                    cla varchar(200),       -- 分类 标记
                    addr text,              -- 地址
                    state varchar(30),      -- 省
                    city varchar(50),       -- 市
                    town varchar(80),       -- 县 镇
                    street varchar(120),    -- 街道
                    code number,            -- 城市代码
                    area number,            -- 区域代码
                    description text,       -- 描述
                    time number)            -- 时间戳
        """)

if __name__ == '__main__':
    # 合并所有搜索到的POI信息
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
        print '{0}/{1}: {2}'.format(num, len(files), name)
        connUnion.commit()
        
    print '{0}/{1}: {2}'.format(num, len(files), '')

    connUnion.commit()
    connUnion.close()
    print u'OK'

