import os
import time
import sys
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.common import Keys
from DrissionPage.errors import AlertExistsError

# --- 設定區 ---
LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"
ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")

def log(msg):
    """即時輸出 Log"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def safe_screenshot(page, filename):
    """
    安全的截圖函式
    """
    try:
        page.get_screenshot(str(ART_DIR / filename))
    except AlertExistsError:
        log("⚠️ 截圖時遇到原生 Alert，嘗試強制處理...")
        try:
            # 直接呼叫處理方法，不檢查屬性
            page.handle_alert(accept=True)
            time.sleep(1)
            page.get_screenshot(str(ART_DIR / filename))
        except Exception as e:
            log(f"❌ 處理 Alert 後截圖仍失敗: {e}")

def run():
    log("🚀 腳本開始執行 (Final Fix)")
    
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_browser_path('/usr/bin/google-chrome')
    co.set_timeouts(base=10, page_load=60)

    try:
        log("1. 啟動瀏覽器...")
        page = ChromiumPage(co)
        
        # [關鍵] 設定全自動處理原生彈窗
        # 只要有 Alert 跳出，自動按確定，無需手動介入
        page.set.auto_handle_alert(accept=True)
        log("✅ 已啟用自動 Alert 處理")

        log(f"2. 前往網址: {LOGIN_URL}")
        page.get(LOGIN_URL, retry=1, timeout=30)
        
        log("⏳ 等待文件載入...")
        page.wait.doc_loaded(timeout=15, raise_err=False)
        safe_screenshot(page, "01_loaded.png")

        log("3. 處理 HTML 遮罩 (Enter Loop)...")
        # 這裡只需要專注處理 "非原生" 的 HTML 遮罩 (因為原生的已經被上面 auto_handle 解決了)
        for i in range(5):
            # 檢查登入框是否可見
            ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=1)
            if ele_user and ele_user.is_displayed():
                log(f"✅ 在第 {i} 次檢查時發現登入框，準備登入。")
                break
            
            log(f"👉 第 {i+1} 次嘗試按 Enter (消除 HTML 遮罩)...")
            page.actions.type(Keys.ENTER)
            time.sleep(1.5)
            
            if i == 0:
                safe_screenshot(page, "01-1_after_enter.png")

        log("4. 尋找登入輸入框...")
        ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=5)
        
        if not ele_user or not ele_user.is_displayed():
            log("❌ 找不到可互動的登入框！")
            safe_screenshot(page, "99_not_found.png")
            return

        log("✅ 找到輸入框，開始輸入帳密...")
        ele_pass = page.ele('css:input#loginpw')
        ele_btn = page.ele('css:input#login_but')

        ele_user.input(USERNAME)
        time.sleep(0.2)
        ele_pass.input(PASSWORD)
        log("✅ 帳密已填寫")
        safe_screenshot(page, "02_filled.png")

        log("5. 點擊登入按鈕...")
        ele_btn.click()
        
        log("⏳ 等待跳轉...")
        page.wait.doc_loaded(timeout=20, raise_err=False)
        
        safe_screenshot(page, "03_result.png")
        log(f"ℹ️ 登入後 URL: {page.url}")

        if "login" not in page.url or page.ele('text:登出'):
            log("🎉 登入成功！")
        else:
            log("❓ 登入狀態未明，請檢查 03_result.png")

    except Exception as e:
        log(f"🔥 發生錯誤: {e}")
        # 錯誤處理區塊也不要檢查 page.alert.exists，直接嘗試 handle
        try:
            page.handle_alert(accept=True)
            page.get_screenshot(str(ART_DIR / "crash_dump.png"))
        except:
            pass
        raise
    finally:
        log("🛑 關閉瀏覽器")
        page.quit()

if __name__ == "__main__":
    run()
