import os
import json
import time
import requests
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

def login(username, password) -> (str, requests.session):
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/83.0.4103.116 Safari/537.36",
        "origin": "https://www.euserv.com"
    }
    login_data = {
        "email": username,
        "password": password,
        "form_selected_language": "en",
        "Submit": "Login",
        "subaction": "login"
    }
    url = "https://support.euserv.com/index.iphp"
    session = requests.Session()
# 先尝试无验证码登录
    resp = session.post(login_url, data=login_data)

    if "captcha" in resp.text.lower():  # 检测是否有验证码提示
    # 提取验证码图片（假设是 img src="/captcha.php?rand=xxx"，需用 BeautifulSoup 或正则提取）
    # 这里简化：假设你已获取 captcha_img_bytes = session.get(captcha_url).content
       captcha_solution = solve_captcha_with_truecaptcha(captcha_img_bytes)
    
      if captcha_solution:
          login_data['captcha'] = captcha_solution  # 字段名根据实际 HTML 可能是 'captcha_code' 等
          resp = session.post(login_url, data=login_data)  # 重新提交
        # 检查是否成功登录
          if "dashboard" in resp.url or "success" in resp.text:
              print("登录成功！")
          else:
              print("验证码可能错，再试一次...")
      else:
          print("验证码识别失败")
  else:
      print("无验证码，直接登录成功")


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
