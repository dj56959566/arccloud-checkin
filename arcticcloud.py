# -*- coding:utf-8 -*-
# -------------------------------
# @Author : github@wh1te3zzz https://github.com/wh1te3zzz/checkin
# @Time : 2025-07-18 16:03:22
# ArcticCloud续期脚本（改进版：支持GitHub Actions、本地、青龙面板）
# -------------------------------
"""
ArcticCloud 免费vps自动续期
变量为账号密码，暂不支持多账户
export ARCTIC_USERNAME="ARCTIC账号"
export ARCTIC_PASSWORD="ARCTIC密码"

cron: 0 12 * * *
"""

import os
import time
import logging
from notify import send
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException

# =================== 配置开关 ===================
WAIT_TIMEOUT = 60          # 等待超时时间
ENABLE_SCREENSHOT = False  # 是否开启截图功能
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
LOG_LEVEL = os.environ.get("ARCTIC_LOG_LEVEL", "INFO").upper()
# =================================================

# 环境变量
USERNAME = os.environ.get("ARCTIC_USERNAME")
PASSWORD = os.environ.get("ARCTIC_PASSWORD")

# 页面地址
LOGIN_URL = "https://vps.polarbear.nyc.mn/index/login/?referer="
CONTROL_INDEX_URL = "https://vps.polarbear.nyc.mn/control/index/"

# 截图目录（相对路径）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 日志配置
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def take_screenshot(driver, filename="error.png"):
    """截图保存到指定目录"""
    if not ENABLE_SCREENSHOT:
        return
    path = os.path.join(SCREENSHOT_DIR, filename)
    driver.save_screenshot(path)
    logging.debug("📸 已保存报错截图至: %s", path)

def setup_driver():
    """初始化浏览器"""
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
    if HEADLESS:
        options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 自动检测 chromedriver 路径
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "chromedriver")
    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    if HEADLESS:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.set_window_size(1920, 1080)

    return driver

def login_with_credentials(driver):
    """使用账号密码登录"""
    logging.debug("使用账号密码登录...")
    if not USERNAME or not PASSWORD:
        raise ValueError("缺少 ARCTIC_USERNAME 或 ARCTIC_PASSWORD 环境变量！")

    driver.get(LOGIN_URL)
    try:
        email_input = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.NAME, "swapname"))
        )
        email_input.send_keys(USERNAME)
        logging.debug("✅ 用户名已输入")
    except Exception:
        logging.error("❌ 无法找到用户名输入框")
        take_screenshot(driver, "login_page_error.png")
        raise

    try:
        password_input = driver.find_element(By.NAME, "swappass")
        password_input.send_keys(PASSWORD)
        logging.debug("✅ 密码已输入")
    except Exception:
        logging.error("❌ 无法找到密码输入框")
        take_screenshot(driver, "password_input_error.png")
        raise

    try:
        login_button = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., '登录')]"))
        )
        login_button.click()
        logging.debug("✅ 登录按钮已点击")
    except Exception:
        logging.error("❌ 无法点击登录按钮")
        take_screenshot(driver, "login_button_error.png")
        raise

    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(EC.url_contains("index/index"))
        logging.info("✅ 登录成功！")
    except Exception:
        logging.error("❌ 登录失败：页面未跳转到预期页面")
        take_screenshot(driver, "login_redirect_error.png")
        raise

def navigate_to_control_index(driver):
    """跳转到控制台首页"""
    logging.debug("正在访问控制台首页...")
    driver.get(CONTROL_INDEX_URL)
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(EC.url_contains("control/index"))
        logging.debug("✅ 已进入控制台首页")
    except Exception:
        logging.error("❌ 控制台首页加载失败")
        take_screenshot(driver, "control_index_error.png")
        raise

