import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

URL_TEMPLATE = "https://w.cps.golf/WestVancouverV3/Home/nIndex?CourseId=1&Date={date}&Time=AnyTime&Player=99&Hole=9"
START_HOUR = 9
END_HOUR = 12
MIN_SPOTS = 4

def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    with smtplib.SMTP("smtp.126.com", 25) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

def check_tee_times_for_date(driver, date_obj):
    date_str = date_obj.strftime("%Y-%-m-%-d")
    url = URL_TEMPLATE.format(date=date_str)
    driver.get(url)
    time.sleep(5)
    matches = []
    rows = driver.find_elements(By.CLASS_NAME, "teeTimeRow")
    for row in rows:
        try:
            t_str = row.find_element(By.CLASS_NAME, "timeCell").text
            p_str = row.find_element(By.CLASS_NAME, "playersCell").text
            hour = int(t_str.split(":")[0])
            if "PM" in t_str.upper() and hour < 12:
                hour += 12
            if "to" in p_str:
                high = int(p_str.split("to")[1].split()[0])
            else:
                high = int(p_str.split()[0])
            if START_HOUR <= hour < END_HOUR and high >= MIN_SPOTS:
                matches.append(f"{date_str} - {t_str} - {p_str}")
        except:
            continue
    return matches

def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    today = datetime.today()
    all_matches = []
    for i in range(1, 9):
        date_obj = today + timedelta(days=i)
        all_matches += check_tee_times_for_date(driver, date_obj)
    driver.quit()
    if all_matches:
        subject = f"⛳ Tee Time 提醒：{len(all_matches)} 个空位"
        body = "\n".join(all_matches)
        send_email(subject, body)

if __name__ == "__main__":
    main()
