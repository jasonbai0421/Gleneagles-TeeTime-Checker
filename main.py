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
        if "AM" in t_str.upper() or "PM" in t_str.upper():
            hour = int(t_str.split(":")[0])
            if "PM" in t_str.upper() and hour < 12:
                hour += 12
            return 9 <= hour < 12
    except:
        pass
    return False

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
    message = "\n".join(found_slots)
    debug_log("Matched Tee Times:\n" + message)

    # 读取上次的结果
    last_result_path = "last_result.txt"
    last_message = ""
    if os.path.exists(last_result_path):
        with open(last_result_path, "r") as f:
            last_message = f.read().strip()

    # 如果有变化才发邮件
    if message != last_message:
        send_email(message)
        with open(last_result_path, "w") as f:
            f.write(message)
        debug_log("Email sent and result updated.")
    else:
        debug_log("Tee times unchanged — no email sent.")
else:
    debug_log("No matching tee times found.")

# 发邮件
def send_email(content):
    msg = MIMEText(content)
    msg["Subject"] = "Gleneagles Tee Time Reminder"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    with smtplib.SMTP_SSL("smtp.126.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    check_tee_times()
