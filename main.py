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
def check_tee_times():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    found_slots = []

    today = datetime.today()
    for offset in range(1, 9):  # 次日到+8天
        target_date = today + timedelta(days=offset)
        date_str = target_date.strftime("%Y-%-m-%-d")
        url = BASE_URL.format(date=date_str)
        debug_log(f"Checking {date_str} ... URL: {url}")

        driver.get(url)
        time.sleep(5)  # 确保加载完页面

        try:
            rows = driver.find_elements(By.CSS_SELECTOR, ".available-times .row")
            debug_log(f"Found {len(rows)} rows on {date_str}")
            for row in rows:
                try:
                    time_el = row.find_element(By.CSS_SELECTOR, ".tee-time")
                    spots_el = row.find_element(By.CSS_SELECTOR, ".tee-time-spots")
                    t_str = time_el.text.strip()
                    spots = spots_el.text.strip()

                    debug_log(f"Raw time: {t_str}, Spots: {spots}")

                    if "4" in spots and is_target_time(t_str):
                        found_slots.append(f"{date_str} {t_str} - {spots}")
                except Exception as e:
                    debug_log(f"Failed to parse a row: {e}")
        except Exception as e:
            debug_log(f"Error fetching tee times for {date_str}: {e}")

    driver.quit()

    if found_slots:
        message = "\n".join(found_slots)
        debug_log("Matched Tee Times:\n" + message)
        send_email(message)
    else:
        debug_log("No matching tee times found.")

# 发邮件
def send_email(content):
    msg = MIMEText(content)
    msg["Subject"] = "Gleneagles Tee Time Reminder"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    check_tee_times()