def find_and_navigate_to_instance_consoles(driver):
    """查找所有实例并进入实例控制台"""
    logging.debug("正在查找所有实例并进入实例控制台...")
    try:
        manage_buttons = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@class, 'btn btn-primary') and contains(@href, '/control/detail/')]")
            )
        )

        instance_ids = [btn.get_attribute('href').split('/')[-2] for btn in manage_buttons]
        if not instance_ids:
            raise ValueError("未找到任何实例")

        logging.info(f"共获取到 {len(instance_ids)} 个实例")

        for i, instance_id in enumerate(instance_ids, start=1):
            logging.info(f"正在处理实例 ID {instance_id} ({i}/{len(instance_ids)})...")
            driver.get(f"https://vps.polarbear.nyc.mn/control/detail/{instance_id}/")

            try:
                WebDriverWait(driver, WAIT_TIMEOUT).until(
                    EC.url_contains(f"/control/detail/{instance_id}/")
                )
                logging.debug(f"✅ 已进入实例 ID {instance_id} 的控制台")
                renew_vps_instance(driver, instance_id)
            except Exception:
                logging.error(f"❌ 无法进入或处理实例 ID {instance_id} 的控制台")
                take_screenshot(driver, f"instance_console_error_{instance_id}.png")
                continue

    except Exception:
        logging.error("❌ 无法找到或点击管理按钮")
        take_screenshot(driver, "manage_button_click_error.png")
        raise

def renew_vps_instance(driver, instance_id):
    """在实例控制台执行续费操作"""
    logging.debug("正在尝试续费 VPS 实例...")
    try:
        renew_button = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-target='#addcontactmodal']"))
        )
        renew_button.click()
        logging.debug("✅ 续费按钮已点击")

        try:
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "input.btn.m-b-xs.w-xs.btn-success.install-complete")
                )
            )
            submit_button.click()
            logging.debug("✅ 已点击 Submit 按钮")
        except TimeoutException:
            logging.error("❌ 未找到 Submit 按钮或超时")
            take_screenshot(driver, "submit_button_not_found.png")
            raise

        try:
            success_alert = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='alert alert-success']"))
            )
            logging.info("✅ 续期成功")
            logging.debug("提示信息：%s", success_alert.text)
        except Exception:
            logging.warning("⚠️ 未检测到续费成功提示，可能已续费成功但页面无反馈")
            take_screenshot(driver, "success_alert_not_found.png")

        try:
            list_group_items = WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_all_elements_located((By.XPATH, "//li[@class='list-group-item']"))
            )
            if len(list_group_items) >= 5:
                full_text = list_group_items[4].text.strip()
                if "到期时间" in full_text:
                    start_index = full_text.find("到期时间")
                    end_index = full_text.find("状态") if "状态" in full_text else len(full_text)
                    expiration_text = full_text[start_index:end_index].strip()
                else:
                    expiration_text = "未找到到期时间信息"

                logging.info(f"📅 实例 {instance_id} 续期成功，下次{expiration_text}")
                send(title="ArcticCloud续期成功", content=f"实例 {instance_id} 下次{expiration_text}")
            else:
                logging.warning("⚠️ 列表项不足五行")
                take_screenshot(driver, "list_group_item_not_enough.png")
        except Exception as e:
            logging.warning("⚠️ 读取列表项内容时发生异常：%s", e)
            take_screenshot(driver, "list_group_item_error.png")

    except Exception:
        logging.error("❌ 续费过程中发生异常", exc_info=True)
        take_screenshot(driver, "renew_process_error.png")
        raise

if __name__ == "__main__":
    driver = None
    try:
        logging.info("🚀 开始执行VPS自动续费脚本...")
        driver = setup_driver()
        login_with_credentials(driver)
        navigate_to_control_index(driver)
        find_and_navigate_to_instance_consoles(driver)
    except Exception:
        logging.error("🔴 主程序运行异常，已终止。", exc_info=True)
    finally:
        if driver:
            logging.info("关闭浏览器...")
            driver.quit()
        logging.info("✅ 脚本执行完成")
