import os
import json
import time
import requests
import base64
from bs4 import BeautifulSoup

USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]
TRUECAPTCHA_USERNAME = os.environ["TRUECAPTCHA_USERNAME"]
TRUECAPTCHA_APIKEY   = os.environ["TRUECAPTCHA_APIKEY"]
PROXIES = {
    "http": "http://127.0.0.1:10809",
    "https": "http://127.0.0.1:10809"
}

def solve_captcha_with_truecaptcha(captcha_image_content):
    """发送 base64 图片到 TrueCaptcha API"""
    base64_img = base64.b64encode(captcha_image_content).decode('utf-8')
    
    url = "https://api.apitruecaptcha.org/one/gettext"
    payload = {
        "username": TRUECAPTCHA_USERNAME,
        "apikey": TRUECAPTCHA_APIKEY,
        "data": base64_img,          # base64 字符串（无 data:image 前缀）
        "case": "mixed"              # EUserv 验证码通常大小写混合，可试 "upper" 或 "lower"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        
        if "result" in result and result.get("status") == "success":
            captcha_text = result["result"]
            print(f"TrueCaptcha 识别成功: {captcha_text}")
            return captcha_text
        else:
            print("TrueCaptcha 错误:", result.get("message", "未知错误"))
            return None
    except Exception as e:
        print("TrueCaptcha 请求失败:", str(e))
        return None

import base64  # 别忘了在文件开头导入 base64（你用了但没 import）

def login(username, password):
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/83.0.4103.116 Safari/537.36",
        "origin": "https://www.euserv.com"
    }
    
    login_data = {
        "email": username,                  # 注意：EUserv 登录用 "email" 而不是 "username"
        "password": password,
        "form_selected_language": "en",
        "Submit": "Login",
        "subaction": "login"
    }
    
    url = "https://support.euserv.com/index.iphp"  # 正确的登录 POST 地址
    
    session = requests.Session()
    
    # 第一次尝试登录（可能无验证码或有）
    resp = session.post(url, data=login_data, headers=headers)
    
    # 检查是否需要验证码（根据历史脚本和常见模式，通常包含 "captcha" 字样或特定 class）
    if "captcha" in resp.text.lower() or "verify" in resp.text.lower():
        print("检测到验证码，尝试自动识别...")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 尝试找到验证码图片（常见几种写法，根据 2021-2025 脚本经验）
        captcha_img_tag = soup.find('img', {'id': 'captcha'}) or \
                          soup.find('img', {'class': 'captcha'}) or \
                          soup.find('img', src=lambda s: s and 'captcha' in s)
        
        if captcha_img_tag and 'src' in captcha_img_tag.attrs:
            captcha_src = captcha_img_tag['src']
            # 补全相对路径
            if captcha_src.startswith('/'):
                captcha_url = "https://support.euserv.com" + captcha_src
            elif not captcha_src.startswith('http'):
                captcha_url = url.rsplit('/', 1)[0] + '/' + captcha_src
            else:
                captcha_url = captcha_src
            
            try:
                img_resp = session.get(captcha_url, headers=headers)
                img_resp.raise_for_status()
                captcha_img_bytes = img_resp.content
                
                captcha_solution = solve_captcha_with_truecaptcha(captcha_img_bytes)
                
                if captcha_solution:
                    # EUserv 验证码字段名通常是 "captcha" 或 "captcha_code"（根据多个老脚本）
                    login_data['captcha'] = captcha_solution.strip()  # 去除可能的空格
                    
                    # 重新提交登录（带验证码）
                    resp = session.post(url, data=login_data, headers=headers)
                    
                    # 再次检查是否成功（简单判断：看是否跳转或有欢迎词）
                    if "dashboard" in resp.url or "welcome" in resp.text.lower() or "my services" in resp.text.lower():
                        print("验证码正确，登录成功！")
                    else:
                        print("验证码可能识别错误或登录仍失败，再试一次可能需要重跑脚本")
                        return None, None  # 失败返回 None
                else:
                    print("TrueCaptcha 识别失败")
                    return None, None
            except Exception as e:
                print(f"获取/识别验证码失败: {e}")
                return None, None
        else:
            print("未在响应中找到验证码图片标签")
            return None, None
    else:
        print("无验证码，直接登录成功")
    
    # 登录成功后，从 cookie 或页面提取 sess_id（常见方式）
    # EUserv 通常把 sess_id 放在 URL 参数或 cookie 中
    # 这里简单从重定向或当前 URL 取（实际可优化）
    sess_id = None
    if 'sess_id' in resp.url:
        sess_id = resp.url.split('sess_id=')[1].split('&')[0]
    elif 'sess_id' in session.cookies:
        sess_id = session.cookies.get('sess_id')
    
    if not sess_id:
        # 备选：从页面 HTML 提取（常见 <input type="hidden" name="sess_id" value="xxx">）
        soup = BeautifulSoup(resp.text, 'html.parser')
        hidden_sess = soup.find('input', {'name': 'sess_id'})
        if hidden_sess:
            sess_id = hidden_sess['value']
    
    if sess_id:
        print(f"获取到 sess_id: {sess_id}")
        return sess_id, session
    else:
        print("登录成功但未能提取 sess_id，请检查")
        return None, session

