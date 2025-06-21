import os
import time
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
GIST_TOKEN = os.environ.get("GIST_TOKEN")  # 从 GitHub 生成的 token
GIST_ID = os.environ.get("GIST_ID")        # 你的 Gist ID
GIST_FILENAME = "northlands_tee_times.txt"  # 你在 Gist 中使用的文件名

def load_previous_tee_times():
    if not GIST_ID or not GIST_TOKEN:
        return set()
    try:
        response = requests.get(
            f"https://api.github.com/gists/{GIST_ID}",
            headers={"Authorization": f"token {GIST_TOKEN}"}
        )
        if response.status_code == 200:
            gist_data = response.json()
            if GIST_FILENAME in gist_data["files"]:
                content = gist_data["files"][GIST_FILENAME]["content"]
                return set(line.strip() for line in content.strip().splitlines())
            else:
                log(f"⚠️ Gist 中未找到指定文件 {GIST_FILENAME}")
    except Exception as e:
        log(f"⚠️ 加载 Gist 失败: {e}")
    return set()

def save_to_gist(lines):
    if not GIST_ID or not GIST_TOKEN:
        return
    try:
        data = {
            "files": {
                GIST_FILENAME: {
                    "content": "\n".join(lines)
                }
            }
        }
        response = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            json=data,
            headers={"Authorization": f"token {GIST_TOKEN}"}
        )
        if response.status_code == 200:
            log("💾 本次 tee time 已更新到 Gist")
            log(f"✅ 写入 Gist 内容:\n{data['files'][GIST_FILENAME]['content']}")
        else:
            log(f"⚠️ Gist 写入失败，状态码: {response.status_code}")
    except Exception as e:
        log(f"❌ 更新 Gist 失败: {e}")
        
#发送邮件
def send_email(content):
    receivers = [email.strip() for email in EMAIL_RECEIVER.split(",")]  # 支持多个收件人
    msg = MIMEText(content)
    msg["Subject"] = "Northlands Tee Time Reminder"
    msg["From"] = EMAIL_SENDER
    #msg["To"] = ", ".join(receivers)
    msg["To"] = "jason_bai@126.com"

    with smtplib.SMTP_SSL("smtp.126.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, receivers, msg.as_string())   

# ========== 登录 ==========
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # ✅ 必需导入这一行
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        wait.until(EC.url_contains("onlineresweb"))
        log("✅ 登录成功并跳转到预约页面")
        #driver.save_screenshot("step4_final_state.png")
    except TimeoutException:
        log(f"❌ 登录后页面未跳转，当前 URL：{driver.current_url}")
        #driver.save_screenshot("step4_final_state.png")
        raise Exception("未跳转到预约页面，登录流程失败")    
        
# ========== 设置日期 ==========
def set_date(driver, target_date):
    wait = WebDriverWait(driver, 15)
    
    # 格式化目标日期为 aria-label 需要的格式，如 24-6-2025
    day = target_date.strftime("%d").lstrip("0")
    month = target_date.strftime("%m").lstrip("0")
    year = target_date.strftime("%Y")
    aria_label = f"{day}-{month}-{year}"
    xpath = f"//div[@role='gridcell' and @aria-label='{aria_label}']//div[contains(@class, 'btn-light')]"
    
    log(f"📅 正在选择日期: {aria_label}")
    
    # 等待并点击日期输入框
    try:
        # 等待输入框渲染并可见
        date_input = wait.until(EC.presence_of_element_located((By.ID, "mat-input-3")))
        driver.execute_script("arguments[0].scrollIntoView(true);", date_input)
        wait.until(EC.element_to_be_clickable((By.ID, "mat-input-3")))
        time.sleep(1)  # 允许动画或遮挡层消失
        date_input.click()
        log("📅 已点击日期输入框，准备选择日期")
        time.sleep(1)
    except Exception as e:
        log(f"❌ 点击日期输入框失败: {e}")
        raise

    # 检查是否有弹窗并关闭
    try:
        close_btn = driver.find_element(By.XPATH, "//button//span[text()='Close']")
        if close_btn.is_displayed():
            log("⚠️ 检测到弹窗，尝试关闭...")
            close_btn.click()
            time.sleep(1)
    except:
        pass  # 没有弹窗，忽略

    # 截图调试
    #screenshot_name = f"screenshot_before_click_{target_date.strftime('%Y%m%d')}.png"
    #driver.save_screenshot(screenshot_name)
    #log(f"🖼️ 截图已保存: {screenshot_name}")

    # 点击日历中的日期
    # 点击日历中的日期
    try:
        date_button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].click();", date_button)
        log("📆 日期已点击")
        
        # ✅ 新增：等待 tee time 卡片至少加载一个，确保日历关闭页面刷新完成
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "teetimecard"))
        )
        time.sleep(1)  # 稍作等待以保证 DOM 稳定
        log("✅ 页面已刷新，teetimecard 元素已出现")

    except Exception as e:
        log(f"❌ 日期点击或等待刷新失败: {e}")
        raise Exception(f"日期点击或 tee time 刷新失败: {e}")

    # 等待页面加载 Tee Time 内容
    try:
        wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "teetimecard")))
        log("✅ Tee Time 列表已加载")
    except TimeoutException:
        log("⚠️ 日期选择后 Tee Time 列表未及时加载")
        
