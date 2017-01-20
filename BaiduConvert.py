#!/usr/bin/env python
# encoding: utf-8

import os, sys, math, urllib, json

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


PI              = 3.14159265358979324
EARTH_RADIUS    = 6378245.0
EE              = 0.00669342162296594323
X_PI            = 3.14159265358979324 * 3000.0 / 180.0


def OutOfChina(lat, lng):
    # 坐标是否在中国外
    if (lng < 72.004 or lng > 137.8347):
        return True
    if (lat < 0.8293 or lat > 55.8271):
        return True
    return False

def TransformLat(x, y):
    # 纬度转换
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret

def TransformLng(x, y):
    # 经度转换
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret

def GPS2Mars(wglat, wglng):
    # 地球坐标转换为火星坐标
    # wglat WGS纬度
    # wglng WGS经度
    # 返回近似火星坐标系
    if (OutOfChina(wglat, wglng)):
        return wglat, wglng
    dlat = TransformLat(wglng - 105.0, wglat - 35.0)
    dlng = TransformLng(wglng - 105.0, wglat - 35.0)
    radlat = wglat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((EARTH_RADIUS * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (EARTH_RADIUS / sqrtmagic * math.cos(radlat) * PI)
    mglat = wglat + dlat
    mglng = wglng + dlng
    return mglat, mglng

def Mars2GPS(gclat, gclng):
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
        tmplat, tmplng = GPS2Mars(wgslat, wgslng)
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
    
def BD_encrypt(gglat, gglng):
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

def BD_decrypt(bdlat, bdlng):
    # 百度坐标转火星坐标
    x = bdlng - 0.0065
    y = bdlat - 0.006
    z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    gglng = z * math.cos(theta)
    gglat = z * math.sin(theta)
    return gglat, gglng

def BDAPI(lat, lng):
    # 百度官方API接口
    # http://api.map.baidu.com/ag/coord/convert?from=2&to=4&mode=1&x=116.3786889372559,116.38632786853032,116.39534009082035,116.40624058825688,116.41413701159672&y=39.90762965106183,39.90795884517671,39.907432133833574,39.90789300648029,39.90795884517671
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
    

if __name__=='__main__':
    lng, lat = 109.43, 24.305833333333332
    print u'经纬度  : {0}, {1}'.format(lng, lat)
    gglat, gglng = GPS2Mars(lat, lng)
    print u'计算火星坐标: {0}, {1}'.format(gglng, gglat)
    bdlat, bdlng = BD_encrypt(gglat, gglng)
    print u'计算百度坐标: {0}, {1}'.format(bdlng, bdlat)
    ddlat, ddlng = BDAPI(lat, lng)
    print u'正确百度坐标: {0}, {1}'.format(ddlng, ddlat)
    print u'-----------------'
    #
    hhlat, hhlng = BD_decrypt(bdlat, bdlng)
    print u'反算火星坐标: {0}, {1}'.format(hhlng, hhlat)
    gplat, gplng = Mars2GPS(hhlat, hhlng)
    print u'反算经纬坐标: {0}, {1}'.format(gplng, gplat)


        