def get_servers(sess_id, session) -> {}:
    d = {}
    url = "https://support.euserv.com/index.iphp?sess_id=" + sess_id
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/83.0.4103.116 Safari/537.36",
        "origin": "https://www.euserv.com"
    }
    f = session.get(url=url, headers=headers)
    f.raise_for_status()
    soup = BeautifulSoup(f.text, 'html.parser')
    for tr in soup.select('#kc2_order_customer_orders_tab_content_1 .kc2_order_table.kc2_content_table tr'):
        server_id = tr.select('.td-z1-sp1-kc')
        if not len(server_id) == 1:
            continue
        flag = True if tr.select('.td-z1-sp2-kc .kc2_order_action_container')[
                           0].get_text().find('Contract extension possible from') == -1 else False
        d[server_id[0].get_text()] = flag
    return d


def renew(sess_id, session, password, order_id) -> bool:
    url = "https://support.euserv.com/index.iphp"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/83.0.4103.116 Safari/537.36",
        "Host": "support.euserv.com",
        "origin": "https://support.euserv.com",
        "Referer": "https://support.euserv.com/index.iphp"
    }
    data = {
        "Submit": "Extend contract",
        "sess_id": sess_id,
        "ord_no": order_id,
        "subaction": "choose_order",
        "choose_order_subaction": "show_contract_details"
    }
    session.post(url, headers=headers, data=data)
    data = {
        "sess_id": sess_id,
        "subaction": "kc2_security_password_get_token",
        "prefix": "kc2_customer_contract_details_extend_contract_",
        "password": password
    }
    f = session.post(url, headers=headers, data=data)
    f.raise_for_status()
    if not json.loads(f.text)["rs"] == "success":
        return False
    token = json.loads(f.text)["token"]["value"]
    data = {
        "sess_id": sess_id,
        "ord_id": order_id,
        "subaction": "kc2_customer_contract_details_extend_contract_term",
        "token": token
    }
    session.post(url, headers=headers, data=data)
    time.sleep(5)
    return True


def check(sess_id, session):
    print("Checking.......")
    d = get_servers(sess_id, session)
    flag = True
    for key, val in d.items():
        if val:
            flag = False
            print("ServerID: %s Renew Failed!" % key)
    if flag:
        print("ALL Work Done! Enjoy")


if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("你没有添加任何账户")
        exit(1)
    user_list = USERNAME.split(',')
    passwd_list = PASSWORD.split(',')
    if len(user_list) != len(passwd_list):
        print("The number of usernames and passwords do not match!")
        exit(1)
    for i in range(len(user_list)):
        print('*' * 30)
        print("正在续费第 %d 个账号" % (i + 1))
        sessid, s = login(user_list[i], passwd_list[i])
        if sessid == '-1':
            print("第 %d 个账号登陆失败，请检查登录信息" % (i + 1))
            continue
        SERVERS = get_servers(sessid, s)
        print("检测到第 {} 个账号有 {} 台VPS，正在尝试续期".format(i + 1, len(SERVERS)))
        for k, v in SERVERS.items():
            if v:
                if not renew(sessid, s, passwd_list[i], k):
                    print("ServerID: %s Renew Error!" % k)
                else:
                    print("ServerID: %s has been successfully renewed!" % k)
            else:
                print("ServerID: %s does not need to be renewed" % k)
        time.sleep(15)
        check(sessid, s)
        time.sleep(5)
    print('*' * 30)
