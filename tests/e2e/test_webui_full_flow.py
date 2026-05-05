"""End-to-end test: Login flow with Brave browser.

Usage:
    uv run pytest tests/e2e/test_webui_full_flow.py -v -s
"""

from __future__ import annotations

import time
import os

import pytest

pytest.importorskip("selenium", reason="selenium not installed")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

BRAVE_BIN = "/usr/sbin/brave"
BASE_URL = "http://127.0.0.1:5055"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="requires RUN_E2E=1 and a live WebUI server",
)


@pytest.fixture(scope="module")
def driver():
    opts = Options()
    opts.binary_location = BRAVE_BIN
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    d = webdriver.Chrome(options=opts)
    d.implicitly_wait(5)
    yield d
    d.quit()


def test_01_home_redirects_to_login(driver):
    driver.get(BASE_URL)
    time.sleep(1)
    assert "/login" in driver.current_url
    print(f"\n[1] Redirected to login → {driver.current_url}")


def test_02_login_with_default_credentials(driver):
    driver.find_element(By.NAME, "username").send_keys("admin")
    driver.find_element(By.NAME, "password").send_keys("admin")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1)
    assert "/change-password" in driver.current_url
    print(f"[2] Default login → {driver.current_url}")


def test_03_change_password(driver):
    driver.find_element(By.NAME, "new_password").send_keys("newpass123")
    driver.find_element(By.NAME, "confirm_password").send_keys("newpass123")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1)
    assert "/change-password" not in driver.current_url
    print(f"[3] Password changed → {driver.current_url}")


def test_04_logout_and_login_with_new_password(driver):
    driver.get(f"{BASE_URL}/logout")
    time.sleep(1)
    assert "/login" in driver.current_url

    driver.find_element(By.NAME, "username").send_keys("admin")
    driver.find_element(By.NAME, "password").send_keys("newpass123")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1)
    assert "/change-password" not in driver.current_url
    assert "/login" not in driver.current_url
    print(f"[4] Login with new password → {driver.current_url}")


def test_05_wrong_password(driver):
    driver.get(f"{BASE_URL}/logout")
    time.sleep(1)
    driver.find_element(By.NAME, "username").send_keys("admin")
    driver.find_element(By.NAME, "password").send_keys("wrong")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1)
    assert "/login" in driver.current_url
    page = driver.page_source
    assert "Invalid" in page
    print(f"[5] Wrong password rejected → {driver.current_url}")
