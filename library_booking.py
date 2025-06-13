import json
import http.client
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import io
import urllib.parse
import qrcode
import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from cookie import (
    getCookieWithCASLogin,
    CookieManager, 
    getCookieWithDirectLogin,
    AccountManager
)
import random

def get_lt_value(url):
    """从CAS登录页面获取lt参数值"""
    try:
        response = requests.get(url, verify=False)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            lt_input = soup.find('input', {'id': 'lt'})
            if lt_input:
                return lt_input.get('value')
    except Exception as e:
        print(f"获取lt值时发生错误: {e}")
        return None

class LibraryBooking:
    def __init__(self):
        self.base_url = "libbooking.gzhu.edu.cn"
        # 随机UA列表
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
        ]
        # 在初始化时就设置随机UA
        random_ua = self.get_random_ua()
        self.headers = {
            "User-Agent": random_ua,
            "Accept": "application/json, text/plain, */*",
            "Sec-Fetch-Site": "same-origin",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Sec-Fetch-Mode": "cors",
            "Content-Type": "application/json;charset=utf-8",
            "Sec-Fetch-Dest": "empty"
        }
        self.cookie = None
        self.year = str(datetime.now().year)  # 获取当前年份
        self.rooms_info = {}  # 存储房间信息的字典
        self.cookie_manager = CookieManager()
        self.username = None  # 存储当前用户名
        self.password = None  # 存储当前密码
        self.debug = True  # 调试模式开关
        self.app_acc_no = None  # 存储用户的appAccNo值，用于预约
        self.debug_print(f"已设置随机User-Agent: {random_ua}")
    
    def get_random_ua(self):
        """获取随机User-Agent"""
        return random.choice(self.user_agents)
        
    def set_debug_mode(self, enabled=True):
        """设置调试模式开关"""
        self.debug = enabled
        if enabled:
            print("\033[36m[DEBUG] 调试模式已开启\033[0m")
        else:
            print("\033[36m[DEBUG] 调试模式已关闭\033[0m")
        return self.debug

    def debug_print(self, message):
        """调试信息打印函数"""
        if self.debug:
            print(f"\033[36m[DEBUG] {message}\033[0m")

    def initialize_cookie(self, username=None, password=None, force_refresh=False):
        """初始化cookie，优先检查cookie有效性，无效时才重新登录"""
        # 如果没有强制刷新，先尝试从cookie管理器加载cookie
        if not force_refresh:
            cookie_data = self.cookie_manager.load_cookie()
            if cookie_data:
                # 设置初始cookie、用户名和密码
                self.cookie = cookie_data.get("cookie")
                self.username = cookie_data.get("username") or username
                self.password = cookie_data.get("password") or password
                
                if self.cookie:
                    self.headers["Cookie"] = self.cookie
                    self.debug_print(f"已从文件加载cookie")
                    
                    # 检查当前cookie是否有效
                    self.debug_print("检查cookie有效性...")
                    try:
                        # 尝试获取预约列表
                        today = datetime.now()
                        begin_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                        end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
                        
                        # 构建请求路径和参数
                        params = {
                            "beginDate": begin_date,
                            "endDate": end_date,
                            "needStatus": "6",
                            "page": "1",
                            "pageNum": "50",
                            "orderKey": "gmt_create",
                            "orderModel": "desc"
                        }
                        
                        # 使用相同的URL和参数方式
                        check_url = "http://libbooking.gzhu.edu.cn/ic-web/reserve/resvInfo"
                        check_response = requests.get(check_url, headers=self.headers, params=params, verify=False)
                        
                        # 解析响应
                        if check_response.status_code == 200:
                            result = check_response.json()
                            if result.get("code") == 0:
                                print("当前cookie有效，无需重新登录")
                                
                                # 从响应中获取appAccNo值
                                if "data" in result and len(result["data"]) > 0:
                                    first_reservation = result["data"][0]
                                    if "appAccNo" in first_reservation:
                                        self.app_acc_no = first_reservation["appAccNo"]
                                        self.debug_print(f"已获取appAccNo: {self.app_acc_no}")
                                
                                return True
                            else:
                                print(f"cookie已失效：{result.get('message', '未知错误')}")
                        else:
                            print(f"检查cookie状态失败，状态码：{check_response.status_code}")
                    except Exception as e:
                        print(f"验证cookie时出错：{str(e)}")
                    
                    print("需要重新登录...")

        # 设置用户名和密码，如果未传入则使用保存的值或请求用户输入
        if not username and self.username:
            username = self.username
            print(f"使用已保存的账号: {username}")
        if not password and self.password:
            password = self.password
            print("使用已保存的密码")
        
        # 如果还是没有用户名密码，提示用户输入
        if not username:
            username = input("请输入学号: ")
        if not password:
            password = input("请输入密码: ")
        
        # 需要登录的情况
        if username and password:
            self.debug_print(f"正在使用直接登录方式，用户名: {username}")
            
            # 尝试直接登录获取cookie
            try:
                cookie = getCookieWithDirectLogin(username, password)
                if cookie:
                    self.cookie = cookie
                    self.headers["Cookie"] = cookie
                    self.username = username
                    self.password = password
                    self.debug_print("登录成功，cookie已更新")
                    
                    # 获取用户appAccNo值
                    self.get_app_acc_no()
                    
                    # 保存cookie到文件
                    self.cookie_manager.save_cookie(cookie, username, password)
                    self.debug_print("cookie已保存到文件")
                    return True
                else:
                    print("直接登录失败，尝试备选登录方式...")
                    # 调用浏览器模拟登录 - 简化try-except结构
                    login_url = "http://libbooking.gzhu.edu.cn"
                    cookie = getCookieWithCASLogin(login_url, username, password)
                    if cookie:
                        self.cookie = cookie
                        self.headers["Cookie"] = cookie
                        self.username = username
                        self.password = password
                        self.debug_print("备选登录成功，cookie已更新")
                        
                        # 获取用户appAccNo值
                        self.get_app_acc_no()
                        
                        # 保存cookie到文件
                        self.cookie_manager.save_cookie(cookie, username, password)
                        self.debug_print("cookie已保存到文件")
                        return True
                    else:
                        self.debug_print("备选登录方式未能获取有效cookie")
            except Exception as e:
                self.debug_print(f"获取cookie过程出错: {e}")
                import traceback
                traceback.print_exc()
        
        print("\033[31m无法获取有效的cookie\033[0m")
        return False

    def get_person_appAccNo(self):
        """从用户信息API获取appAccNo"""
        try:
            self.debug_print("尝试从userInfo API获取用户ID")
            # 确保使用正确的URL
            url = "http://libbooking.gzhu.edu.cn/ic-web/auth/userInfo"
            
            self.debug_print(f"请求用户信息URL: {url}")
            
            # 发送请求 - 使用requests库而不是session
            response = requests.get(url, headers=self.headers, verify=False)
            
            self.debug_print(f"userInfo API响应状态码: {response.status_code}")
            self.debug_print(f"userInfo API响应内容: {response.text}...")
            
            if response.status_code == 200:
                data = response.json()
                # 兼容大小写的code字段
                code = data.get("code") or data.get("CODE")
                if (code == 0 or code == "0") and "data" in data:
                    app_acc_no = data["data"].get("accNo")
                    if app_acc_no:
                        self.app_acc_no = app_acc_no
                        self.debug_print(f"成功获取用户ID: {app_acc_no}")
                        return app_acc_no
                    else:
                        self.debug_print("用户信息中没有accNo字段")
                else:
                    # 兼容大小写的message字段
                    message = data.get("message") or data.get("MESSAGE", "未知错误")
                    self.debug_print(f"API返回错误: {message}")
            else:
                self.debug_print(f"获取用户信息失败，状态码: {response.status_code}")
            
            return None
        except Exception as e:
            self.debug_print(f"获取用户ID时发生异常: {str(e)}")
            import traceback
            self.debug_print(f"异常详情: {traceback.format_exc()}")
            return None

    def get_app_acc_no(self):
        """获取用户的appAccNo，首先尝试userInfo接口，然后尝试从预约列表中获取"""
        # 先尝试从userInfo接口获取
        app_acc_no = self.get_person_appAccNo()
        if app_acc_no:
            self.debug_print(f"从userInfo接口获取到appAccNo: {app_acc_no}")
            return app_acc_no
            
        # 如果失败，再尝试从预约列表获取
        try:
            self.debug_print("尝试从预约列表获取用户appAccNo...")
            
            # 计算查询日期范围
            today = datetime.now()
            begin_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            
            # 构建请求参数
            params = {
                "beginDate": begin_date,
                "endDate": end_date,
                "needStatus": "6",
                "page": "1",
                "pageNum": "50",
                "orderKey": "gmt_create",
                "orderModel": "desc"
            }
            
            # 发送请求获取预约列表
            check_url = "http://libbooking.gzhu.edu.cn/ic-web/reserve/resvInfo"
            response = requests.get(check_url, headers=self.headers, params=params, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0 or result.get("CODE") == "0":
                    # 从响应中获取appAccNo
                    if "data" in result and len(result["data"]) > 0:
                        first_reservation = result["data"][0]
                        if "appAccNo" in first_reservation:
                            self.app_acc_no = first_reservation["appAccNo"]
                            self.debug_print(f"成功获取appAccNo: {self.app_acc_no}")
                            return self.app_acc_no
                        else:
                            self.debug_print("在预约记录中未找到appAccNo字段")
                    else:
                        self.debug_print("无预约记录，无法获取appAccNo")
                else:
                    self.debug_print(f"获取预约列表失败: {result.get('message', result.get('MESSAGE', ''))}")
            else:
                self.debug_print(f"请求失败，状态码: {response.status_code}")
        
        except Exception as e:
            self.debug_print(f"获取appAccNo过程出错: {str(e)}")
            import traceback
            self.debug_print(f"异常详情: {traceback.format_exc()}")
        
        self.debug_print("无法获取appAccNo，请联系开发者")
        return None

    def refresh_cookie_if_needed(self, target_time=None, force_refresh=False):
        """如果cookie即将过期或在预约前，刷新cookie
        
        Args:
            target_time: 目标预约时间（可选）
            force_refresh: 是否强制刷新cookie
        """
        # 如果强制刷新，则直接获取新cookie
        if force_refresh:
            return self.initialize_cookie(self.username, self.password, force_refresh=True)
            
        cookie_data = self.cookie_manager.load_cookie()
        
        # 检查cookie是否即将过期
        if not cookie_data or self.cookie_manager.is_cookie_expired(cookie_data):
            return self.initialize_cookie(self.username, self.password, force_refresh=True)
        
        # 如果指定了目标时间，检查是否需要在预约前刷新
        if target_time:
            # 解析目标时间
            target_parts = target_time.split(":")
            target_hour = int(target_parts[0])
            target_minute = int(target_parts[1])
            
            # 计算目标时间
            now = datetime.now()
            target_datetime = datetime(now.year, now.month, now.day, target_hour, target_minute)
            
            # 如果目标时间已过，设置为明天
            if target_datetime < now:
                target_datetime = target_datetime + timedelta(days=1)
            
            # 计算距离目标时间的分钟数
            minutes_to_target = (target_datetime - now).total_seconds() / 60
            
            # 如果距离预约时间小于等于10分钟，刷新cookie
            if minutes_to_target <= 10:
                print("\n距离预约时间不到10分钟，正在刷新cookie以确保预约成功...")
                return self.initialize_cookie(self.username, self.password, force_refresh=True)
        
        return True

    def get_rooms_info(self):
        """获取所有房间信息"""
        try:
            request_url = "https://libbooking.gzhu.edu.cn/ic-web/seatMenu"
            self.debug_print(f"发送GET请求: {request_url}")
            self.debug_print(f"请求头: {json.dumps(self.headers, indent=2)}")
            
            # 使用requests库发送请求
            response = requests.get(request_url, headers=self.headers, verify=False)
            
            # 解析JSON响应
            data = response.json()
            
            if self.debug:
                self.debug_print(f"响应状态码: {response.status_code}")
                self.debug_print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
            
            if data["code"] == 0:
                rooms_info = {}
                
                def extract_rooms(node):
                    """递归提取房间信息"""
                    # 如果是大学城校区，处理其子节点
                    if node.get("name") == "大学城校区":
                        for building in node.get("children", []):  # 遍历楼层
                            for room in building.get("children", []):  # 遍历房间
                                if "children" not in room:  # 确保是最终的房间节点
                                    room_name = room["name"]
                                    # 处理特殊房间号 - 走廊区域
                                    if ("走廊" in room_name and "区" in room_name) or "（C区）" in room_name or "(C区)" in room_name:
                                        # 处理各种格式的C区房间
                                        if "（C区）" in room_name or "(C区)" in room_name:
                                            # 提取楼层号
                                            floor = room_name[0]
                                            room_number = f"{floor}C"
                                        # 处理类似"2楼北面（C区）"的情况
                                        elif "（" in room_name and "）" in room_name:
                                            floor = room_name[0]
                                            area = room_name[room_name.find("（") + 1]
                                            room_number = f"{floor}{area}"
                                        else:
                                            floor = room_name[0]
                                            area = room_name[room_name.find("(") + 1]
                                            room_number = f"{floor}{area}"
                                    else:
                                        room_number = room_name.split("自修室")[0].split("书库")[0].split("区")[0].strip()
                                    
                                    rooms_info[room_number] = {
                                        "id": room["id"],
                                        "name": room["name"],
                                        "total_seats": room["totalCount"]
                                    }
                    # 如果有子节点，继续递归
                    elif "children" in node:
                        for child in node["children"]:
                            extract_rooms(child)
                
                # 处理所有校区
                for campus in data["data"]:
                    extract_rooms(campus)
                
                if not rooms_info:
                    print("\033[33m[WARNING] 未找到大学城校区的房间信息\033[0m")
                    return None
                
                self.rooms_info = rooms_info
                self.debug_print(f"解析出 {len(rooms_info)} 个房间信息")
                return rooms_info
            else:
                print(f"获取房间信息失败: {data['message']}")
                return None
                
        except Exception as e:
            print(f"获取房间信息时发生错误: {str(e)}")
            if self.debug:
                import traceback
                self.debug_print(f"异常详情: {traceback.format_exc()}")
            return None

    def get_seats_info(self, date_str, room_id):
        """获取指定日期和房间的座位列表信息"""
        try:
            # 构建请求URL
            url = f"https://{self.base_url}/ic-web/reserve"
            
            # 构建请求参数
            params = {
                "roomIds": room_id,
                "resvDates": f"{self.year}{date_str}",
                "sysKind": "8"
            }
            
            self.debug_print(f"发送GET请求: {url}")
            self.debug_print(f"请求参数: {params}")
            
            # 发送GET请求
            response = requests.get(url, headers=self.headers, params=params, verify=False)
            
            # 解析JSON响应
            data = response.json()
            
            print(f"{data}")
            if self.debug:
                self.debug_print(f"响应状态码: {response.status_code}")
                self.debug_print(f"响应数据大小: {len(response.content)} 字节")
                seats_count = len(data["data"]) if data["code"] == 0 and "data" in data else 0
                self.debug_print(f"座位数量: {seats_count}")
                if seats_count > 0:
                    self.debug_print(f"座位示例: {json.dumps(data['data'][0], indent=2, ensure_ascii=False)}")
            
            if data["code"] == 0:
                seats_info = {}
                for seat in data["data"]:
                    seat_info = {
                        "devId": seat["devId"],
                        "devName": seat["devName"],
                        "coordinate": seat.get("coordinate", ""),  # 添加坐标信息
                        "reserved_times": []
                    }
                    
                    # 提取已预约时间段
                    for resv in seat.get("resvInfo", []):
                        start_time = datetime.fromtimestamp(resv["startTime"]/1000)
                        end_time = datetime.fromtimestamp(resv["endTime"]/1000)
                        seat_info["reserved_times"].append({
                            "start": start_time.strftime("%H:%M"),
                            "end": end_time.strftime("%H:%M")
                        })
                    
                    seats_info[seat["devName"]] = seat_info
                
                self.debug_print(f"成功获取 {len(seats_info)} 个座位信息")
                return seats_info
            else:
                print(f"获取座位信息失败: {data['message']}")
                self.debug_print(f"错误响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
                return None
                
        except Exception as e:
            print(f"获取座位信息时发生错误: {str(e)}")
            if self.debug:
                import traceback
                self.debug_print(f"异常详情: {traceback.format_exc()}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()

    def get_available_times(self, seat_info):
        """计算座位可用时间段"""
        # 图书馆开放时间
        opening_time = "08:30"
        closing_time = "21:45"
        
        # 将已预约时间段按开始时间排序
        reserved_times = sorted(seat_info["reserved_times"], key=lambda x: x["start"])
        
        # 计算可用时间段
        available_times = []
        current_time = opening_time
        
        for reserved in reserved_times:
            if current_time < reserved["start"]:
                available_times.append({
                    "start": current_time,
                    "end": reserved["start"]
                })
            current_time = reserved["end"]
        
        # 添加最后一个预约之后到闭馆的时间段
        if current_time < closing_time:
            available_times.append({
                "start": current_time,
                "end": closing_time
            })
        
        return available_times

    def make_reservation(self, seat_sn, begin_time, end_time, date_str, app_acc_no=None):
        """提交座位预约请求"""
        # 清理可能存在的非法Unicode字符
        begin_time = ''.join(char for char in begin_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
        end_time = ''.join(char for char in end_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
        
        # 使用传入的app_acc_no或尝试获取
        if app_acc_no is None:
            # 确保已获取appAccNo
            if self.app_acc_no is None:
                self.get_app_acc_no()
            app_acc_no = self.app_acc_no
        
        # 检查app_acc_no是否有效
        if not app_acc_no:
            return {"code": -1, "message": "无法获取用户ID (appAccNo)"}
        
        # 确保self.year存在
        if not hasattr(self, 'year') or self.year is None:
            # 如果date_str是MMDD格式 (例如0513)
            if len(date_str) == 4:
                self.year = str(datetime.now().year)
            # 如果date_str是YYYYMMDD格式 (例如20250513)
            elif len(date_str) == 8:
                self.year = date_str[:4]
                date_str = date_str[4:]  # 截取后面的MMDD部分
            # 如果是其他格式则使用当前年份
            else:
                self.year = str(datetime.now().year)
        
        # 构建正确的日期字符串格式
        try:
            # 解析日期字符串
            if len(date_str) == 4:  # MMDD
                month = date_str[:2]
                day = date_str[2:]
                formatted_date = f"{self.year}-{month}-{day}"
            elif len(date_str) == 8:  # YYYYMMDD
                year = date_str[:4]
                month = date_str[4:6]
                day = date_str[6:]
                formatted_date = f"{year}-{month}-{day}"
            elif '-' in date_str:  # YYYY-MM-DD
                formatted_date = date_str
            else:
                return {"code": -1, "message": f"无效的日期格式: {date_str}"}
        except Exception as e:
            return {"code": -1, "message": f"日期格式处理错误: {str(e)}"}
        
        data = {
            "sysKind": 8,
            "memberKind": 1,
            "appAccNo": app_acc_no,
            "resvMember": [app_acc_no],  # 使用appAccNo值
            "resvBeginTime": f"{formatted_date} {begin_time}:00",
            "resvEndTime": f"{formatted_date} {end_time}:00",
            "testName": "",
            "captcha": "",
            "resvProperty": 0,
            "resvDev": [seat_sn],
            "memo": ""
        }

        try:
            # 构建请求URL
            url = f"http://{self.base_url}/ic-web/reserve"
            
            if self.debug:
                self.debug_print(f"发送预约请求: {url}")
                self.debug_print(f"预约数据: {json.dumps(data, ensure_ascii=False)}")
            
            # 发送POST请求
            response = requests.post(url, headers=self.headers, json=data, verify=False)
            
            # 解析JSON响应
            result = response.json()
            
            if self.debug:
                self.debug_print(f"预约响应状态码: {response.status_code}")
                self.debug_print(f"预约响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 转换响应格式为统一的格式
            if "code" in result:
                result["CODE"] = result["code"]
                result["MESSAGE"] = result.get("message", "")
            
            if result.get("CODE", result.get("code")) == 0:
                print(f"\033[32m预约成功! 座位: {seat_sn}, 时间: {begin_time}-{end_time}\033[0m")
            else:
                print(f"\033[31m预约失败: {result.get('MESSAGE', result.get('message', '未知错误'))}\033[0m")
            
            return result
            
        except Exception as e:
            print(f"\033[31m[ERROR] 预约请求发生错误: {str(e)}\033[0m")
            if self.debug:
                import traceback
                self.debug_print(f"预约异常详情: {traceback.format_exc()}")
            return {"CODE": -1, "MESSAGE": f"预约请求异常: {str(e)}"}

    def get_room_layout(self, room_id):
        """获取房间平面图"""
        try:
            # 创建HTTPS连接
            conn = http.client.HTTPSConnection(self.base_url)
            
            # 构建请求路径 - 确保URL编码
            path = f"/ic-web/sysInfo?sysType=2&sysValue={room_id}&sysKind=16"
            
            self.debug_print(f"发送GET请求: https://{self.base_url}{path}")
            self.debug_print(f"请求参数: sysType=2, sysValue={room_id}, sysKind=16")
            
            # 发送GET请求
            conn.request("GET", path, headers=self.headers)
            
            # 获取响应
            response = conn.getresponse()
            response_data = response.read()
            
            # 解析JSON响应
            data = json.loads(response_data.decode("utf-8"))
            
            if self.debug:
                self.debug_print(f"响应状态码: {response.status}")
                self.debug_print(f"响应数据大小: {len(response_data)} 字节")
                if data["code"] == 0 and data["data"]:
                    self.debug_print(f"房间平面图数据: {json.dumps(data['data'], indent=2, ensure_ascii=False)}")
                else:
                    self.debug_print(f"错误响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data["code"] == 0 and data["data"]:
                # 提取图片信息
                image_data = data["data"]
                try:
                    # 获取图片路径
                    if isinstance(image_data, dict) and "content" in image_data:
                        image_path = image_data["content"]
                        if image_path:
                            try:
                                # 创建新的连接获取图片
                                conn = http.client.HTTPSConnection(self.base_url)
                                image_request_path = f"/ic-web/{image_path}"
                                
                                # 确保路径编码正确
                                # 转义非ASCII字符
                                image_request_path = urllib.parse.quote(image_request_path, safe='/:-._?=&')
                                
                                self.debug_print(f"获取图片请求: https://{self.base_url}{image_request_path}")
                                
                                # 发送GET请求获取图片
                                conn.request("GET", image_request_path, headers=self.headers)
                                image_response = conn.getresponse()
                                image_bytes = image_response.read()
                                
                                self.debug_print(f"图片响应状态码: {image_response.status}")
                                self.debug_print(f"图片数据大小: {len(image_bytes)} 字节")
                                
                                # 创建PIL图片对象
                                image = Image.open(io.BytesIO(image_bytes))
                                # 转换为RGB模式
                                if image.mode in ['RGBA', 'LA']:
                                    background = Image.new('RGB', image.size, 'white')
                                    background.paste(image, mask=image.split()[-1])
                                    image = background
                                elif image.mode != 'RGB':
                                    image = image.convert('RGB')
                                return image
                            except Exception as e:
                                print(f"\033[33m[WARNING] 处理图片请求时出错: {str(e)}\033[0m")
                                self.debug_print(f"处理图片请求异常: {str(e)}")
                                # 返回一个空白背景作为备选
                                return self.create_blank_layout()
                    else:
                        print("\033[33m[WARNING] 未找到图片路径\033[0m")
                        self.debug_print("未在响应中找到图片路径内容")
                        return self.create_blank_layout()
                except Exception as e:
                    print(f"\033[33m[WARNING] 获取图片时出错: {str(e)}\033[0m")
                    if self.debug:
                        import traceback
                        self.debug_print(f"获取图片异常详情: {traceback.format_exc()}")
                    return self.create_blank_layout()
            else:
                print("\033[33m[WARNING] 获取房间平面图信息失败\033[0m")
                self.debug_print(f"获取平面图信息失败: {data.get('message', '未知错误')}")
                return self.create_blank_layout()
                
        except Exception as e:
            print(f"\033[33m[WARNING] 获取房间平面图时发生错误: {str(e)}\033[0m")
            if self.debug:
                import traceback
                self.debug_print(f"异常详情: {traceback.format_exc()}")
            return self.create_blank_layout()
        finally:
            if 'conn' in locals():
                conn.close()
                
    def create_blank_layout(self, width=800, height=600):
        """创建一个空白的背景图用于当房间布局图无法获取时使用"""
        # 创建一个白色背景图像
        blank_image = Image.new('RGB', (width, height), (245, 245, 245))
        
        # 在图像上绘制一些网格线，使其看起来像一个布局图
        from PIL import ImageDraw
        draw = ImageDraw.Draw(blank_image)
        
        # 绘制水平线
        for y in range(0, height, 50):
            draw.line([(0, y), (width, y)], fill=(220, 220, 220), width=1)
            
        # 绘制垂直线
        for x in range(0, width, 50):
            draw.line([(x, 0), (x, height)], fill=(220, 220, 220), width=1)
            
        # 添加文字说明布局图无法加载
        return blank_image

    def visualize_seats(self, seats_info, room_id, target_start=None, target_end=None):
        """生成座位布局图"""
        # 获取房间平面图
        room_layout = self.get_room_layout(room_id)
        
        # 获取房间名称
        room_name = ""
        for room_number, info in self.rooms_info.items():
            if info["id"] == room_id:
                room_name = info["name"]
                break
        
        # 创建新的图形
        fig = plt.figure(figsize=(15, 10))
        ax = fig.add_subplot(111)
        
        # 设置中文字体 - 处理可能的字体问题
        try:
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'sans-serif']  # 尝试多种字体
            plt.rcParams['axes.unicode_minus'] = False
        except Exception as e:
            print(f"\033[33m[WARNING] 设置字体时出错: {str(e)}\033[0m")
        
        # 获取所有座位的坐标以计算范围
        x_coords = []
        y_coords = []
        for seat_info in seats_info.values():
            if "coordinate" in seat_info:
                coords = seat_info["coordinate"].split(",")
                if len(coords) >= 2:
                    # 调整坐标系统
                    x = float(coords[0])
                    y = float(coords[1])
                    x_coords.append(x)
                    y_coords.append(y)
        
        if x_coords and y_coords:
            # 计算坐标范围，并添加一些边距
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            margin = 5  # 边距百分比
            x_range = x_max - x_min
            y_range = y_max - y_min
            x_min -= x_range * margin / 100
            x_max += x_range * margin / 100
            y_min -= y_range * margin / 100
            y_max += y_range * margin / 100
            
            # 翻转Y轴，使坐标系与图片一致
            y_min, y_max = y_max, y_min
        else:
            x_min, x_max = 0, 100
            y_min, y_max = 100, 0  # 翻转Y轴
        
        if room_layout:
            # 显示房间平面图，并设置其范围与座位坐标一致
            ax.imshow(room_layout, extent=[x_min, x_max, y_min, y_max], cmap='gray')
            # 调整图片亮度和对比度
            plt.setp(ax.get_images(), alpha=0.7)
        
        # 存储所有座位的信息
        seat_numbers = []
        simplified_seat_numbers = []  # 存储简化后的座位号
        colors = []
        
        # 当前时间
        current_time = datetime.now().strftime("%H:%M")
        
        # 重置坐标列表用于绘制散点图
        x_coords = []
        y_coords = []
        
        for seat_name, seat_info in seats_info.items():
            if "coordinate" in seat_info:
                coords = seat_info["coordinate"].split(",")
                if len(coords) >= 2:
                    # 调整坐标系统
                    x = float(coords[0])
                    y = float(coords[1])
                    x_coords.append(x)
                    y_coords.append(y)
                    seat_numbers.append(seat_name)
                    
                    # 提取座位号的后缀部分
                    if "-" in seat_name:
                        simplified_seat_numbers.append(seat_name.split("-")[-1])
                    else:
                        simplified_seat_numbers.append(seat_name)
                    
                    # 根据座位状态设置颜色
                    if target_start and target_end:
                        # 模式二：根据指定时间段判断座位是否可用
                        is_available = self.check_seat_available(seat_info, target_start, target_end)
                        colors.append('green' if is_available else 'yellow')
                    else:
                        # 模式一：根据座位当前预约状态设置颜色
                        if seat_info["reserved_times"]:
                            is_reserved = False
                            for resv in seat_info["reserved_times"]:
                                if resv["start"] <= current_time <= resv["end"]:
                                    is_reserved = True
                                    break
                            colors.append('red' if is_reserved else 'orange')
                        else:
                            colors.append('green')
        
        # 绘制散点图
        scatter = ax.scatter(x_coords, y_coords, c=colors, s=100, alpha=0.7, edgecolors='white')
        
        # 添加座位号标签，只显示后缀
        for i, txt in enumerate(simplified_seat_numbers):
            ax.annotate(txt, (x_coords[i], y_coords[i]),
                       xytext=(0, -15),  # 调整标签位置到点的下方
                       textcoords='offset points',
                       fontsize=8,
                       color='black',
                       ha='center',  # 水平居中对齐
                       bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))
        
        # 添加图例
        if target_start and target_end:
            # 模式二的图例
            legend_elements = [
                plt.scatter([], [], c='green', label=f'在{target_start}-{target_end}时段可用', alpha=0.7, edgecolors='white'),
                plt.scatter([], [], c='yellow', label=f'在{target_start}-{target_end}时段不可用', alpha=0.7, edgecolors='white')
            ]
        else:
            # 模式一的图例
            legend_elements = [
                plt.scatter([], [], c='green', label='可预约', alpha=0.7, edgecolors='white'),
                plt.scatter([], [], c='orange', label='部分时段已预约', alpha=0.7, edgecolors='white'),
                plt.scatter([], [], c='red', label='当前时段已预约', alpha=0.7, edgecolors='white')
            ]
        ax.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # 设置标题，包含房间名称
        title = f'{room_name} 座位布局图'
        if target_start and target_end:
            title += f' ({target_start}-{target_end}时段)'
        ax.set_title(title)
        
        # 移除坐标轴
        ax.set_xticks([])
        ax.set_yticks([])
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图片
        plt.savefig('seat_layout.png', bbox_inches='tight', dpi=300, facecolor='white')
        print("\n座位布局图已保存为 seat_layout.png")
        
        # 使用非阻塞模式显示图形
        # plt.show(block=False)

    def check_seat_available(self, seat_info, target_start, target_end):
        """检查座位在指定时间段是否可用"""
        # 座位没有预约记录，则完全可用
        if not seat_info["reserved_times"]:
            return True
            
        # 检查是否与已预约时间段冲突
        for resv in seat_info["reserved_times"]:
            # 检查时间是否重叠：两个时间段重叠的条件是开始时间小于对方的结束时间且结束时间大于对方的开始时间
            if not (target_end <= resv["start"] or target_start >= resv["end"]):
                return False
                
        return True

    def split_time_periods(self, start_time, end_time, max_minutes=240, min_minutes=60):
        """将长时间段拆分为多个时间段，确保每段不少于min_minutes分钟且不超过max_minutes分钟
        
        Args:
            start_time: 开始时间 (HH:MM)
            end_time: 结束时间 (HH:MM)
            max_minutes: 每段最大分钟数，默认240分钟
            min_minutes: 每段最小分钟数，默认60分钟
            
        Returns:
            时间段列表，每个元素为(开始时间, 结束时间)的元组
        """
        # 转换时间字符串为datetime对象
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")
        
        # 计算分钟差
        if end_dt < start_dt:  # 处理跨天的情况
            end_dt = end_dt + timedelta(days=1)
        
        time_diff = (end_dt - start_dt).total_seconds() / 60
        
        # 检查总时间是否满足最小时间要求
        if time_diff < min_minutes:
            print(f"\n\033[33m[WARNING] 预约时间段小于{min_minutes}分钟，图书馆要求预约时间至少为{min_minutes}分钟\033[0m")
            # 尝试延长到最小时间
            if end_dt + timedelta(minutes=(min_minutes - time_diff)) <= datetime.strptime("21:45", "%H:%M"):
                end_dt = start_dt + timedelta(minutes=min_minutes)
                end_time = end_dt.strftime("%H:%M")
                print(f"\n已自动调整结束时间为: {end_time}")
            else:
                print(f"\n无法自动调整时间段到符合要求，请重新选择")
                return []
        
        # 如果时间段不超过max_minutes，直接返回
        if time_diff <= max_minutes:
            return [(start_time, end_time)]
        
        # 否则，将时间段拆分为多个不超过max_minutes的时间段
        time_periods = []
        current_start = start_dt
        
        # 计算完整的时间段数量
        num_full_periods = int(time_diff // max_minutes)
        remaining_minutes = time_diff % max_minutes
        
        # 如果剩余时间小于最小时间要求，调整最后一个完整时间段
        if 0 < remaining_minutes < min_minutes:
            # 减少完整时间段的数量
            if num_full_periods > 0:
                # 分配剩余分钟到最后一个完整段
                adjusted_last_period = max_minutes + remaining_minutes
                # 确保不超过最大时间限制
                if adjusted_last_period <= max_minutes:
                    num_full_periods -= 1
                    remaining_minutes = adjusted_last_period
            else:
                # 如果没有完整时间段，直接返回整段
                return [(start_time, end_time)]
        
        # 添加完整时间段
        for _ in range(num_full_periods):
            current_end = current_start + timedelta(minutes=max_minutes)
            time_periods.append((
                current_start.strftime("%H:%M"),
                current_end.strftime("%H:%M")
            ))
            current_start = current_end
        
        # 添加最后一个不完整时间段（如果有）
        if remaining_minutes >= min_minutes:
            time_periods.append((
                current_start.strftime("%H:%M"),
                end_dt.strftime("%H:%M")
            ))
        elif remaining_minutes > 0 and time_periods:
            # 如果剩余时间太短但大于0，将其并入前一段
            last_start, _ = time_periods.pop()
            time_periods.append((
                last_start,
                end_dt.strftime("%H:%M")
            ))
        
        # 最终检查所有时间段，确保没有超过max_minutes的段
        validated_periods = []
        for start_str, end_str in time_periods:
            start_period = datetime.strptime(start_str, "%H:%M")
            end_period = datetime.strptime(end_str, "%H:%M")
            
            # 处理跨天情况
            if end_period < start_period:
                end_period = end_period + timedelta(days=1)
                
            period_minutes = (end_period - start_period).total_seconds() / 60
            
            # 如果发现超过最大时间的段，进行再次拆分
            if period_minutes > max_minutes:
                # 计算需要切分的次数
                num_splits = int(period_minutes // max_minutes)
                split_start = start_period
                
                for _ in range(num_splits):
                    split_end = split_start + timedelta(minutes=max_minutes)
                    validated_periods.append((
                        split_start.strftime("%H:%M"),
                        split_end.strftime("%H:%M")
                    ))
                    split_start = split_end
                
                # 处理最后一段
                remaining = (end_period - split_start).total_seconds() / 60
                if remaining >= min_minutes:
                    validated_periods.append((
                        split_start.strftime("%H:%M"),
                        end_period.strftime("%H:%M")
                    ))
                elif remaining > 0 and validated_periods:
                    # 合并到前一段
                    last_start, _ = validated_periods.pop()
                    validated_periods.append((
                        last_start,
                        end_period.strftime("%H:%M")
                    ))
            else:
                validated_periods.append((start_str, end_str))
        
        # 最后确认每个时间段的时长
        final_periods = []
        for start_str, end_str in validated_periods:
            start_period = datetime.strptime(start_str, "%H:%M")
            end_period = datetime.strptime(end_str, "%H:%M")
            
            # 处理跨天情况
            if end_period < start_period:
                end_period = end_period + timedelta(days=1)
                
            period_minutes = (end_period - start_period).total_seconds() / 60
            
            # 确保不超过最大允许时间
            if period_minutes > max_minutes:
                end_period = start_period + timedelta(minutes=max_minutes)
                end_str = end_period.strftime("%H:%M")
                
            final_periods.append((start_str, end_str))
        
        return final_periods

    def generate_checkin_qrcode(self, seat_id, seat_number):
        """生成签到二维码"""
        try:
            # 构建签到URL
            checkin_url = f"http://update.unifound.net/wxnotice/s.aspx?c=12_nSeat_{seat_id}_1EW"
            
            # 使用qrcode库生成二维码
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(checkin_url)
            qr.make(fit=True)

            # 在终端打印ASCII二维码
            print("\n签到二维码（扫描下方二维码签到）:")
            qr.print_ascii(invert=True)
            print(f"签到URL: {checkin_url}")
            
            # 创建图像
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # 确保qrcode文件夹存在
            qrcode_dir = "qrcode"
            if not os.path.exists(qrcode_dir):
                os.makedirs(qrcode_dir)
            
            # 保存图像，以座位号命名
            qr_filename = f"{qrcode_dir}/{seat_number}.png"
            qr_img.save(qr_filename)
            
            print(f"二维码已保存为: {qr_filename}")
            
            return qr_filename
        except Exception as e:
            print(f"\033[33m[WARNING] 生成签到二维码时出错: {str(e)}\033[0m")
            return None

    def get_reservations(self):
        """获取当前用户的预约列表"""
        try:
            # 计算查询日期范围（前一天到后一天）
            today = datetime.now()
            begin_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            
            # 构建请求URL和参数
            url = f"https://{self.base_url}/ic-web/reserve/resvInfo"
            params = {
                "beginDate": begin_date,
                "endDate": end_date,
                "needStatus": "6",
                "page": "1",
                "pageNum": "50",
                "orderKey": "gmt_create",
                "orderModel": "desc"
            }
            
            self.debug_print(f"发送GET请求: {url}")
            self.debug_print(f"请求参数: {params}")
            
            # 发送GET请求
            response = requests.get(url, headers=self.headers, params=params, verify=False)
            
            # 解析JSON响应
            data = response.json()
            
            if self.debug:
                self.debug_print(f"响应状态码: {response.status_code}")
                self.debug_print(f"响应数据大小: {len(response.content)} 字节")
                if data["code"] == 0:
                    reservations_count = len(data["data"]) if "data" in data else 0
                    self.debug_print(f"预约记录数: {reservations_count}")
                    if reservations_count > 0:
                        self.debug_print(f"预约记录示例: {json.dumps(data['data'][0], indent=2, ensure_ascii=False)}")
                        
                        # 输出所有不同的状态码，帮助发现新的状态类型
                        if "data" in data and len(data["data"]) > 0:
                            status_codes = set(item["resvStatus"] for item in data["data"])
                            self.debug_print(f"发现的状态码: {status_codes}")
                            for code in status_codes:
                                desc = self.get_reservation_status_description(code)
                                self.debug_print(f"状态码 {code}: {desc}")
                else:
                    self.debug_print(f"错误响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data["code"] == 0:
                reservations = data["data"]
                return reservations
            else:
                print(f"\033[31m获取预约列表失败: {data.get('message', '未知错误')}\033[0m")
                return None
                
        except Exception as e:
            print(f"\033[31m[ERROR] 获取预约列表时发生错误: {str(e)}\033[0m")
            if self.debug:
                import traceback
                self.debug_print(f"异常详情: {traceback.format_exc()}")
            return None

    def get_reservation_status_description(self, status_code):
        """
        根据状态码返回友好的预约状态描述
        
        Args:
            status_code: 预约状态码
            
        Returns:
            status_description: 状态描述字符串
        """
        status_map = {
            1027: "已预约（等待签到）",
            1093: "已签到（使用中）",
            1029: "已超时（未签到被系统取消）",
            3141: "暂时离开",
            1031: "已终止（管理员终止）",
            1033: "已删除（被管理员删除）"
        }
        
        return status_map.get(status_code, f"未知状态({status_code})")
        
    def display_reservations(self, reservations):
        """显示预约列表并允许用户选择查看签到二维码或删除预约"""
        if not reservations:
            print("\n暂无预约记录")
            return
        
        print("\n========== 当前预约列表 ==========")
        print(f"共找到 {len(reservations)} 条预约记录")
        
        # 按预约开始时间排序
        sorted_reservations = sorted(reservations, key=lambda x: x["resvBeginTime"])
        
        for i, resv in enumerate(sorted_reservations, 1):
            # 获取座位信息
            seat_info = resv["resvDevInfoList"][0] if resv["resvDevInfoList"] else {"devName": "未知", "roomName": "未知"}
            
            # 转换时间戳为可读时间
            begin_time = datetime.fromtimestamp(resv["resvBeginTime"]/1000).strftime("%Y-%m-%d %H:%M")
            end_time = datetime.fromtimestamp(resv["resvEndTime"]/1000).strftime("%H:%M")
            
            # 获取预约状态
            status_code = resv["resvStatus"]
            status = self.get_reservation_status_description(status_code)
            
            # 显示预约信息
            print(f"\n{i}. 座位: {seat_info['devName']} ({seat_info['roomName']})")
            print(f"   时间: {begin_time} - {end_time}")
            print(f"   状态: {status}")
            
            # 计算距离签到时间
            if status_code == 1027:  # 如果是未签到状态
                latest_check_in_time = datetime.fromtimestamp(resv["latestCheckInTime"]/1000)
                now = datetime.now()
                if latest_check_in_time > now:
                    time_diff = latest_check_in_time - now
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    print(f"   距离签到截止时间还有: {int(hours)}小时{int(minutes)}分钟")
                else:
                    print("   已超过签到时间")
        
        # 提供操作选项
        while True:
            print("\n请选择操作：")
            print("1. 删除预约")
            print("2. 查看预约二维码")
            print("3. 签到")
            print("4. 返回主菜单")
            
            choice = input("\n请输入操作编号 (1/2/3/4): ")
            
            if choice == "1":
                # 删除预约流程
                print("\n请选择要删除的预约：")
                delete_choice = input("请输入预约序号(输入0返回): ")
                
                try:
                    index = int(delete_choice)
                    if index == 0:
                        continue
                    
                    if 1 <= index <= len(sorted_reservations):
                        selected_resv = sorted_reservations[index-1]
                        uuid = selected_resv["uuid"]
                        room_name = selected_resv["resvDevInfoList"][0]["roomName"] if selected_resv["resvDevInfoList"] else "未知"
                        seat_name = selected_resv["resvDevInfoList"][0]["devName"] if selected_resv["resvDevInfoList"] else "未知"
                        
                        print(f"\n您选择删除的预约信息:")
                        print(f"座位: {seat_name} ({room_name})")
                        begin_time = datetime.fromtimestamp(selected_resv["resvBeginTime"]/1000).strftime("%Y-%m-%d %H:%M")
                        end_time = datetime.fromtimestamp(selected_resv["resvEndTime"]/1000).strftime("%H:%M")
                        print(f"时间: {begin_time} - {end_time}")
                        
                        confirm = input("\n确认删除？(y/n): ")
                        if confirm.lower() == 'y':
                            success = self.delete_reservation(uuid)
                            if success:
                                print("\n\033[32m[SUCCESS] 预约删除成功！\033[0m")
                                # 重新获取预约列表
                                print("\n正在更新预约列表...")
                                new_reservations = self.get_reservations()
                                if new_reservations:
                                    # 递归调用显示新的预约列表
                                    return self.display_reservations(new_reservations)
                                else:
                                    print("\n暂无预约记录")
                                    return None
                    else:
                        print("\n无效的选择")
                except ValueError:
                    print("\n请输入有效的数字")
                
            elif choice == "2":
                # 查看预约二维码流程
                if any(resv["resvStatus"] == 1027 for resv in sorted_reservations):  # 如果有未签到的预约
                    print("\n请选择要查看的预约：")
                    qr_choice = input("请输入预约序号(输入0返回): ")
                    
                    try:
                        index = int(qr_choice)
                        if index == 0:
                            continue
                            
                        if 1 <= index <= len(sorted_reservations):
                            selected_resv = sorted_reservations[index-1]
                            
                            seat_info = selected_resv["resvDevInfoList"][0]
                            self.generate_checkin_qrcode(seat_info["devSn"], seat_info["devName"])
                            
                        else:
                            print("\n无效的选择")
                    except ValueError:
                        print("\n请输入有效的数字")
                else:
                    print("\n没有可以签到的预约")
                    
            elif choice == "3":
                # 签到流程
                
                print("\n请选择要签到的预约：")
                sign_choice = input("请输入预约序号(输入0返回): ")
                    
                try:
                        index = int(sign_choice)
                        if index == 0:
                            continue
                            
                        if 1 <= index <= len(sorted_reservations):
                            selected_resv = sorted_reservations[index-1]
                            seat_info = selected_resv["resvDevInfoList"][0]
                            devSn = seat_info["devSn"]
                            success = self.sign_reservation(devSn)
                            if success:
                                print("\n\033[32m[SUCCESS] 签到成功！\033[0m")
                            # 重新获取预约列表
                            print("\n正在更新预约列表...")
                            new_reservations = self.get_reservations()
                            return self.display_reservations(new_reservations)
                        else:
                            print("\n无效的选择")
                except ValueError:
                        print("\n请输入有效的数字")
                
                    
            elif choice == "4":
                # 返回主菜单
                return None
            else:
                print("\n无效的选择，请重新输入")
        
        return sorted_reservations

    def sign_reservation(self, devSn):
        """发送请求签到预约"""
        try:
            lurl = f"https://{self.base_url}/ic-web/phoneSeatReserve/login"
            
            # 发送POST请求
            login_data = {
                "devSn": devSn,
                "type": "1",
                "bind": 0,
                "loginType": 2
            }
            
            response_login = requests.post(url=lurl, json=login_data, headers=self.headers, timeout=60)
            
            response_login_data = response_login.json()
            
            if self.debug:
                self.debug_print(f"响应状态码: {response_login.status_code}")
                self.debug_print(f"响应数据: {json.dumps(response_login_data, indent=2, ensure_ascii=False)}")
            
            resvId = response_login_data.get('data').get('reserveInfo').get('resvId')
            # 构造请求数据
            data = {"resvId": resvId}
            
            self.debug_print(f"发送POST请求: https://{self.base_url}/ic-web/phoneSeatReserve/sign")
            self.debug_print(f"请求数据: {data}")
            
            # 发送POST请求
            url = f"https://{self.base_url}/ic-web/phoneSeatReserve/sign"
            response = requests.post(url, headers=self.headers, json=data, verify=False)
            
            # 解析JSON响应
            result = response.json()
            
            if self.debug:
                self.debug_print(f"响应状态码: {response.status_code}")
                self.debug_print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if result["code"] == 0:
                return True
            else:
                print(f"\033[31m[ERROR] 签到失败: {result.get('message', '未知错误')}\033[0m")
                return False
                
        except Exception as e:
            print(f"\033[31m[ERROR] 签到请求发生错误: {str(e)}\033[0m")
            if self.debug:
                import traceback
                self.debug_print(f"异常详情: {traceback.format_exc()}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def delete_reservation(self, uuid):
        """发送请求删除预约"""
        try:
            # 构建请求URL
            url = f"https://{self.base_url}/ic-web/reserve/delete"
            
            # 构造请求数据
            data = {"uuid": uuid}
            
            self.debug_print(f"发送POST请求: {url}")
            self.debug_print(f"请求数据: {json.dumps(data)}")
            
            # 发送POST请求
            response = requests.post(url, headers=self.headers, json=data, verify=False)
            
            # 解析JSON响应
            result = response.json()
            
            if self.debug:
                self.debug_print(f"响应状态码: {response.status_code}")
                self.debug_print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if result["code"] == 0:
                return True
            else:
                print(f"\033[31m删除预约失败: {result.get('message', '未知错误')}\033[0m")
                return False
                
        except Exception as e:
            print(f"\033[31m[ERROR] 删除预约请求发生错误: {str(e)}\033[0m")
            if self.debug:
                import traceback
                self.debug_print(f"异常详情: {traceback.format_exc()}")
            return False

    def auto_book_at_time(self, seat_info, date_str, start_time, end_time, target_time, room_number, seats_info, room_id):
        """在指定时间自动预约座位"""
        seat_number = seat_info["devName"]
        seat_sn = seat_info["devId"]
        
        # 清理可能存在的非法Unicode字符
        start_time = ''.join(char for char in start_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
        end_time = ''.join(char for char in end_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
        
        # 计算需要等待的时间
        now = datetime.now()
        
        # 解析目标时间 (HH:MM)
        target_parts = target_time.split(":")
        target_hour = int(target_parts[0])
        target_minute = int(target_parts[1])
        
        # 创建目标日期时间对象
        target_datetime = datetime(now.year, now.month, now.day, target_hour, target_minute)
        
        # 如果目标时间已经过去，设置为明天
        if target_datetime < now:
            target_datetime = target_datetime + timedelta(days=1)
        
        # 计算等待时间（秒）
        wait_seconds = (target_datetime - now).total_seconds()
        
        # 检查时间段是否需要拆分（超过240分钟）
        time_periods = self.split_time_periods(start_time, end_time)
        is_split = len(time_periods) > 1
        
        if is_split:
            print(f"\n您选择的时间段({start_time}-{end_time})超过4小时，将自动拆分为以下时间段：")
            for i, (s, e) in enumerate(time_periods, 1):
                print(f"  {i}. {s}-{e}")
        
        # 显示预约信息
        print(f"\n将在 {target_datetime.strftime('%Y-%m-%d %H:%M:%S')} 自动预约以下座位：")
        print(f"房间: {self.rooms_info[room_number]['name']}")
        print(f"座位号: {seat_number}")
        print(f"日期: {self.year}-{date_str[:2]}-{date_str[2:]}")
        if is_split:
            periods_str = ", ".join([f"{s}-{e}" for s, e in time_periods])
            print(f"时间段: {periods_str}")
        else:
            print(f"时间段: {start_time}-{end_time}")
        
        print(f"\n距离预约时间还有: {int(wait_seconds//3600)}小时 {int((wait_seconds%3600)//60)}分钟 {int(wait_seconds%60)}秒")
        print(f"请保持网络连接并勿关闭程序，程序将在目标时间自动发送预约请求...\n")
        print("系统将在预约前10分钟自动刷新登录状态，确保预约成功")

        # 计算预约前10分钟的时间
        refresh_time = target_datetime - timedelta(minutes=10)
        
        # 等待直到预约前10分钟
        while datetime.now() < refresh_time:
            # 每10秒显示一次倒计时信息
            if int(datetime.now().timestamp()) % 10 == 0:
                remaining = (target_datetime - datetime.now()).total_seconds()
                print(f"\r距离预约还有: {int(remaining//3600)}小时 {int((remaining%3600)//60)}分钟 {int(remaining%60)}秒", end="")
            time.sleep(1)
            
        # 到达预约前10分钟，刷新cookie
        print("\n\n已到达预约前10分钟，正在刷新登录状态...")
        if not self.refresh_cookie_if_needed(force_refresh=True):
            print("\n\033[31m[ERROR] 自动刷新登录状态失败，预约可能会失败\033[0m")
            
        # 继续等待到预约时间
        while datetime.now() < target_datetime:
            # 每秒显示一次倒计时信息
            remaining = (target_datetime - datetime.now()).total_seconds()
            print(f"\r距离预约还有: {int(remaining//60)}分钟 {int(remaining%60)}秒", end="")
            time.sleep(1)
        
        print(f"\n\n已到达预约时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("正在发送预约请求...")
        
        # 发送预约请求
        success_flag = False
        if is_split:
            all_success = True
            success_periods = []
            
            for i, (period_start, period_end) in enumerate(time_periods, 1):
                print(f"\n提交第 {i}/{len(time_periods)} 段预约 ({period_start}-{period_end})...")
                result = self.make_reservation(seat_sn, period_start, period_end, date_str)
                if result and result.get("code") == 0:
                    success_periods.append((period_start, period_end))
                else:
                    all_success = False
                    
                    # 如果第一次失败，重试一次
                    if result and "已经预约" not in str(result.get("message", "")):
                        print("预约失败，正在重试...")
                        time.sleep(1)  # 等待1秒后重试
                        result = self.make_reservation(seat_sn, period_start, period_end, date_str)
                        if result and result.get("code") == 0:
                            success_periods.append((period_start, period_end))
                            all_success = True
            
            if all_success:
                print(f"\n\033[32m[SUCCESS] 所有时间段预约成功！\033[0m")
                success_flag = True
            elif success_periods:
                print(f"\n\033[33m[部分成功] 以下时间段预约成功：\033[0m")
                for i, (s, e) in enumerate(success_periods, 1):
                    print(f"  {i}. {s}-{e}")
                success_flag = True
            
            if success_periods:
                print(f"\n预约详情：")
                print(f"房间: {self.rooms_info[room_number]['name']}")
                print(f"座位号: {seat_number}")
                print(f"日期: {self.year}-{date_str[:2]}-{date_str[2:]}")
                periods_str = ", ".join([f"{s}-{e}" for s, e in success_periods])
                print(f"时间: {periods_str}")
        else:
            # 常规单次预约
            result = self.make_reservation(seat_sn, start_time.strip(), end_time.strip(), date_str)
            
            # 如果失败，重试一次
            if result and result.get("code") != 0 and "已经预约" not in str(result.get("message", "")):
                print("预约失败，正在重试...")
                time.sleep(1)  # 等待1秒后重试
                result = self.make_reservation(seat_sn, start_time.strip(), end_time.strip(), date_str)
            
            if result and result.get("code") == 0:
                print(f"\n\033[32m[SUCCESS] 预约成功！\033[0m")
                print(f"\n预约详情：")
                print(f"房间: {self.rooms_info[room_number]['name']}")
                print(f"座位号: {seat_number}")
                print(f"日期: {self.year}-{date_str[:2]}-{date_str[2:]}")
                print(f"时间: {start_time.strip()} - {end_time.strip()}")
                success_flag = True
        
        # 如果预约成功，生成签到二维码
        if success_flag:
            print("\n正在生成签到二维码...")
            self.generate_checkin_qrcode(seat_sn, seat_number)
            
            # 发出系统提示音通知用户
            print('\a')  # 系统提示音
        else:
            print("\n\033[31m[ERROR] 所有预约请求均失败\033[0m")
            print('\a\a\a')  # 多次提示音表示错误

    def request(self, method, url, **kwargs):
        """请求包装器，确保每次请求都使用随机UA
        
        Args:
            method: 请求方法，如'get', 'post'等
            url: 请求URL
            **kwargs: 请求的其他参数
            
        Returns:
            requests.Response: 请求响应对象
        """
        # 确保headers使用最新的
        if 'headers' not in kwargs:
            kwargs['headers'] = self.headers
            
        # 禁用SSL警告
        kwargs['verify'] = False
        
        # 发送请求
        self.debug_print(f"发送 {method.upper()} 请求: {url}")
        response = getattr(requests, method.lower())(url, **kwargs)
        self.debug_print(f"响应状态码: {response.status_code}")
        
        return response

def main():
    # 初始化账号管理器
    account_manager = AccountManager()
    
    # 账号选择流程
    print("=" * 80)
    print("\n欢迎使用广州大学图书馆座位预约脚本")
    print("\n脚本信息")
    print("- author: evermore")
    print("- verison: 1.0_250329")
    print("- github repo: https://github.com/Weverses/gzhu-library-booking")
    print("- license: GPL-3.0")
    print("\nEula: 非官方脚本，仅供学习交流使用，作者不对脚本使用产生的情况承担任何责任")
    print("使用该脚本即代表您已阅读并同意Eula")
    print("=" * 80)
    
    # 检查是否有已保存的账号
    accounts = account_manager.list_accounts()
    account_count = account_manager.get_account_count()
    is_new_account = False
    
    if account_count > 0:
        print(f"\n已保存 {account_count} 个账号：")
        for i, account in enumerate(accounts, 1):
            print(f"{i}. {account['nickname']} ({account['username']})")
            
        print("\n请选择操作：")
        print("1/2/3. 选择对应序号的账号登录")
        print("A. 添加新账号")
        print("B. 删除账号")
        print("C. 清空所有账号")
        print("Q. 退出程序")
        
        choice = input("\n请输入操作：").strip()
        
        if choice.upper() == 'Q':
            print("\n感谢使用，再见！")
            return
        elif choice.upper() == 'A':
            # 添加新账号流程
            username = input("\n请输入学号：").strip()
            password = input("请输入密码：").strip()
            nickname = input("请输入账号昵称（可选，直接回车使用默认）：").strip()
            
            if account_manager.add_account(username, password, nickname if nickname else None):
                print(f"\n✅ 账号 {username} 添加成功！")
            else:
                print(f"\n❌ 账号 {username} 添加失败！")
                return
                
            # 使用刚添加的账号继续
            selected_username = username
            selected_password = password
        
        elif choice.upper() == 'B':
            # 删除账号流程
            del_index = input("\n请输入要删除的账号序号：").strip()
            try:
                del_index = int(del_index)
                if 1 <= del_index <= len(accounts):
                    username_to_delete = accounts[del_index-1]['username']
                    confirm = input(f"确定要删除账号 {accounts[del_index-1]['nickname']} ({username_to_delete}) 吗？(y/n)：").strip().lower()
                    
                    if confirm == 'y':
                        if account_manager.remove_account(username_to_delete):
                            print(f"\n✅ 账号 {username_to_delete} 已删除！")
                        else:
                            print(f"\n❌ 账号 {username_to_delete} 删除失败！")
                    else:
                        print("\n已取消删除")
                else:
                    print("\n❌ 无效的账号序号！")
                
                # 删除后重新运行main函数
                return main()
            except ValueError:
                print("\n❌ 输入无效，请输入数字！")
                return main()
        
        elif choice.upper() == 'C':
            # 清空所有账号
            if account_count == 0:
                print("\n账号列表已经是空的")
                return main()
                
            confirm = input(f"\n确定要清空所有 {account_count} 个账号吗？此操作不可恢复！(YES/NO): ").strip()
            
            if confirm.upper() == "YES":
                # 逐个删除账号
                for account in accounts:
                    account_manager.remove_account(account['username'])
                    
                print("\n✅ 已清空所有账号")
            else:
                print("\n已取消清空操作")
                
            # 清空后重新运行main函数
            return main()
        
        else:
            # 尝试解析为数字，选择对应账号
            try:
                index = int(choice)
                if 1 <= index <= len(accounts):
                    selected_account = accounts[index-1]
                    selected_username = selected_account['username']
                    account_info = account_manager.get_account(selected_username)
                    
                    if not account_info:
                        print("\n❌ 获取账号信息失败！")
                        return
                        
                    selected_password = account_info['password']
                    print(f"\n已选择账号：{selected_account['nickname']} ({selected_username})")
                else:
                    print("\n❌ 无效的账号序号！")
                    return main()
            except ValueError:
                print("\n❌ 输入无效，请重新选择！")
                return main()
    else:
        print("\n未发现保存的账号，请添加新账号")
        username = input("请输入学号：").strip()
        password = input("请输入密码：").strip()
        nickname = input("请输入账号昵称（可选，直接回车使用默认）：").strip()
        
        if account_manager.add_account(username, password, nickname if nickname else None):
            print(f"\n✅ 账号 {username} 添加成功！")
        else:
            print(f"\n❌ 账号 {username} 添加失败！")
            return
            
        # 使用刚添加的账号继续
        selected_username = username
        selected_password = password
        # 标记为新添加的账号
        is_new_account = True
        # 设置初始选择为空字符串
        choice = ""
    
    # 初始化预约系统
    booking = LibraryBooking()
    
    # 使用选择的账号初始化cookie
    print("\n正在检查登录状态...")
    # 如果是新添加的账号，强制刷新cookie
    if choice.upper() == 'A' or is_new_account == False:
        if not booking.initialize_cookie(selected_username, selected_password, force_refresh=True):
            print("\033[31m[ERROR] 登录失败，程序退出\033[0m")
            return
    else:
        if not booking.initialize_cookie(selected_username, selected_password):
            print("\033[31m[ERROR] 登录失败，程序退出\033[0m")
            return
    
    while True:
        # 选择操作模式
        print("\n请选择操作：")
        print("1. 新建预约")
        print("2. 查询已有预约")
        print("3. 设置调试模式")
        print("4. 切换账号")
        print("5. 退出程序")
        operation = input("\n请输入操作编号 (1/2/3/4/5): ")
        
        if operation == "1":
            # 以下为新建预约流程
            # 输入预约日期
            date_str = input("\n请输入预约日期（格式：MMDD，例如0321）: ")
            
            # 获取房间信息
            print("\n正在获取大学城校区房间信息...")
            rooms_info = booking.get_rooms_info()
            if not rooms_info:
                print("\033[31m[ERROR] 获取房间信息失败\033[0m")
                continue
            
            # 显示所有房间
            print("\n大学城校区可用房间列表：")
            print("\n=== 普通房间 ===")
            for room_number, info in sorted(rooms_info.items(), key=lambda x: x[0]):
                if not (len(room_number) == 2 and room_number[1] in ['A', 'B', 'C']):
                    print(f"{room_number}: {info['name']} (总座位数: {info['total_seats']})")
            
            print("\n=== 走廊区域 ===")
            for room_number, info in sorted(rooms_info.items(), key=lambda x: x[0]):
                if len(room_number) == 2 and room_number[1] in ['A', 'B', 'C']:
                    print(f"{room_number[0]}楼{room_number[1]}区: {info['name']} (总座位数: {info['total_seats']})")
            
            # 输入房间号
            room_number = input("\n请输入房间号（普通房间如101、203，走廊区域如5C）: ")
            
            # 处理走廊区域的输入，转为大写处理
            if len(room_number) == 2 and room_number[1].upper() in ['A', 'B', 'C']:
                room_number = f"{room_number[0]}{room_number[1].upper()}"
            
            # 尝试在rooms_info中查找完整房间号（先尝试直接匹配，再尝试忽略大小写的匹配）
            if room_number not in rooms_info:
                # 创建大小写不敏感的房间号字典
                room_map = {k.upper(): k for k in rooms_info.keys()}
                
                # 尝试大小写不敏感的匹配
                if room_number.upper() in room_map:
                    room_number = room_map[room_number.upper()]
                # 如果没有匹配上，尝试模糊匹配
                else:
                    # 尝试查找匹配的房间
                    matching_rooms = []
                    for r in rooms_info.keys():
                        # 大小写不敏感的匹配
                        if room_number.upper() in r.upper() or r.upper() in room_number.upper():
                            matching_rooms.append(r)
                    
                    if len(matching_rooms) == 1:
                        room_number = matching_rooms[0]
                    elif len(matching_rooms) > 1:
                        print("\n找到多个匹配的房间:")
                        for i, r in enumerate(matching_rooms, 1):
                            print(f"{i}. {r}: {rooms_info[r]['name']}")
                        choice = input("\n请选择房间编号: ")
                        try:
                            room_number = matching_rooms[int(choice) - 1]
                        except (ValueError, IndexError):
                            print("\033[31m[ERROR] 无效的选择\033[0m")
                            continue
                    else:
                        print("\033[31m[ERROR] 未找到该房间号\033[0m")
                        continue
            
            room_id = rooms_info[room_number]["id"]
            
            # 获取座位信息
            print(f"\n正在获取 {rooms_info[room_number]['name']} 的座位信息...")
            seats_info = booking.get_seats_info(date_str, room_id)
            if not seats_info:
                print("\033[31m[ERROR] 获取座位信息失败\033[0m")
                continue
            
            # 选择预约模式
            print("\n请选择预约模式：")
            print("1. 常规模式 - 先选择座位，再选择时间")
            print("2. 时间优先 - 先选择时间，再查找可用座位")
            print("3. 定时预约 - 在指定时间自动预约选择的座位")
            mode = input("\n请输入模式编号 (1/2/3): ")
            
            if mode == "1":
                # 显示座位布局图
                print("\n正在生成座位布局图...")
                booking.visualize_seats(seats_info, room_id)
                
                # 输入座位号
                seat_number = input("\n请输入座位号（例如203-013）: ")
                if seat_number not in seats_info:
                    print("\033[31m[ERROR] 未找到该座位号\033[0m")
                    continue
                
                # 显示座位可用时间
                seat_info = seats_info[seat_number]
                available_times = booking.get_available_times(seat_info)
                
                print(f"\n座位 {seat_number} 的可用时间段：")
                for i, time_slot in enumerate(available_times, 1):
                    print(f"{i}. {time_slot['start']} - {time_slot['end']}")
                
                # 输入预约时间
                time_str = input("\n请输入预约时间段（格式：HH:MM-HH:MM，例如09:00-12:00）: ")
                start_time, end_time = time_str.split("-")
                start_time = start_time.strip()
                end_time = end_time.strip()
                
                # 清理可能存在的非法Unicode字符
                start_time = ''.join(char for char in start_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
                end_time = ''.join(char for char in end_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
                
                # 检查时间段是否需要拆分（超过240分钟）
                time_periods = booking.split_time_periods(start_time, end_time)
                is_split = len(time_periods) > 1
                
                if is_split:
                    print(f"\n\033[33m[提示] 您选择的时间段({start_time}-{end_time})超过4小时，将自动拆分为以下时间段：\033[0m")
                    for i, (s, e) in enumerate(time_periods, 1):
                        print(f"  {i}. {s}-{e}")
                
            elif mode == "2":
                # 先输入预约时间段
                print("\n请输入您想要预约的时间段：")
                time_str = input("格式：HH:MM-HH:MM，例如09:00-12:00: ")
                try:
                    start_time, end_time = time_str.split("-")
                    start_time = start_time.strip()
                    end_time = end_time.strip()
                    
                    # 清理可能存在的非法Unicode字符
                    start_time = ''.join(char for char in start_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
                    end_time = ''.join(char for char in end_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
                    
                    # 检查时间段是否需要拆分（超过240分钟）
                    time_periods = booking.split_time_periods(start_time, end_time)
                    is_split = len(time_periods) > 1
                    
                    if is_split:
                        print(f"\n\033[33m[提示] 您选择的时间段({start_time}-{end_time})超过4小时，将自动拆分为以下时间段：\033[0m")
                        for i, (s, e) in enumerate(time_periods, 1):
                            print(f"  {i}. {s}-{e}")
                    
                    # 显示座位布局图
                    print("\n正在生成座位布局图...")
                    booking.visualize_seats(seats_info, room_id, start_time, end_time)
                    
                    # 找出该时间段可用的座位
                    available_seats = {}
                    for seat_number, seat_info in seats_info.items():
                        if booking.check_seat_available(seat_info, start_time, end_time):
                            available_seats[seat_number] = seat_info
                    
                    # 显示可用座位
                    if not available_seats:
                        print(f"\n\033[33m[WARNING] 在 {start_time}-{end_time} 时段内没有可用座位\033[0m")
                        continue
                        
                    print(f"\n在 {start_time}-{end_time} 时段内可用的座位：")
                    available_seats_list = sorted(available_seats.keys())
                    
                    # 限制显示的座位数量，避免屏幕刷屏
                    max_display = 30
                    if len(available_seats_list) > max_display:
                        print(f"找到 {len(available_seats_list)} 个可用座位，显示前 {max_display} 个：")
                        displayed_seats = available_seats_list[:max_display]
                    else:
                        displayed_seats = available_seats_list
                        
                    # 显示可用座位列表
                    for seat_number in displayed_seats:
                        print(f"{seat_number}")
                        
                    # 选择座位
                    seat_number = input("\n请直接输入座位号（例如203-013）: ")
                    
                    # 验证座位是否在可用列表中
                    if seat_number in available_seats:
                        seat_info = available_seats[seat_number]
                    else:
                        print(f"\033[31m[ERROR] 座位 {seat_number} 不在可用座位列表中或不存在\033[0m")
                        continue
                        
                except Exception as e:
                    print(f"\033[31m[ERROR] 处理时间输入出错: {str(e)}\033[0m")
                    continue
                    
            elif mode == "3":
                # 定时预约模式
                # 选择是以座位优先还是时间优先
                print("\n请选择定时预约的方式：")
                print("1. 先选座位 - 先选择座位，再选择时间")
                print("2. 先选时间 - 先选择时间，再查找可用座位")
                auto_mode = input("\n请输入方式编号 (1/2): ")
                
                if auto_mode == "1":
                    # 显示座位布局图
                    print("\n正在生成座位布局图...")
                    booking.visualize_seats(seats_info, room_id)
                    
                    # 输入座位号
                    seat_number = input("\n请输入座位号（例如203-013）: ")
                    if seat_number not in seats_info:
                        print("\033[31m[ERROR] 未找到该座位号\033[0m")
                        continue
                    
                    # 显示座位可用时间（这里显示的是当前可用时间，实际预约时可能会变化）
                    seat_info = seats_info[seat_number]
                    available_times = booking.get_available_times(seat_info)
                    
                    print(f"\n座位 {seat_number} 的当前可用时间段：")
                    print("注意：以下时间段仅供参考，实际预约时可能已变化")
                    for i, time_slot in enumerate(available_times, 1):
                        print(f"{i}. {time_slot['start']} - {time_slot['end']}")
                    
                    # 输入预约时间
                    time_str = input("\n请输入预约时间段（格式：HH:MM-HH:MM，例如09:00-12:00）: ")
                    start_time, end_time = time_str.split("-")
                    start_time, end_time = start_time.strip(), end_time.strip()
                    
                    # 清理可能存在的非法Unicode字符
                    start_time = ''.join(char for char in start_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
                    end_time = ''.join(char for char in end_time if ord(char) < 0xD800 or ord(char) > 0xDFFF)
                    
                    # 检查时间段是否需要拆分（超过240分钟）
                    time_periods = booking.split_time_periods(start_time, end_time)
                    is_split = len(time_periods) > 1
                    
                    if is_split:
                        print(f"\n\033[33m[提示] 您选择的时间段({start_time}-{end_time})超过4小时，将自动拆分为以下时间段：\033[0m")
                        for i, (s, e) in enumerate(time_periods, 1):
                            print(f"  {i}. {s}-{e}")
                    
                elif auto_mode == "2":
                    # 先输入预约时间段
                    print("\n请输入您想要预约的时间段：")
                    time_str = input("格式：HH:MM-HH:MM，例如09:00-12:00: ")
                    try:
                        start_time, end_time = time_str.split("-")
                        start_time, end_time = start_time.strip(), end_time.strip()
                        
                        # 显示座位布局图
                        print("\n正在生成座位布局图...")
                        booking.visualize_seats(seats_info, room_id, start_time, end_time)
                        
                        # 找出该时间段可用的座位
                        available_seats = {}
                        for seat_number, seat_info in seats_info.items():
                            if booking.check_seat_available(seat_info, start_time, end_time):
                                available_seats[seat_number] = seat_info
                        
                        # 显示可用座位
                        if not available_seats:
                            print(f"\n\033[33m[WARNING] 在 {start_time}-{end_time} 时段内没有可用座位\033[0m")
                            continue
                            
                        print(f"\n在 {start_time}-{end_time} 时段内可用的座位：")
                        available_seats_list = sorted(available_seats.keys())
                        
                        # 限制显示的座位数量，避免屏幕刷屏
                        max_display = 30
                        if len(available_seats_list) > max_display:
                            print(f"找到 {len(available_seats_list)} 个可用座位，显示前 {max_display} 个：")
                            displayed_seats = available_seats_list[:max_display]
                        else:
                            displayed_seats = available_seats_list
                            
                        # 显示可用座位列表
                        for seat_number in displayed_seats:
                            print(f"{seat_number}")
                            
                        # 选择座位
                        seat_number = input("\n请直接输入座位号（例如203-013）: ")
                        
                        # 验证座位是否在可用列表中
                        if seat_number in available_seats:
                            seat_info = available_seats[seat_number]
                        else:
                            print(f"\033[31m[ERROR] 座位 {seat_number} 不在可用座位列表中或不存在\033[0m")
                            continue
                            
                    except Exception as e:
                        print(f"\033[31m[ERROR] 处理时间输入出错: {str(e)}\033[0m")
                        continue
                    else:
                        print("\033[31m[ERROR] 无效的方式选择\033[0m")
                        continue
                
                # 输入定时预约的时间
                print("\n请输入何时发送预约请求：")
                print("注意：如果当前时间已过6:15，请确保预约的是下一天的座位")
                auto_time = input("格式：HH:MM，例如06:15 表示早上6点15分: ")
                
                # 创建一个线程来处理定时预约
                thread = threading.Thread(
                    target=booking.auto_book_at_time,
                    args=(seat_info, date_str, start_time, end_time, auto_time, room_number, seats_info, room_id)
                )
                # 设置为守护线程，这样如果主程序被中断，线程也会停止
                thread.daemon = True
                thread.start()
                
                # 阻止主线程退出，等待预约线程完成
                try:
                    while thread.is_alive():
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n\033[31m程序被用户中断，定时预约取消\033[0m")
                
                # 预约完成后继续显示主菜单
                continue
                
            else:
                print("\033[31m[ERROR] 无效的模式选择\033[0m")
                continue
            
            # 提交预约请求
            if mode == "1" and is_split:
                print("\n正在提交多段预约请求...")
                all_success = True
                success_periods = []
                
                for i, (period_start, period_end) in enumerate(time_periods, 1):
                    print(f"\n提交第 {i}/{len(time_periods)} 段预约 ({period_start}-{period_end})...")
                    result = booking.make_reservation(seat_info["devId"], period_start, period_end, date_str)
                    if result and result.get("code") == 0:
                        success_periods.append((period_start, period_end))
                    else:
                        all_success = False
                
                if all_success:
                    print(f"\n\033[32m[SUCCESS] 所有时间段预约成功！\033[0m")
                elif success_periods:
                    print(f"\n\033[33m[部分成功] 以下时间段预约成功：\033[0m")
                    for i, (s, e) in enumerate(success_periods, 1):
                        print(f"  {i}. {s}-{e}")
                
                if success_periods:
                    print(f"\n预约详情：")
                    print(f"房间: {rooms_info[room_number]['name']}")
                    print(f"座位号: {seat_number}")
                    print(f"日期: {booking.year}-{date_str[:2]}-{date_str[2:]}")
                    periods_str = ", ".join([f"{s}-{e}" for s, e in success_periods])
                    print(f"时间: {periods_str}")
                    
                    # 生成签到二维码
                    print("\n正在生成签到二维码...")
                    booking.generate_checkin_qrcode(seat_info["devId"], seat_number)
            elif mode == "2" and is_split:
                print("\n正在提交多段预约请求...")
                all_success = True
                success_periods = []
                
                for i, (period_start, period_end) in enumerate(time_periods, 1):
                    print(f"\n提交第 {i}/{len(time_periods)} 段预约 ({period_start}-{period_end})...")
                    result = booking.make_reservation(seat_info["devId"], period_start, period_end, date_str)
                    if result and result.get("code") == 0:
                        success_periods.append((period_start, period_end))
                    else:
                        all_success = False
                
                if all_success:
                    print(f"\n\033[32m[SUCCESS] 所有时间段预约成功！\033[0m")
                elif success_periods:
                    print(f"\n\033[33m[部分成功] 以下时间段预约成功：\033[0m")
                    for i, (s, e) in enumerate(success_periods, 1):
                        print(f"  {i}. {s}-{e}")
                
                if success_periods:
                    print(f"\n预约详情：")
                    print(f"房间: {rooms_info[room_number]['name']}")
                    print(f"座位号: {seat_number}")
                    print(f"日期: {booking.year}-{date_str[:2]}-{date_str[2:]}")
                    periods_str = ", ".join([f"{s}-{e}" for s, e in success_periods])
                    print(f"时间: {periods_str}")
                    
                    # 生成签到二维码
                    print("\n正在生成签到二维码...")
                    booking.generate_checkin_qrcode(seat_info["devId"], seat_number)
            else:
                print("\n正在提交预约请求...")
                result = booking.make_reservation(seat_info["devId"], start_time.strip(), end_time.strip(), date_str)
                
                if result and result.get("code") == 0:
                    print(f"\n预约详情：")
                    print(f"房间: {rooms_info[room_number]['name']}")
                    print(f"座位号: {seat_number}")
                    print(f"日期: {booking.year}-{date_str[:2]}-{date_str[2:]}")
                    print(f"时间: {start_time.strip()} - {end_time.strip()}")
                    
                    # 生成签到二维码
                    print("\n正在生成签到二维码...")
                    booking.generate_checkin_qrcode(seat_info["devId"], seat_number)
                    
        elif operation == "2":
            # 查询预约模式
            print("\n正在获取预约记录...")
            reservations = booking.get_reservations()
            booking.display_reservations(reservations)
            
        elif operation == "3":
            # 设置调试模式
            print("\n调试模式设置：")
            print("1. 开启调试模式")
            print("2. 关闭调试模式")
            debug_choice = input("\n请输入选项 (1/2): ")
            
            if debug_choice == "1":
                booking.set_debug_mode(True)
                print("\n调试模式已开启，将显示详细的请求和响应信息")
            elif debug_choice == "2":
                booking.set_debug_mode(False)
                print("\n调试模式已关闭")
            else:
                print("\n无效的选择")
            
        elif operation == "4":
            # 切换账号
            print("\n请选择要切换的账号：")
            
            # 重新获取账号列表
            accounts = account_manager.list_accounts()
            account_count = account_manager.get_account_count()
            
            if account_count > 0:
                for i, account in enumerate(accounts, 1):
                    print(f"{i}. {account['nickname']} ({account['username']})")
            else:
                print("没有已保存的账号")
                continue
                
            switch_choice = input("请输入账号编号 (输入0返回): ")
            
            try:
                index = int(switch_choice)
                if index == 0:
                    continue
                
                if 1 <= index <= len(accounts):
                    selected_account = accounts[index-1]
                    selected_username = selected_account['username']
                    account_info = account_manager.get_account(selected_username)
                    
                    if not account_info:
                        print("\n❌ 获取账号信息失败！")
                        continue
                        
                    selected_password = account_info['password']
                    
                    print(f"\n已切换到账号：{selected_account['nickname']} ({selected_username})")
                    
                    # 使用新账号初始化cookie
                    print("\n正在检查登录状态...")
                    if not booking.initialize_cookie(selected_username, selected_password, force_refresh=True):
                        print("\033[31m[ERROR] 登录失败，程序退出\033[0m")
                        return
                    
                    # 使用新账号继续
                    continue
                else:
                    print("\n无效的账号编号")
                    continue
            except ValueError:
                print("\n请输入有效的数字")
                
        elif operation == "5":
            # 退出程序
            print("\n感谢使用，再见！")
            break
            
        else:
            print("\n无效的选择，请重新输入")

if __name__ == "__main__":
    main()
