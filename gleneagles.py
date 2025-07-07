import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

BASE_URL = "https://w.cps.golf/WestVancouverV3/Home/nIndex?CourseId=1&Date={date}&Time=AnyTime&Player=99&Hole=9"

# 设置调试输出
def debug_log(message):
    print(f"[DEBUG] {message}")

##新增逻辑读取googlesheet
import gspread
import json
from google.oauth2.service_account import Credentials

## 获取 Google Sheet 中用户配置
def load_user_preferences():
    #scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    # ⚠️ 请确保先定义 scopes
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly"
    ]

    # 从环境变量中读取 JSON 字符串（必须是 GitHub Secret 中设置的内容）
    credentials_file = "teetime-465103-5096aca64eb6.json"
    if not os.path.exists(credentials_file):
        raise ValueError("❌ Credentials JSON file not found.")
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)    

    # 解析 JSON 字符串为字典
    #info = json.loads(credentials_json_str)
    # 创建 credentials 对象
    #creds = Credentials.from_service_account_info(info, scopes=scopes)

    gc = gspread.authorize(creds)
    sh = gc.open("teetime")  # 表格文件名
    worksheet = sh.sheet1     # 第一张表（即表单响应汇总）

    records = worksheet.get_all_records()
    user_prefs = []
    for row in records:
        email = row.get("邮箱地址", "").strip()
        watch_days = row.get("监控日期", "").strip()
        start_time = row.get("监控开始时间", "").strip()
        end_time = row.get("监控结束时间", "").strip()
        if email and start_time and end_time:
            user_prefs.append({
                "email": email,
                "days": watch_days,
                "start": start_time,
                "end": end_time
            })
    return user_prefs

## 判断该 tee time 是否在用户设定时间范围
def is_time_in_range(tee_time, start_str, end_str):
    fmt = "%H:%M"
    try:
        tee = datetime.strptime(tee_time, fmt).time()
        start = datetime.strptime(start_str, fmt).time()
        end = datetime.strptime(end_str, fmt).time()
        return start <= tee <= end
    except Exception:
        return False

## 判断是否满足用户设置的日期范围
def is_day_match(date_obj, watch_days):
    weekday = date_obj.weekday()
    if watch_days == "每天":
        return True
    elif watch_days == "工作日":
        return weekday < 5
    elif watch_days == "周末":
        return weekday >= 5
    return False

def is_target_time_in_range(t_str, start_time_str, end_time_str):
    try:
        def parse_time(s):
            s = s.strip().upper()
            if "AM" in s or "PM" in s:
                return datetime.strptime(s, "%I:%M %p").time()
            else:
                return datetime.strptime(s, "%H:%M").time()

        t = parse_time(t_str)
        start = parse_time(start_time_str)
        end = parse_time(end_time_str)
        return start <= t <= end
    except Exception as e:
        debug_log(f"[TimeParseError] Failed to parse time '{t_str}' or range ({start_time_str}-{end_time_str}): {e}")
        return False

import requests

GIST_ID = os.getenv("GIST_ID")
GIST_TOKEN = os.getenv("GIST_TOKEN")

def get_user_gist_filename(email):
    sanitized = email.replace("@", "_at_").replace(".", "_dot_")
    return f"last_result_{sanitized}.txt"

def load_last_result_from_gist(email):
    filename = get_user_gist_filename(email)
    try:
        headers = {
            "Authorization": f"Bearer {GIST_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        url = f"https://api.github.com/gists/{GIST_ID}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            files = response.json().get("files", {})
            content = files.get(filename, {}).get("content", "")
            return content.strip()
        else:
            debug_log(f"[Gist] Error loading {filename}: {response.status_code}")
    except Exception as e:
        debug_log(f"[Gist] ⚠️ 异常: {e}")
    return ""

def save_result_to_gist(email, content):
    filename = get_user_gist_filename(email)
    try:
        headers = {
            "Authorization": f"Bearer {GIST_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        data = {
            "files": {
                filename: {
                    "content": content
                }
            }
        }
        response = requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=headers, json=data)
        if response.status_code == 200:
            debug_log(f"Gist updated for {email}.")
        else:
            debug_log(f"Failed to update Gist for {email}: {response.status_code}")
    except Exception as e:
        debug_log(f"Error saving Gist for {email}: {e}")
        
# 抓取一个日期的数据
def check_tee_times():
    user_prefs = load_user_preferences()

    if not user_prefs:
        debug_log("❌ 无用户设置，跳过抓取")
        return

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    today = datetime.today()
    all_matched = {}  # email => [lines]

    for offset in range(1, 8):  # 次日到+8天
        target_date = today + timedelta(days=offset)
        date_str = target_date.strftime("%Y-%-m-%-d")
        url = BASE_URL.format(date=date_str)
        debug_log(f"Checking {date_str} ... URL: {url}")

        driver.get(url)
        time.sleep(5)  # 确保加载完页面

        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "div.teetime")
            debug_log(f"Found {len(rows)} rows on {date_str}")

            for row in rows:
                try:
                    time_el = row.find_element(By.CSS_SELECTOR, "h3.timeDiv span")
                    t_str = time_el.text.strip()
                    player_info_el = row.find_element(By.CSS_SELECTOR, "div.player p")
                    player_info = player_info_el.text.strip()

                    for user in user_prefs:
                        if not is_day_match(target_date, user["days"]):
                            continue
                        if not is_target_time_in_range(t_str, user["start"], user["end"]):
                            continue
                        if "4" not in player_info and "2 - 4" not in player_info:
                            continue
                        line = f"{date_str} {t_str} - {player_info}"
                        all_matched.setdefault(user["email"], []).append(line)
                except Exception as e:
                    debug_log(f"Failed to parse a row: {e}")
        except Exception as e:
            debug_log(f"Error fetching tee times for {date_str}: {e}")

    driver.quit()
    
    for user in user_prefs:
        email = user["email"]
        slots = all_matched.get(email, [])

        if not slots:
            continue

        last_message = load_last_result_from_gist(email)
        last_lines = set(last_message.strip().splitlines()) if last_message else set()

        message_lines = []
        new_lines = []

        for line in slots:
            date_part = line.split(" ")[0]
            url = BASE_URL.format(date=date_part)
            if line not in last_lines:
                line_with_link = f'<span style="color:red">{line}</span> <a href="{url}">去预订</a>'
                new_lines.append(line)
            else:
                line_with_link = f'{line} <a href="{url}">去预订</a>'
            message_lines.append(line_with_link)

        if message_lines:
            message_html = "<br>".join(message_lines)
            debug_log(f"[邮件] 给 {email} 发送：\n{message_html}")
            send_email(message_html, [email])

        # 仅当有新内容才更新 gist
        if new_lines:
            combined = sorted(set(last_lines | set(slots)))
            save_result_to_gist(email, "\n".join(combined))
            debug_log(f"[Gist] 更新 {email} 的历史记录")
        else:
            debug_log(f"[Gist] {email} 没有新 tee time，跳过更新")

# 发邮件
def send_email(content, receivers):
    msg = MIMEText(content, "html")
    msg["Subject"] = "Gleneagles Tee Time Reminder"
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(receivers)

    with smtplib.SMTP_SSL("smtp.126.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, receivers, msg.as_string())

if __name__ == "__main__":
    check_tee_times()
