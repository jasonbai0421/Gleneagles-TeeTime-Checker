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

# ========== 日志函数 ==========
def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    with open("northlands.log", "a") as f:
        f.write(full_message + "\n")

# ========== 邮件配置 ==========
EMAIL = os.environ.get("NORTHLANDS_EMAIL")
PASSWORD = os.environ.get("NORTHLANDS_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", EMAIL)
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

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL, receivers, msg.as_string())
        log("📧 邮件已发送")
    except Exception as e:
        log(f"❌ 邮件发送失败: {e}")

# ========== 登录 ==========
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def login(driver):
    wait = WebDriverWait(driver, 30)
    log("🔑 打开登录页面...")
    driver.get("https://northlands.cps.golf/onlineresweb/auth/verify-email?returnUrl=%2Fm%2Fsearch-teetime%2Fdefault")

    email_input = wait.until(EC.visibility_of_element_located((By.ID, "mat-input-0")))
    email_input.clear()
    email_input.send_keys(EMAIL)
    email_input.send_keys(Keys.TAB)
    time.sleep(1)
    log("📨 已输入邮箱地址")

    next_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'NEXT')]")))
    log(f"🔍 NEXT 按钮 disabled 属性：{next_button.get_attribute('disabled')}")
    driver.execute_script("arguments[0].click();", next_button)

    password_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password']")))
    password_input.send_keys(PASSWORD)
    password_input.send_keys(Keys.TAB)
    time.sleep(1)
    log("🔒 已输入密码")

    sign_in_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'SIGN IN')]")))
    log(f"🔍 SIGN IN 按钮 disabled 属性：{sign_in_button.get_attribute('disabled')}")
    driver.execute_script("arguments[0].click();", sign_in_button)
    log("🟢 点击 SIGN IN 按钮...")

    # 👉 等待 loading 图标出现
    try:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "mat-progress-spinner")))
        log("⏳ 登录中... loading 图标出现")
    except TimeoutException:
        log("⚠️ 登录后未显示 loading 图标，继续尝试跳转")

    # 👉 然后等待 loading 消失（可能出现多次）
    try:
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "mat-progress-spinner")))
        log("✅ loading 完成，准备跳转")
    except TimeoutException:
        log("⚠️ loading 图标未消失，可能跳转异常")

    # 👉 再等跳转到预约页
    try:
        wait.until(EC.url_contains("/m/search-teetime"))
        log("✅ 登录成功并跳转到预约页面")
    except TimeoutException:
        log(f"❌ 登录后页面未跳转，当前 URL：{driver.current_url}")
        driver.save_screenshot("step4_final_state.png")
        raise Exception("未跳转到预约页面，登录流程失败")
    
# ========== 设置日期 ==========
def set_date(driver, target_date):
    wait = WebDriverWait(driver, 10)
    date_input = wait.until(EC.element_to_be_clickable((By.ID, "mat-input-3")))
    date_input.click()
    while True:
        month_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".mat-calendar-period-button")))
        if target_date.strftime("%B %Y") in month_elem.text:
            break
        driver.find_element(By.CSS_SELECTOR, ".mat-calendar-next-button").click()
        time.sleep(0.3)
    day = target_date.day
    wait.until(EC.element_to_be_clickable((
        By.XPATH, f"//div[contains(@class, 'mat-calendar-body-cell-content') and text()='{day}']"))).click()
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[.//span[contains(text(), 'Modify search')]]"))).click()
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "card")))

# ========== 抓取 Tee Time ==========
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

# ========== 日期范围 ==========
def get_upcoming_weekdays(days=21):
    today = datetime.today()
    return [today + timedelta(days=i) for i in range(days) if (today + timedelta(days=i)).weekday() < 5]

# ========== 主流程 ==========
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
                log(f"🔍 正在查询 {day.strftime('%Y-%m-%d')}...")
                set_date(driver, day)
                results = extract_tee_times(driver, day)
                if results:
                    log(f"✅ 找到 {len(results)} 条 tee time：{day.strftime('%Y-%m-%d')}")
                    all_results.extend(results)
                else:
                    log(f"ℹ️ 无上午 tee time：{day.strftime('%Y-%m-%d')}")
            except Exception as e:
                log(f"❌ 查询失败 {day.strftime('%Y-%m-%d')}: {e}")
            log("⏳ 等待 2 秒后继续查询下一天...")
            time.sleep(2)
    finally:
        driver.quit()

    if all_results:
        content = "\n\n".join(all_results)
        send_email(content)
    else:
        log("✅ 未来三周无上午 tee time，无需发送邮件")

if __name__ == "__main__":
    main()