# ========== 抓取 Tee Time ==========
'''_def extract_tee_times(driver, target_date):
    cards = driver.find_elements(By.CLASS_NAME, "teetimecard")
    result = []
    raw_log = []

    for card in cards:
        try:
            text = card.text.strip()
            raw_log.append(text)

            # 抓取时间字段
            time_element = card.find_element(By.TAG_NAME, "time")
            time_str = time_element.text.strip()
            t = datetime.strptime(time_str, "%I:%M")

            # 判断上午 9 点到 12 点，且包含 "4 GOLFERS"
            if 9 <= t.hour < 12 and "4 GOLFERS" in text:
                result.append(f"{target_date.strftime('%Y-%m-%d')} | {text}")
        except Exception as e:
            continue

    log(f"🧾 所有 tee time 原始信息（{target_date.strftime('%Y-%m-%d')}）:\n" + "\n".join(raw_log))
    return result '''

def extract_tee_times(driver, target_date):
    tee_cards = driver.find_elements(By.CLASS_NAME, "teetimecard")
    all_raw = []
    valid = []
    for card in tee_cards:
        try:
            time_elem = card.find_element(By.TAG_NAME, "time")
            time_text = time_elem.text.strip()
            time_full = time_elem.get_attribute("datetime")  # e.g., 2025-06-24T09:36:00
            if not time_full:
                continue
            dt = datetime.fromisoformat(time_full)
            ampm = "AM" if dt.hour < 12 else "PM"

            # tee time slot summary
            line = f"{target_date.strftime('%Y-%m-%d')} | {dt.strftime('%-I:%M')} {ampm}"

            # 添加 HOLES 信息
            holes_text = ""
            try:
                holes = card.find_element(By.CLASS_NAME, "teetimeholes")
                holes_text = holes.text.strip()
                line += f" | {holes_text}"
            except:
                pass

            # 添加价格信息
            try:
                price = card.find_element(By.CLASS_NAME, "teetimetableprice")
                line += f" | {price.text.strip()}"
            except:
                pass

            all_raw.append(line)
            if 9 <= dt.hour < 12 and "4 GOLFERS" in holes_text:
                valid.append(line)
        except Exception as e:
            continue

    # 打印所有抓到的 tee time 信息方便调试
    log(f"🧾 所有 tee time 原始信息（{target_date.strftime('%Y-%m-%d')}）:")
    for row in all_raw:
        log("  " + row)

    return valid

# ========== 日期范围 ==========
def get_upcoming_weekdays(days=21):
    today = datetime.today()
    return [today + timedelta(days=i) for i in range(days) if (today + timedelta(days=i)).weekday() < 5]

# ========== 主流程 ==========
def main():
    mobile_emulation = {
        "deviceName": "iPhone X"  # ✅ 模拟移动端设备
    }

    chrome_options = Options()
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
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

                # 👉 加一个截图，保存当前页面
                #screenshot_filename = f"debug_{day.strftime('%Y-%m-%d')}.png"
                #driver.save_screenshot(screenshot_filename)
                #log(f"📸 已保存截图：{screenshot_filename}")
                
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

    # 使用 set 结构去重比较
    current = set(all_results)
    previous = load_previous_tee_times()

    if current:
        content = "\n".join(sorted(current))
        log("📤 当前抓取结果内容:\n" + content)

        log(f"📥 上一次 Gist 中记录的 tee time 数量: {len(previous)}")
        log(f"📈 本次抓取 tee time 数量: {len(current)}")

        # ✅ 如果当前内容不是上次的子集，则认为有新增
        if not previous or not current.issubset(previous):
            send_email(content)
            save_to_gist(sorted(current))  # 保存新内容
            log("📬 邮件已发送，Gist 已更新")
        else:
            log("✅ 当前 tee time 是上次的子集或相同，不发送邮件")
    else:
        log("✅ 未来三周无上午 tee time，无需发送邮件")
        
if __name__ == "__main__":
    main()
