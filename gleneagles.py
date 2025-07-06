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
from google.oauth2.service_account import Credentials

## 获取 Google Sheet 中用户配置
def load_user_preferences():
    credentials_file = "teetime-465103-5096aca64eb6.json"  # 文件名保持和 GitHub Secret 上传一致
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)

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

def load_last_result_from_gist():
    try:
        headers = {
            "Authorization": f"Bearer {GIST_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        url = f"https://api.github.com/gists/{GIST_ID}"
        debug_log(f"[Gist] Fetching Gist from: {url}")
        debug_log(f"[Gist] Using Token (first 6 chars): {GIST_TOKEN[:6]}...")

        response = requests.get(url, headers=headers)

        debug_log(f"[Gist] Status Code: {response.status_code}")
        debug_log(f"[Gist] Response Text: {response.text[:200]}...")  # 只显示前200字避免太长

        if response.status_code == 200:
            files = response.json().get("files", {})
            content = files.get("last_result.txt", {}).get("content", "")
            return content.strip()
        elif response.status_code == 401:
            debug_log("[Gist] ❌ Unauthorized (401): Token 无效或权限不足")
        elif response.status_code == 404:
            debug_log("[Gist] ❌ Not Found (404): Gist ID 不存在或你无权访问")
        else:
            debug_log(f"[Gist] ⚠️ 未知错误: {response.status_code}")
    except Exception as e:
        debug_log(f"[Gist] ⚠️ 异常: {e}")
    return ""

def save_result_to_gist(content):
    try:
        headers = {
            "Authorization": f"Bearer {GIST_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        data = {
            "files": {
                "last_result.txt": {
                    "content": content
                }
            }
        }
        response = requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=headers, json=data)
        if response.status_code == 200:
            debug_log("Gist updated successfully.")
        else:
            debug_log(f"Failed to update Gist: {response.status_code}")
    except Exception as e:
        debug_log(f"Error saving Gist: {e}")

# 抓取一个日期的数据
# 抓取一个日期的数据
def check_tee_times():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    found_slots = []

    today = datetime.today()
    for offset in range(1, 8):  # 次日到+8天
        target_date = today + timedelta(days=offset)
        # ➤ 只处理周一到周五
        if target_date.weekday() > 4:
            debug_log(f"Skipping {target_date.strftime('%Y-%-m-%-d')} (Weekend)")
            continue

        date_str = target_date.strftime("%Y-%-m-%-d")
        url = BASE_URL.format(date=date_str)
        debug_log(f"Checking {date_str} ... URL: {url}")

        driver.get(url)
        time.sleep(5)  # 确保加载完页面

        try:
            # 每一个 tee time 都是一个 div.teetime
            rows = driver.find_elements(By.CSS_SELECTOR, "div.teetime")
            debug_log(f"Found {len(rows)} rows on {date_str}")
            for row in rows:
                try:
                    # 读取时间
                    time_el = row.find_element(By.CSS_SELECTOR, "h3.timeDiv span")
                    t_str = time_el.text.strip()

                    # 读取人数（如 Single Only 或 2 - 4 players）
                    player_info_el = row.find_element(By.CSS_SELECTOR, "div.player p")
                    player_info = player_info_el.text.strip()

                    debug_log(f"Raw time: {t_str}, Players: {player_info}")

                    # 判断是否符合时间要求，且至少有“4”这个关键词（可以调整逻辑）
                    if ("4" in player_info or "2 - 4" in player_info) and is_target_time(t_str):
                        found_slots.append(f"{date_str} {t_str} - {player_info}")
                except Exception as e:
                    debug_log(f"Failed to parse a row: {e}")
        except Exception as e:
            debug_log(f"Error fetching tee times for {date_str}: {e}")

    driver.quit()
    if found_slots:
        
        # 读取上次的结果
        last_message = load_last_result_from_gist()
        
        #message = "\n".join(found_slots)
        # 构造 HTML 消息（带链接 + 红色标注新 tee time）
        message_lines = []
        # 获取上次纯文本记录（用换行分隔）
        last_lines = set(last_message.strip().splitlines()) if last_message else set()
        for line in found_slots:
            date_part = line.split(" ")[0]
            url = BASE_URL.format(date=date_part)
            # 如果是新出现的 tee time，用红色高亮显示
            if line not in last_lines:
                line_with_link = f'<span style="color:red">{line}</span> <a href="{url}">去预订</a>'
            else:
                line_with_link = f'{line} <a href="{url}">去预订</a>'
            message_lines.append(line_with_link)
        message = "<br>".join(message_lines)  # 最终 HTML 邮件内容
        
        debug_log("Matched Tee Times:\n" + message)
        
        debug_log(f"[Gist] Previous content:\n{last_message}")
        debug_log("Current content:\n"+message)        

        # 如果有变化才发邮件
        #if not message or not last_message or not set(message.splitlines()).issubset(set(last_message.splitlines())):
        #    send_email(message)
        #    save_result_to_gist(message)
        #    debug_log("Email sent and result updated.")
        #else:
        #    debug_log("Current tee times are subset of previous — no email sent.")

        # 比较时用纯文本 found_slots 和 last_lines
        current_lines_set = set(found_slots)
        if not current_lines_set or not last_lines or not current_lines_set.issubset(last_lines):
            send_email(message)
            save_result_to_gist("\n".join(found_slots))  # 只保存纯文本
            debug_log("Email sent and result updated.")
        else:
            debug_log("Current tee times are subset of previous — no email sent.")
            
    else:
        debug_log("No matching tee times found.")


# 发邮件
def send_email(content):
    receivers = [email.strip() for email in EMAIL_RECEIVER.split(",")]  # 支持多个收件人
    #msg = MIMEText(content)
    msg = MIMEText(content, "html")  # ← 让它支持 HTML 格式
    msg["Subject"] = "Gleneagles Tee Time Reminder"
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(receivers)

    with smtplib.SMTP_SSL("smtp.126.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, receivers, msg.as_string())   

if __name__ == "__main__":
    check_tee_times()
