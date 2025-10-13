import json
import time
import requests
import logs
from bs4 import BeautifulSoup
import cv2
import base64
import numpy as np
from datetime import datetime

# --- Selenium 相关库 ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# --------------------

# --- 通用变量 (保持不变) ---
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Referer": "https://elife.fudan.edu.cn/app/",
}
app_url = "https://elife.fudan.edu.cn/app/"
search_url = "https://elife.fudan.edu.cn/app/api/search.action"
# ... (其他 URL 变量保持不变)
get_reservables_url = "https://elife.fudan.edu.cn/app/api/toResourceFrame.action"
reserve_url = "https://elife.fudan.edu.cn/app/api/order/saveOrder.action?op=order"
captcha_url = "https://elife.fudan.edu.cn/public/front/getImgSwipe.htm?_="
# -------------------------

# --- 全新重写的、基于 Selenium 的 login 函数 ---
def login(username, password):
    logs.log_console("Step 1: Setting up Selenium WebDriver...", "INFO")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式, 在后台运行
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    
    s = requests.Session()
    s.headers.update(headers)

    try:
        logs.log_console("Step 2: Navigating to the app URL...", "INFO")
        driver.get(app_url)
        
        # 等待页面跳转到登录页, 并等待用户名输入框出现 (最多等待20秒)
        wait = WebDriverWait(driver, 20)
        user_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        pass_input = driver.find_element(By.ID, "password")
        
        logs.log_console("Step 3: Entering credentials...", "INFO")
        user_input.send_keys(username)
        pass_input.send_keys(password)
        
        # 点击登录按钮
        login_button = driver.find_element(By.NAME, "submit")
        login_button.click()

        # 等待登录成功并跳转回 elife 主页 (通过检查某个元素来判断)
        logs.log_console("Step 4: Waiting for successful login redirect...", "INFO")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '体育项目')]"))) # 假设主页有“体育项目”字样
        
        logs.log_console("Step 5: Transferring cookies from Selenium to Requests...", "INFO")
        # 将浏览器中的 cookie 转移到我们的 requests session 中
        selenium_cookies = driver.get_cookies()
        for cookie in selenium_cookies:
            s.cookies.set(cookie['name'], cookie['value'])

        # 检查关键的 cookie 是否存在
        if "MOD_AUTH_CAS" not in s.cookies and "JSESSIONID" not in s.cookies:
            raise Exception("Login failed, final token not found in cookies after Selenium process.")

        logs.log_console("Login process successful!", "INFO")
        return s

    except Exception as e:
        logs.log_console(f"A critical error occurred during Selenium login: {e}", "ERROR")
        driver.save_screenshot("error_screenshot.png") # 保存一张截图以供调试
        raise
    finally:
        driver.quit() # 确保浏览器被关闭

# --- 以下函数保持不变, 仅为所有网络请求添加 timeout ---
# (从 load_sports_and_campus_id 开始的所有函数都保持原样)
def load_sports_and_campus_id(s: requests.Session, service_category_id, target_campus, target_sport):
    logs.log_console("Begin Fetching Sports and Campus ID", "INFO")
    response = s.get(search_url, params={"id": service_category_id}, timeout=15)
    raw_data = json.loads(response.text)['object']['queryList']
    campuses = raw_data[0]['serviceDics']
    sports = raw_data[1]['serviceDics']
    sport_id = None
    campus_id = None
    for campus in campuses:
        if campus['value'] == target_campus:
            campus_id = campus['id']
            break
    for sport in sports:
        if sport['value'] == target_sport:
            sport_id = sport['id']
            break
    if sport_id is None or campus_id is None:
        logs.log_console("Sport or Campus ID not found", "ERROR")
        raise Exception("Sport or Campus not found")
    logs.log_console(f"Campus ID for {target_campus} is {campus_id}", "INFO")
    logs.log_console(f"Sports ID for {target_sport} is {sport_id}", "INFO")
    return campus_id, sport_id


