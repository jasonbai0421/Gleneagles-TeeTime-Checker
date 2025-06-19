import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from email.mime.text import MIMEText
import smtplib

EMAIL = os.environ.get("NORTHLANDS_EMAIL")
PASSWORD = os.environ.get("NORTHLANDS_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", EMAIL)  # 可设置为发送给自己或多收件人
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.zoho.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", EMAIL)
SMTP_PASS = os.environ.get("SMTP_PASS", PASSWORD)

def send_email(content):
    receivers = [email.strip() for email in EMAIL_RECEIVER.split(",")]
    msg = MIMEText(content)
    msg["Subject"] = "Northlands Tee Time Update"
    msg["From"] = EMAIL
    msg["To"] = ", ".join(receivers)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL, receivers, msg.as_string())

def login(driver):
    wait = WebDriverWait(driver, 15)
    driver.get("https://northlands.cps.golf/onlineresweb/auth/verify-email?returnUrl=%2Fm%2Fsearch-teetime%2Fdefault")
    email_input = wait.until(EC.visibility_of_element_located((By.ID, "mat-input-0")))
    email_input.clear()
    email_input.send_keys(EMAIL)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='NEXT']/.."))).click()
    password_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password']")))
    password_input.send_keys(PASSWORD)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='SIGN IN']/.."))).click()
    wait.until(EC.url_contains("/m/search-teetime"))

def set_date(driver, target_date):
    wait = WebDriverWait(driver, 10)
    date_input = wait.until(EC.element_to_be_clickable((By.ID, "mat-input-3")))
    date_input.click()

    while True:
        month_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".mat-calendar-period-button")))
        if target_date.strftime("%B %Y") in month_elem.text:
            break
        driver.find_element(By.CSS_SELECTOR, ".mat-calendar-next-button").click()
        time.sleep(0.4)

    day = target_date.day
    wait.until(EC.element_to_be_clickable((
        By.XPATH, f"//div[contains(@class, 'mat-calendar-body-cell-content') and text()='{day}']"))).click()

    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[.//span[contains(text(), 'Modify search')]]"))).click()

    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "card")))

def extract_tee_times(driver, target_date):
    cards = driver.find_elements(By.CLASS_NAME, "card")
    result = []
    for card in cards:
        text = card.text.strip()
        if "AM" in text:
            try:
                lines = text.split('\n')
                t = datetime.strptime(lines[0], "%I:%M %p")
                if 9 <= t.hour < 12:
                    result.append(f"{target_date.strftime('%Y-%m-%d')} | {text}")
            except:
                continue
    return result

def get_upcoming_weekdays(days=21):
    today = datetime.today()
    return [today + timedelta(days=i) for i in range(days) if (today + timedelta(days=i)).weekday() < 5]

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    all_results = []

    try:
        login(driver)
        for day in get_upcoming_weekdays():
            try:
                set_date(driver, day)
                results = extract_tee_times(driver, day)
                all_results.extend(results)
            except Exception as e:
                print(f"❌ Failed on {day.strftime('%Y-%m-%d')}: {e}")
    finally:
        driver.quit()

    if all_results:
        send_email("\n\n".join(all_results))
    else:
        print("✅ No morning tee times found.")

if __name__ == "__main__":
    main()
