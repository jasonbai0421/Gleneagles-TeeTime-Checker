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

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.126.com", 25) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("✅ 邮件发送成功")
    except Exception as e:
        print("❌ 邮件发送失败:", e)

def check_tee_times():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    today = datetime.today()
    all_results = []

    for i in range(1, 9):  # 次日到第 8 天
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime("%Y-%-m-%-d")
        url = f"https://w.cps.golf/WestVancouverV3/Home/nIndex?CourseId=1&Date={date_str}&Time=AnyTime&Player=99&Hole=9"

        print(f"\n🔍 正在检查日期：{check_date.strftime('%Y-%m-%d')}")

        driver.get(url)
        time.sleep(2)

        slots = driver.find_elements(By.CSS_SELECTOR, ".teeTime")
        for slot in slots:
            try:
                t_str = slot.find_element(By.CSS_SELECTOR, ".startTime").text.strip()
                p_str = slot.find_element(By.CSS_SELECTOR, ".playerCount").text.strip()

                print(f"发现时间段: {t_str}, 玩家数: {p_str}")

                if "AM" in t_str.upper() or "PM" in t_str.upper():
                    hour = int(t_str.split(":")[0])
                    if "PM" in t_str.upper() and hour < 12:
                        hour += 12
                    if 9 <= hour < 12:
                        players = int(p_str.split("/")[0])
                        if players == 0:
                            result = f"{check_date.strftime('%Y-%m-%d')} {t_str} 有 4 个空位"
                            all_results.append(result)
                            print("✅ 匹配空位:", result)
            except Exception as e:
                print("❌ 解析某个 slot 出错:", e)

    driver.quit()

    if all_results:
        content = "\n".join(all_results)
        send_email("🎯 Gleneagles 可用 Tee Time", content)
    else:
        print("😔 当前无符合条件的 tee time。")

if __name__ == "__main__":
    check_tee_times()
