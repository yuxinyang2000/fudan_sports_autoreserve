import json
import time
import requests
import logs
from bs4 import BeautifulSoup
import cv2
import base64
import numpy as np
from datetime import datetime

# --- 新增的加密库 ---
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
# --------------------

# --- 通用变量 (保持不变) ---
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Referer": "https://elife.fudan.edu.cn/app/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}
get_reservables_url = "https://elife.fudan.edu.cn/app/api/toResourceFrame.action"
app_url = "https://elife.fudan.edu.cn/app/"
reserve_url = "https://elife.fudan.edu.cn/app/api/order/saveOrder.action?op=order"
captcha_url = "https://elife.fudan.edu.cn/public/front/getImgSwipe.htm?_="
order_form_url = "https://elife.fudan.edu.cn/app/api/order/loadOrderForm_ordinary.action"
search_url = "https://elife.fudan.edu.cn/app/api/search.action"
max_retry = 3
# -------------------------


# --- 全新重写的 login 函数 ---
def login(username, password):
    s = requests.Session()
    s.headers.update(headers)
    
    try:
        # 第1步: 访问应用主页, 获取正确的登录重定向URL和初始令牌
        logs.log_console("Step 1: Visiting app to get login redirect...", "DEBUG")
        initial_response = s.get(app_url, timeout=15)
        login_page_url = initial_response.url
        logs.log_console(f"Redirected to login page: {login_page_url}", "DEBUG")
        
        soup = BeautifulSoup(initial_response.text, "lxml")
        
        # --- 新增的调试步骤 ---
        # 打印脚本看到的完整HTML, 以便我们找到正确的标签
        logs.log_console("--- BEGIN LOGIN PAGE HTML ---", "DEBUG")
        logs.log_console(initial_response.text, "DEBUG")
        logs.log_console("--- END LOGIN PAGE HTML ---", "DEBUG")
        # ------------------------

        # 注意: 以下选择器是根据标准CAS登录页面的最佳猜测。
        # 如果登录失败, 最可能的原因是这些隐藏值的HTML标签或ID发生了变化。
        lok_value = soup.find('input', {'name': 'lok'}).get('value')
        authChainCode_value = soup.find('input', {'name': 'authChainCode'}).get('value')
        entityId_value = soup.find('input', {'name': 'entityId'}).get('value')
        logs.log_console(f"Found lok: {lok_value}", "DEBUG")
        logs.log_console(f"Found authChainCode: {authChainCode_value}", "DEBUG")

        # 第2步: 获取用于加密密码的公钥
        logs.log_console("Step 2: Fetching public key...", "DEBUG")
        pubkey_url = "https://id.fudan.edu.cn/dp/idp/authn/getJsPublicKey"
        pubkey_response = s.get(pubkey_url, timeout=15)
        public_key_str = "-----BEGIN PUBLIC KEY-----\n" + pubkey_response.json()['key'] + "\n-----END PUBLIC KEY-----"
        
        # 第3步: 使用公钥加密密码
        logs.log_console("Step 3: Encrypting password...", "DEBUG")
        key = RSA.import_key(public_key_str)
        cipher = PKCS1_v1_5.new(key)
        encrypted_password_bytes = cipher.encrypt(password.encode('utf-8'))
        encrypted_password_b64 = base64.b64encode(encrypted_password_bytes).decode('utf-8')
        logs.log_console(f"Password encrypted successfully.", "DEBUG")

        # 第4步: 构造最终的Payload
        final_payload = {
            "authModuleCode": "userAndPwd",
            "authChainCode": authChainCode_value,
            "authPara": {
                "loginName": username,
                "password": encrypted_password_b64,
                "verifyCode": ""
            },
            "entityId": entityId_value,
            "lok": lok_value,
            "requestType": "chain_type"
        }

        # 第5步: 发送最终的认证请求
        logs.log_console("Step 5: Sending final authentication POST...", "DEBUG")
        auth_url = "https://id.fudan.edu.cn/idp/authn/authExecute"
        auth_response = s.post(auth_url, json=final_payload, timeout=15)
        
        # 第6步 (简化处理): 检查是否登录成功
        # 完整的流程需要处理后续的一系列跳转, 但我们可以通过检查最终的Cookie来判断
        # 比如, elife 网站可能会设置一个名为 MOD_AUTH_CAS 的cookie
        if "MOD_AUTH_CAS" not in s.cookies and "JSESSIONID" not in s.cookies :
             logs.log_console(f"Login failed. Response from authExecute: {auth_response.text}", "ERROR")
             raise Exception("Login failed, final token not found in cookies.")

        logs.log_console("Login process successful!", "INFO")
        return s

    except Exception as e:
        logs.log_console(f"A critical error occurred during login: {e}", "ERROR")
        raise


# --- 以下函数保持不变, 仅为所有网络请求添加 timeout ---

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

