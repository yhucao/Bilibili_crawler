import os
import time
import datetime
import json
import re
import threading
import requests
import xlwt

class Crawler(object):
    def __init__(self):
        config_fp = open("./config.json", "r", encoding="utf-8")  #读取配置文件
        self.config_data = json.load(config_fp)
        config_fp.close()
        self.rank_url = self.config_data["page"] #参照配置文件进行选择
        self.base_url = "https://api.bilibili.com/archive_stat/stat?aid="   #视频详细信息的接口
        # self.danmu_url = 'https://api.bilibili.com/x/v2/dm/history?type=1&oid='   #弹幕的接口
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.116 Mobile Safari/537.36",
            "Referer": "https://www.bilibili.com/"
        }                           #排行榜页面所使用的请求头
        try:
            self.cookie = self.config_data["cookie"]        #获取设置的cookie信息
        except Exception as result:
            exit(result)
        self.page_headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36'
                           '(KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'),
            "Cookie":self.cookie
        }                       #获取单个视频信息所使用的请求头
        self.__get_data_from_internet()
        self.__analytical_data()
        self.__detail_analytical()
        self.__video_detail_get()
        # self.__multi_threading()
        self.__save_as_excel()
        if self.config_data["mongodb"]:
            self.__save_to_mongodb()
        '''
        给出相关的网址链接和伪造请求头,读取配置信息，并执行一些函数
        '''
        
    def __get_data_from_internet(self):
        self.resp = requests.get(self.rank_url, headers=self.headers)
        self.text = self.resp.content.decode('utf-8')
        self.page_link_list = re.findall(r'<div class="info">.*?<a href="(.*?)".target=', self.text, re.DOTALL)
        self.video_data_list = []
        self.up_data_list = []
        self.danmu_id_list = []
        for page_link in self.page_link_list:
            time.sleep(0.1)
            print("正在获取来自页面%s的数据" % 'http:'+page_link)
            try:
                response = requests.get(url='http:'+page_link, headers=self.page_headers)
                data = response.content.decode("utf-8")
                video_data = re.findall(r'"videoData":(.*?),"rights":', data, re.DOTALL)
                self.video_data_list.append(video_data[0] + '}')
                up_data = re.findall(r'"upData":(.*?),"pendant":', data, re.DOTALL)
                self.up_data_list.append(up_data[0] + '}')
                danmu_id = re.findall(r'pages.*?cid":(.*?),.page',data,re.DOTALL)
                self.danmu_id_list.append(danmu_id[0])
            except Exception as result:
                print(result)
        self.core_data = list(zip(self.video_data_list, self.up_data_list))

        '''
                从网上获取源数据,并储存为元素为元组的列表
                '''


    def __analytical_data(self):
        self.video_dic_list = []
        self.up_dic_list = []
        for video_one, up_one in self.core_data:
            try:
                video_dic = json.loads(video_one)
                self.video_dic_list.append(video_dic)
                up_dic = json.loads(up_one)
                self.up_dic_list.append(up_dic)
            except Exception as result:
                print(result)
        '''
               对数据做进一步的处理，将列表中的元组拆包，并反序列化成字典，
               并将反序列化的视频信息和up主信息分别加入到列表self.video_dic_list和self.up_dic_list中
               '''
    def __detail_analytical(self):
        self.new_video_data_list = []
        for video_data in self.video_dic_list:
            temp_dic_video = {
                "BV号": video_data['bvid'],
                "aid": video_data['aid'],
                "分类":video_data['tname'],
                "封面图片地址":video_data['pic'],
                "标题":video_data['title'],
                "发布日期":time.strftime('%Y-%m-%d',time.gmtime(video_data['pubdate'])),
                "发布的精准时间":time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(video_data['pubdate'])),
                "视频描述":video_data['desc'],
                "视频时长（秒）":video_data['duration'],
                "视频集数":video_data['videos']
            }
            self.new_video_data_list.append(temp_dic_video)
        '''
        对元素为字典的列表中的数据做细节分析，并存放到新的列表中
        '''

    def __video_detail_get(self):
        index = 0
        for dic in self.new_video_data_list:
            aid = dic["aid"]
            intact_url = self.base_url + str(aid)
            print("正在获取视频{}的详细信息".format(dic["BV号"]))
            time.sleep(0.1)
            resp = requests.get(url=intact_url, headers=self.headers).content.decode("utf-8")
            data_dic = json.loads(resp)
            temp_dic = {
                "播放量":data_dic["data"]["view"],
                "弹幕总量":data_dic["data"]["danmaku"],
                "评论数":data_dic["data"]["reply"],
                "点赞数":data_dic["data"]["favorite"],
                "投币数":data_dic["data"]["coin"],
                "分享数":data_dic["data"]["share"]
            }
            dictMerged = dict(dic, **temp_dic)
            self.new_video_data_list[index] = dictMerged
            index += 1

    def __save_as_excel(self):
        self.workbook = xlwt.Workbook(encoding='utf-8')
        self.worksheet1 = self.workbook.add_sheet('sheet1')  #创建工作表
        i = 0
        for dic in self.new_video_data_list:
            j = 0
            for key in dic:
                self.worksheet1.write(i, j, key)
                j += 1
                self.worksheet1.write(i, j, dic[key])
                j += 1
            i += 2
        self.workbook.save(r'B站视频排行.xls')

        '''
        将数据保存为excel表格
        '''

if __name__ == '__main__':
    print("开始启动爬虫")
    spider = Crawler()
