import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText
import os

# 获取环境变量
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def send_email(slots):
    if not slots:
        print("没有匹配的时间，不发送邮件。")
        return
    content = "\n".join([f"{s['date']} {s['time']} - {s['players']} players" for s in slots])
    msg = MIMEText(content)
    msg["Subject"] = "Gleneagles 可预订 Tee Time"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.126.com", 25) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("✅ 邮件已发送。")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def check_tee_times():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)

    base_url = "https://w.cps.golf/WestVancouverV3/(S(55dss44jkrdzyv2ptxgv5yfh))/Home/nIndex?CourseId=1&Date={}&Time=AnyTime&Player=99&Hole=9"

    today = datetime.now()
    start_date = today + timedelta(days=1)
    end_date = today + timedelta(days=8)

    matching_slots = []

    for i in range((end_date - start_date).days + 1):
        check_date = start_date + timedelta(days=i)
        date_str = check_date.strftime("%Y-%-m-%-d")
        url = base_url.format(date_str)

        print(f"\n🔍 检查日期：{date_str}")
        driver.get(url)
        time.sleep(2)

        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "tr.dataRow")
            print(f"🔍 找到 {len(rows)} 个 Tee Time 行")

            for row in rows:
                t_str = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text.strip()
                players_text = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)").text.strip()

                print(f"  ⏱️ 原始时间：{t_str}，空位情况：{players_text}")

                hour = int(t_str.split(":")[0])
                if "PM" in t_str.upper() and hour < 12:
                    hour += 12

                if 9 <= hour < 12 and "4" in players_text:
                    print("    ✅ 匹配条件：加入到匹配列表中")
                    matching_slots.append({
                        "date": date_str,
                        "time": t_str,
                        "players": players_text
                    })
                else:
                    print("    ❌ 不符合条件")
        except Exception as e:
            print(f"⚠️ 抓取失败: {e}")

    driver.quit()
    
    if matching_slots:
        print("\n✅ 匹配到的 Tee Time：")
        for slot in matching_slots:
            print(f"  - {slot['date']} {slot['time']} with {slot['players']} players")
    else:
        print("\n❌ 没有符合条件的 Tee Time")

    send_email(matching_slots)

if __name__ == "__main__":
    check_tee_times()
