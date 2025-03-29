import logging
import urllib3
import requests
import random
import time
import urllib.parse
from encryption import str_enc
from datetime import datetime, timedelta
import os
import json
from bs4 import BeautifulSoup

def getCookieWithDirectLogin(username, password):
    """直接HTTP登录方式获取cookie，无需打开浏览器"""
    try:
        # 禁用SSL警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 创建会话
        session = requests.Session()
        
        # 随机化User-Agent以避免被检测
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]
        
        random_ua = random.choice(user_agents)

        # 设置基本请求头
        headers = {
            "User-Agent": random_ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "http://libbooking.gzhu.edu.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
        session.headers.update(headers)
        
        print("开始尝试直接登录...")
        
        # 步骤1: 访问图书馆主页获取初始Cookie
        library_url = "http://libbooking.gzhu.edu.cn"
        response = session.get(library_url, verify=False)
        print(f"图书馆主页响应状态码: {response.status_code}")
        
        # 添加一个小延迟，防止服务器风控了
        time.sleep(random.uniform(1, 2))
        
        # 最大重试次数
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 步骤2: 调用auth/address接口获取重定向URL
                print(f"步骤2: 调用auth/address接口获取重定向URL (尝试 {retry_count+1}/{max_retries})...")
                auth_address_url = "http://libbooking.gzhu.edu.cn/ic-web/auth/address"
                
                # 添加必要的查询参数
                params = {
                    "finalAddress": "https://libbooking.gzhu.edu.cn/scancode.html#/transferPage?sta=1&sysid=1EW&lab=12&dev=100586871&msn=c9115f6e-f384-4641-a66b-e0982031239c",
                    "errPageUrl": "https://libbooking.gzhu.edu.cn/scancode.html#/error",
                    "manager": "false",
                    "consoleType": "16"
                }
                
                response = session.get(auth_address_url, params=params, verify=False)
                print(f"auth/address接口响应状态码: {response.status_code}")
                
                redirect_data = response.json()
                print(f"auth/address接口响应: {redirect_data}")
                
                if redirect_data.get("code") == 0 and redirect_data.get("data"):
                    redirect_url = redirect_data.get("data")
                    print(f"获取到重定向URL: {redirect_url}")
                    break  # 成功获取重定向URL，退出重试循环
                else:
                    print(f"接口返回错误: {redirect_data.get('message')}")
                    retry_count += 1
                    if retry_count < max_retries:
                        delay = random.uniform(3, 5)  # 增加随机延迟
                        print(f"等待 {delay:.1f} 秒后重试...")
                        time.sleep(delay)
                    else:
                        print("❌ 无法从auth/address接口获取重定向URL")
                        return None
            except Exception as e:
                print(f"调用auth/address接口出错: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    delay = random.uniform(3, 5)
                    print(f"等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                else:
                    print("❌ 调用auth/address接口失败")
                    return None
        
        # 检查是否成功获取重定向URL
        if not redirect_url:
            print("❌ 未能获取重定向URL")
            return None
            
        # 添加一个小延迟
        time.sleep(random.uniform(1, 2))
        
        # 步骤3: 访问重定向URL触发CAS跳转
        print("步骤3: 访问重定向URL触发CAS跳转...")
        response = session.get(redirect_url, verify=False, allow_redirects=False)
        print(f"重定向响应状态码: {response.status_code}")
        
        # 获取CAS登录URL
        cas_url = response.headers.get('Location')
        if not cas_url:
            print("❌ 未获取到CAS登录URL")
            return None
            
        print(f"成功获取CAS登录URL: {cas_url}")
        
        # 解析service参数
        if 'service=' in cas_url:
            service_param = cas_url.split('service=')[1]
            # 记住原始service参数，后面会用到
            original_service = urllib.parse.unquote(service_param)  # 使用正确的模块
            print(f"原始service参数: {original_service}")
        else:
            print("⚠️ 未在CAS URL中找到service参数")
            original_service = "http://libbooking.gzhu.edu.cn/authcenter/doAuth"
        
        # 添加一个小延迟
        time.sleep(random.uniform(1, 2))
        
        # 步骤4: 获取CAS登录页面
        print("步骤4: 获取CAS登录页面...")
        response = session.get(cas_url, verify=False)
        print(f"CAS页面响应状态码: {response.status_code}")
        
        # 解析登录页面，提取表单参数
        soup = BeautifulSoup(response.text, 'html.parser')
        lt_element = soup.find('input', {'id': 'lt'})
        execution_element = soup.find('input', {'name': 'execution'})
        
        lt = lt_element['value'] if lt_element else None
        execution = execution_element['value'] if execution_element else None
        
        if not lt or not execution:
            print(f"❌ 未能获取必要的登录参数: lt={lt}, execution={execution}")
            return None
            
        print(f"获取到lt参数: {lt}")
        print(f"获取到execution参数: {execution}")
        
        # 添加一个小延迟
        time.sleep(random.uniform(1, 2))
        
        # 步骤5: 准备登录数据
        print("步骤5: 准备登录数据...")
        # 构造加密内容
        combined = username + password + lt
        print(f"加密内容长度: {len(combined)}")
        
        # DES加密
        encrypted = str_enc(combined, "1", "2", "3")
        
        # 构造登录表单数据
        login_data = {
            'rsa': encrypted,
            'ul': len(username),
            'pl': len(password),
            'lt': lt,
            'execution': execution,
            '_eventId': 'submit'
        }
        
        # 步骤6: 提交登录表单
        print("步骤6: 提交登录表单...")
        login_response = session.post(cas_url, data=login_data, verify=False, allow_redirects=False)
        print(f"登录响应状态码: {login_response.status_code}")
        
        # 检查是否有重定向
        if 300 <= login_response.status_code < 400:
            redirect_url = login_response.headers.get('Location')
            print(f"获取到重定向URL: {redirect_url}")
            
            if redirect_url and "ticket=" in redirect_url:
                # 获取ticket参数
                ticket = redirect_url.split("ticket=")[1]
                print(f"获取到CAS票据: {ticket}")
                
                # 构建正确的服务URL
                if original_service.startswith("http"):
                    correct_url = original_service
                    if "?" in correct_url:
                        correct_url += "&ticket=" + ticket
                    else:
                        correct_url += "?ticket=" + ticket
                else:
                    # 如果original_service不是完整URL，构建一个
                    correct_url = f"http://libbooking.gzhu.edu.cn{original_service}"
                    if "?" in correct_url:
                        correct_url += "&ticket=" + ticket
                    else:
                        correct_url += "?ticket=" + ticket
                
                print(f"构建的验证URL: {correct_url}")
                
                # 添加一个小延迟
                time.sleep(random.uniform(1, 2))
                
                # 步骤7: 访问正确的带ticket的URL
                print("步骤7: 访问票据验证URL...")
                ticket_response = session.get(correct_url, verify=False, allow_redirects=True)
                print(f"票据验证响应状态码: {ticket_response.status_code}")
                print(f"票据验证后URL: {ticket_response.url}")
                
                # 添加一个小延迟
                time.sleep(random.uniform(1, 2))
                
                # 步骤8: 访问首页确认登录成功
                print("步骤8: 访问首页确认登录成功...")
                final_url = "https://libbooking.gzhu.edu.cn/#/ic/home"
                final_response = session.get(final_url, verify=False)
                print(f"首页响应状态码: {final_response.status_code}")
                
                # 获取最终cookies
                cookies = session.cookies.get_dict()
                print(f"最终cookies: {cookies}")
                
                # 转换cookies为字符串格式
                cookie_str = '; '.join([f"{key}={value}" for key, value in cookies.items()])
                
                # 检查是否成功获取到cookie
                if cookies:
                    print("✅ 登录成功，已获取到有效cookie")
                    
                    # 尝试访问预约信息API验证cookie有效性
                    print("步骤10: 验证cookie有效性...")
                    try:
                        # 计算查询日期范围（前一天到后一天）
                        today = datetime.now()
                        begin_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                        end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
                        
                        # 构建请求参数，完全模拟get_reservations的方式
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
                        check_response = session.get(check_url, params=params, verify=False)
                        
                        if check_response.status_code == 200:
                            try:
                                check_data = check_response.json()
                                if check_data.get("code") == 0:
                                    print("✅ Cookie验证成功：能够获取预约信息")
                                    # 打印预约数量
                                    if "data" in check_data:
                                        reservations_count = len(check_data["data"])
                                        print(f"找到 {reservations_count} 条预约记录")
                                else:
                                    print(f"⚠️ Cookie可能无效: {check_data.get('message')}")
                            except Exception as e:
                                print(f"⚠️ 无法解析预约信息响应: {str(e)}")
                        else:
                            print(f"⚠️ 预约信息请求失败: {check_response.status_code}")
                            print(f"响应内容: {check_response.text[:200]}...")
                    except Exception as e:
                        print(f"⚠️ 验证cookie时出错: {str(e)}")
                    
                    return cookie_str
                else:
                    print("❌ 未能获取有效cookie")
                    return None
            else:
                print("❌ 登录重定向URL中没有ticket参数")
        else:
            print(f"❌ 登录请求失败: {login_response.status_code}")
        
        return None
    
    except Exception as e:
        print(f"登录过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def getCookieWithCASLogin(login_url, username, password):
    """
    使用 Selenium 自动化登录，并提取登录后的 Cookie。
    
    Args:
        login_url (str): 登录页面的 URL
        username (str): 用户名
        password (str): 密码
    
    Returns:
        str: 格式化后的 Cookie 字符串
    """
    # 在函数内部导入selenium，以便只有在需要时才导入
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
    except ImportError:
        print("\033[31m[错误] 未安装selenium库。请使用pip install selenium安装，或使用直接登录方式。\033[0m")
        return None
    
    # 将getWebDriver函数移到函数内部
    def getWebDriver():
        """
        初始化并返回WebDriver实例
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")  # 窗口最大化
        options.add_argument("--headless")  # 启用无头模式
        options.add_argument("--disable-gpu")  # 针对某些系统的 GPU 问题
        options.add_argument("--window-size=1920,1080")  # 设置窗口大小
        return webdriver.Chrome(options=options)
    
    driver = getWebDriver()
    wait = WebDriverWait(driver, 30)  # 设置显式等待时间为30秒
    
    try:
        # 打开登录页面
        driver.get(login_url)
        print("\033[32m[TIPS] 浏览器已运行, 正在填充账号密码...\033[0m")
        
        # 等待用户名输入框加载
        username_field = wait.until(EC.presence_of_element_located((By.ID, "un")))
        password_field = driver.find_element(By.ID, "pd")
        login_button = driver.find_element(By.ID, "index_login_btn")
        
        # 输入用户名和密码
        username_field.clear()
        username_field.send_keys(username)
        password_field.clear()
        password_field.send_keys(password)
        
        # 点击登录按钮
        login_button.click()
        print("[INFO] 已提交登录表单，等待登录完成...")
        
        # 使用新的登录成功标识进行检测
        try:
            success_element = wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "el-submenu__title"))
            )
            print("\033[32m[INFO] 登录成功！\033[0m")
        except TimeoutException:
            print(f"[INFO] 检测到可能需要手动验证。请在浏览器中完成任何额外的登录步骤，然后按 Enter 键继续...")
            input()
            # 重新检测登录状态
            try:
                success_element = wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "el-submenu__title"))
                )
                print("\033[32m[INFO] 登录成功！\033[0m")
            except TimeoutException:
                print(f"[ERROR] 登录过程超时, 登录失败, 请检查网络或登录信息")
                return None

        # 提取所有 Cookie
        cookies = driver.get_cookies()
        print(f"[INFO] 获取到 {len(cookies)} 个 Cookie。")
        print(f"{cookies}")
        
        # 格式化 Cookie
        cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
        print("\033[32m[SUCCESS] 成功获取登录后的 Cookie\033[0m")
        
    except Exception as e:
        logging.error(f"获取 Cookie 过程中出错: {e}")
        cookie_str = ""
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"关闭浏览器时出错: {e}")

    return cookie_str

if __name__ == "__main__":
    # 使用示例
    login_url = "http://libbooking.gzhu.edu.cn"
    username = "32x0xxxxxx"
    password = "xxxxxx"
    
    cookie = getCookieWithCASLogin(login_url, username, password)
    if cookie:
        print("获取到的Cookie:", cookie)

class CookieManager:
    def __init__(self, cookie_file="cookie.json"):
        """初始化CookieManager，指定cookie文件路径"""
        self.cookie_file = cookie_file
        self.cookie_lifetime = timedelta(hours=1)  # cookie有效期为1小时
    
    def save_cookie(self, cookie, username, password=None):
        """保存cookie及用户名密码到文件
        
        Args:
            cookie: cookie字符串
            username: 用户名
            password: 密码 (可选)
        """
        # 创建包含cookie、用户名和时间戳的字典
        cookie_data = {
            "cookie": cookie,
            "username": username,
            "timestamp": datetime.now().timestamp(),  # 记录保存时间
        }
        
        # 如果提供了密码，也保存密码
        if password:
            cookie_data["password"] = password
        
        # 将数据写入文件
        try:
            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f)
            return True
        except Exception as e:
            print(f"保存cookie失败: {str(e)}")
            return False
    
    def load_cookie(self):
        """从文件加载cookie
        
        Returns:
            如果文件存在并且cookie未过期，返回cookie数据字典
            否则返回None
        """
        if not os.path.exists(self.cookie_file):
            return None
        
        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)
            
            # 返回cookie数据
            return cookie_data
        except Exception as e:
            print(f"加载cookie失败: {str(e)}")
            return None
    
    def is_cookie_expired(self, cookie_data):
        """检查cookie是否已过期
        
        Args:
            cookie_data: cookie数据字典，包含timestamp字段
            
        Returns:
            如果cookie已过期，返回True，否则返回False
        """
        if not cookie_data or "timestamp" not in cookie_data:
            return True
        
        # 获取cookie保存时间
        timestamp = cookie_data["timestamp"]
        save_time = datetime.fromtimestamp(timestamp)
        
        # 检查是否已超过有效期
        return datetime.now() - save_time > self.cookie_lifetime
    
    def clear_cookie(self):
        """清除保存的cookie文件"""
        if os.path.exists(self.cookie_file):
            try:
                os.remove(self.cookie_file)
                return True
            except Exception as e:
                print(f"清除cookie失败: {str(e)}")
                return False
        return True

class AccountManager:
    def __init__(self, accounts_file="accounts.json"):
        """初始化AccountManager，指定账号文件路径"""
        self.accounts_file = accounts_file
        self.accounts = self.load_accounts()
        
    def load_accounts(self):
        """从文件加载所有账号"""
        if not os.path.exists(self.accounts_file):
            return {}
        
        try:
            with open(self.accounts_file, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
            return accounts
        except Exception as e:
            print(f"加载账号失败: {str(e)}")
            return {}
    
    def save_accounts(self):
        """保存账号信息到文件"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(self.accounts, f)
            return True
        except Exception as e:
            print(f"保存账号失败: {str(e)}")
            return False
    
    def add_account(self, username, password, nickname=None):
        """添加新账号
        
        Args:
            username: 用户名/学号
            password: 密码
            nickname: 账号昵称（可选）
        
        Returns:
            成功返回True，失败返回False
        """
        if not nickname:
            nickname = f"账号_{username[-4:]}"  # 使用学号后4位作为默认昵称
            
        self.accounts[username] = {
            "username": username,
            "password": password,
            "nickname": nickname,
            "created_at": datetime.now().timestamp()
        }
        
        return self.save_accounts()
    
    def remove_account(self, username):
        """删除账号
        
        Args:
            username: 要删除的账号用户名
            
        Returns:
            成功返回True，失败返回False
        """
        if username in self.accounts:
            del self.accounts[username]
            return self.save_accounts()
        return False
    
    def get_account(self, username):
        """获取指定账号信息
        
        Args:
            username: 账号用户名
            
        Returns:
            账号信息字典，不存在返回None
        """
        return self.accounts.get(username)
    
    def list_accounts(self):
        """列出所有账号
        
        Returns:
            账号信息列表
        """
        result = []
        for username, info in self.accounts.items():
            result.append({
                "username": username,
                "nickname": info.get("nickname", f"账号_{username[-4:]}"),
                "created_at": datetime.fromtimestamp(info.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
            })
        return result

    def get_account_count(self):
        """获取账号数量"""
        return len(self.accounts) 