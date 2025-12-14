import os
import time
import sys
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.common import Keys  # 引入按鍵常數

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

def run():
    log("🚀 腳本開始執行 (Enter 鍵連發版)")
    
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_browser_path('/usr/bin/google-chrome')
    co.set_timeouts(base=15, page_load=30)

    try:
        log("1. 啟動瀏覽器...")
        page = ChromiumPage(co)
        
        log(f"2. 前往網址: {LOGIN_URL}")
        page.get(LOGIN_URL, retry=1, timeout=20)
        
        log("⏳ 等待文件載入...")
        page.wait.doc_loaded(timeout=10, raise_err=False)
        page.get_screenshot(str(ART_DIR / "01_loaded.png"))

        # --- [核心修正] 迴圈按 Enter 消除彈窗 ---
        log("3. 處理彈窗 (嘗試按 Enter)...")
        
        # 設定最多嘗試 5 次 (即使你說 1-3 次，多設一點比較保險)
        popup_cleared = False
        for i in range(5):
            # 每次按之前，先檢查登入框是否已經出現且可見
            # 如果已經可以輸入，代表彈窗沒了，直接跳出迴圈
            ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=1)
            if ele_user and ele_user.is_displayed():
                log(f"✅ 在第 {i} 次檢查時發現登入框，停止按 Enter。")
                popup_cleared = True
                break
            
            log(f"👉 第 {i+1} 次嘗試按 Enter...")
            
            # 模擬按下 Enter 鍵
            page.actions.type(Keys.ENTER)
            
            # 等待一下讓彈窗動畫消失
            time.sleep(1.5)
            
            # 截圖紀錄過程 (可選)
            if i == 0:
                page.get_screenshot(str(ART_DIR / "01-1_after_first_enter.png"))
        
        # 如果跑完迴圈還沒標記成功，再最後確認一次
        if not popup_cleared:
            log("⚠️ 迴圈結束，將嘗試直接尋找登入框...")
        # -------------------------------------

        log("4. 尋找登入輸入框...")
        ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=5)
        
        if not ele_user or not ele_user.is_displayed():
            log("❌ 仍然找不到可互動的登入框！可能 Enter 沒效或彈窗太多。")
            page.get_screenshot(str(ART_DIR / "99_not_found.png"))
            return

        log("✅ 找到輸入框，開始輸入帳密...")
        ele_pass = page.ele('css:input#loginpw')
        ele_btn = page.ele('css:input#login_but')

        ele_user.input(USERNAME)
        time.sleep(0.2)
        ele_pass.input(PASSWORD)
        log("✅ 帳密已填寫")
        page.get_screenshot(str(ART_DIR / "02_filled.png"))

        log("5. 點擊登入按鈕...")
        ele_btn.click()
        
        log("⏳ 等待跳轉...")
        page.wait.doc_loaded(timeout=15, raise_err=False)
        
        page.get_screenshot(str(ART_DIR / "03_result.png"))
        log(f"ℹ️ 登入後 URL: {page.url}")

        if "login" not in page.url or page.ele('text:登出'):
            log("🎉 登入成功！")
        else:
            log("❓ 登入狀態未明，請檢查 03_result.png")

    except Exception as e:
        log(f"🔥 發生錯誤: {e}")
        page.get_screenshot(str(ART_DIR / "crash_dump.png"))
        raise
    finally:
        log("🛑 關閉瀏覽器")
        page.quit()

if __name__ == "__main__":
    run()
