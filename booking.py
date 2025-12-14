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
    安全的截圖函式：
    如果截圖時剛好遇到原生 Alert，先處理掉再截圖，避免崩潰。
    """
    try:
        page.get_screenshot(str(ART_DIR / filename))
    except AlertExistsError:
        log("⚠️ 截圖時遇到原生 Alert，嘗試自動接受...")
        try:
            page.handle_alert(accept=True) # 點擊確定
            time.sleep(1)
            page.get_screenshot(str(ART_DIR / filename))
        except Exception as e:
            log(f"❌ 處理 Alert 後截圖仍失敗: {e}")

def run():
    log("🚀 腳本開始執行 (Auto-Handle Alert 版)")
    
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_browser_path('/usr/bin/google-chrome')
    # 設定較長的 timeout，以免載入太久
    co.set_timeouts(base=10, page_load=60)

    try:
        log("1. 啟動瀏覽器...")
        page = ChromiumPage(co)
        
        # --- [關鍵修正 1] 開啟自動處理原生彈窗 ---
        # 這行指令告訴瀏覽器：只要看到 Alert/Confirm，自動點「確定」(accept=True)
        # 這會持續生效，解決 "1-3 次彈窗" 的問題
        page.set.auto_handle_alert(accept=True)
        log("✅ 已啟用自動 Alert 處理 (Auto-Accept)")
        # -------------------------------------

        log(f"2. 前往網址: {LOGIN_URL}")
        page.get(LOGIN_URL, retry=1, timeout=30)
        
        log("⏳ 等待文件載入...")
        # 這裡可能會因為 Alert 出現而稍微卡住，但 auto_handle 應該會秒解
        page.wait.doc_loaded(timeout=15, raise_err=False)
        
        safe_screenshot(page, "01_loaded.png")

        # --- [關鍵修正 2] 混合處理 (HTML 彈窗 + 原生 Alert) ---
        log("3. 雙重檢查彈窗 (HTML Modal)...")
        
        # 雖然開了 auto_handle，但如果是 HTML 做的假彈窗，還是要按 Enter
        for i in range(5):
            # 檢查是否還有原生 Alert 殘留 (防呆)
            if page.alert.exists:
                log(f"👉 [原生] 發現殘留 Alert，手動處理...")
                page.handle_alert(accept=True)
                time.sleep(1)
                continue

            # 檢查登入框是否可見
            ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=1)
            if ele_user and ele_user.is_displayed():
                log(f"✅ 在第 {i} 次檢查時發現登入框，準備登入。")
                break
            
            log(f"👉 [HTML] 第 {i+1} 次嘗試按 Enter (消除遮罩)...")
            page.actions.type(Keys.ENTER)
            time.sleep(1.5)
            
            if i == 0:
                safe_screenshot(page, "01-1_after_enter.png")
        # -------------------------------------

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
        # 最後再嘗試處理一次 alert 以便截圖
        try:
            if page.alert.exists:
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