def get_service_id(s: requests.Session, service_cat_id, campus_id, sport_id, target_sport_location):
    logs.log_console(f"Begin Fetching Service ID for {target_sport_location}", "INFO")
    response = s.get(search_url, params={"id": service_cat_id, "dicId": campus_id + ',' + sport_id}, timeout=15)
    sports_list = json.loads(response.text)['object']['pageBean']['list']
    service_id = None
    for sport in sports_list:
        if sport['publishName'] == target_sport_location:
            service_id = sport['id']
            logs.log_console(f"Service ID for {target_sport_location} is {service_id}", "INFO")
            break
    if service_id is None:
        logs.log_console("Service ID not found", "ERROR")
        raise Exception("Service ID not found")
    return service_id


def reserve(s: requests.Session, service_id, service_cat_id, target_date, target_time, USER_NAME, USER_PHONE):
    logs.log_console("Begin Loading Reservable Options List", "INFO")
    s.headers.update({"Referer": app_url, "Host": "elife.fudan.edu.cn", "Accept": "application/json, text/plain, */*"})
    response = s.get(get_reservables_url, params={"contentId": service_id,
                                                  "pageNum": "1", "pageSize": "100", "currentDate": target_date}, timeout=15)

    logs.log_console(f"Reservable Options Response {response.text}", "DEBUG")
    reservable_options_list = json.loads(response.text)['object']['page']['list']
    logs.log_console("Loading Reservable Options List Successful", "INFO")

    for reservable_option in reservable_options_list:
        if reservable_option['ifOrder'] and reservable_option['serviceTime']['beginTime'] == target_time and reservable_option['openDate'] == target_date:
            logs.log_console(f"Begin Reserving Target: {reservable_option['openDate']} {reservable_option['serviceTime']['beginTime']}", "VITAL")
            
            user_name = USER_NAME
            user_phone = USER_PHONE
            logs.log_console("Name: " + user_name + " Phone: " + user_phone, "INFO")

            logs.log_console("Begin Fetch Captcha", "INFO")
            move_X = get_and_recognize_captcha(s, captcha_url)
            response = s.post(reserve_url, data={"lastDays": 0, "orderuser": user_name,
                                                 "mobile": user_phone, "d_cgyy.bz": None,
                                                 "moveEnd_X": move_X, "wbili": 1.0,
                                                 "resourceIds": reservable_option['id'],
                                                 "serviceContent.id": service_id,
                                                 "serviceCategory.id": service_cat_id,
                                                 "orderCounts": 1}, timeout=15)
            logs.log_console(f"Reserve Response: {response.text}", "DEBUG")
            if response.status_code <= 300 and json.loads(response.text)['message'] == "操作成功！":
                logs.log_console("Reservation Successful", "VITAL")
            else:
                logs.log_console("Reservation Failed", "VITAL")
                raise Exception("Reservation Failed")
            break
        else:
            logs.log_console(f"Skipping Available Option: {reservable_option['openDate']} {reservable_option['serviceTime']['beginTime']}", "INFO")


def get_and_recognize_captcha(s,captcha_url):
    stamp = str(int(datetime.timestamp(datetime.now()) * 1000))
    full_captcha_url = captcha_url + stamp
    i = 0
    response_json = None
    while i < 6:
        try:
            response = s.get(full_captcha_url, timeout=15)
            response_json = json.loads(response.text)["object"]
            break
        except Exception as e:
            i += 1
            time.sleep(1)
            continue
    if response_json is None:
        raise Exception("Failed to fetch captcha after multiple retries")

    src_edge = image_convert(response_json["SrcImage"])
    cut_edge = image_convert(response_json["CutImage"])
    res = cv2.matchTemplate(cut_edge, src_edge, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    x = max_loc[0]
    return x

def image_convert(image):
    image = base64.b64decode(image)
    nparr = np.frombuffer(image, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    edge = cv2.Canny(img, 100, 200)
    return edge

