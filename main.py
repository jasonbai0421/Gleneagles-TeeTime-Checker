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

# 判断是否在上午9点到12点之间
def is_target_time(t_str):
    try:
        t_str = t_str.strip().upper()
        if "AM" in t_str or "PM" in t_str:
            # 格式如 10:30 AM
            hour_part = t_str.split(":")[0]
            hour = int(hour_part)
            if "PM" in t_str and hour < 12:
                hour += 12
            elif "AM" in t_str and hour == 12:
                hour = 0
        else:
            # 格式如 10:30
            hour = int(t_str.split(":")[0])
        return 9 <= hour < 12
    except:
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

        # 读取上次的结果
        last_message = load_last_result_from_gist()
        debug_log(f"[Gist] Previous content:\n{last_message}")
        debug_log("Current content:\n"+message)
        
        # 如果有变化才发邮件
        if not message or not last_message or not set(message.splitlines()).issubset(set(last_message.splitlines())):
            send_email(message)
            save_result_to_gist(message)
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
