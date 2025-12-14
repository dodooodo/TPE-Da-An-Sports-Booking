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
    """安全的截圖函式"""
    try:
        page.get_screenshot(str(ART_DIR / filename))
    except Exception as e:
        try:
            # 截圖失敗通常是因為有 Alert，嘗試點掉
            page.handle_alert(accept=True)
            time.sleep(0.5)
            page.get_screenshot(str(ART_DIR / filename))
        except:
            pass

def run():
    log("🚀 腳本開始執行 (Strict Check Mode)")
    
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_browser_path('/usr/bin/google-chrome')
    co.set_timeouts(base=10, page_load=60)

    try:
        log("1. 啟動瀏覽器...")
        page = ChromiumPage(co)
        page.set.auto_handle_alert(accept=True)
        
        log(f"2. 前往網址: {LOGIN_URL}")
        page.get(LOGIN_URL, retry=1, timeout=30)
        page.wait.doc_loaded(timeout=15, raise_err=False)
        safe_screenshot(page, "01_loaded.png")

        # 3. 處理 HTML 遮罩 & Swal
        log("3. 處理遮罩與彈窗...")
        
        # 3-1. 先檢查 swal2 (優先點擊)
        try:
            btn_confirm = page.ele('css:button.swal2-confirm', timeout=2)
            if btn_confirm and btn_confirm.states.is_displayed:
                log("👉 發現 swal2-confirm，點擊！")
                btn_confirm.click()
                time.sleep(1)
        except:
            pass

        # 3-2. 再檢查登入框，若被擋住則按 Enter
        for i in range(3):
            ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=1)
            # 使用 states.is_displayed 確保是真的看得到
            if ele_user and ele_user.states.is_displayed:
                log(f"✅ 登入框已顯示，準備輸入。")
                break
            page.actions.type(Keys.ENTER)
            time.sleep(0.5)

        log("4. 輸入帳密...")
        ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=5)
        if not ele_user or not ele_user.states.is_displayed:
            log("❌ 找不到可互動的登入框！")
            safe_screenshot(page, "99_not_found.png")
            return

        ele_pass = page.ele('css:input#loginpw')
        ele_btn = page.ele('css:input#login_but')

        ele_user.input(USERNAME)
        time.sleep(0.2)
        ele_pass.input(PASSWORD)
        log("✅ 帳密已填寫")
        safe_screenshot(page, "02_filled.png")

        log("5. 執行登入 (使用 JS 強制點擊)...")
        # 改用 by_js=True，這通常能穿透上方可能的透明遮罩
        ele_btn.click(by_js=True)
        
        log("⏳ 正在等待 URL 改變 (最多 10 秒)...")
        # 手動輪詢 URL 變化，比 wait.doc_loaded 更準確
        login_success = False
        for _ in range(10):
            time.sleep(1)
            current_url = page.url
            if LOGIN_URL not in current_url and "login" not in current_url:
                login_success = True
                break
            
            # 有時候只是參數變了，但還是在 login頁面
            if "files=login" not in current_url: 
                # 如果 URL 變短了或變成長的 session ID，也算成功
                pass 

        safe_screenshot(page, "03_result.png")
        log(f"ℹ️ 最終 URL: {page.url}")

        # 6. 結果判定與診斷
        if page.url != LOGIN_URL and "login_page" not in page.url:
             log("🎉 登入成功！(URL 已變更)")
        else:
            log("❌ 登入失敗：URL 未變更。")
            
            # --- [診斷區] 為什麼失敗？ ---
            log("🔎 開始診斷失敗原因 (掃描頁面文字)...")
            
            # 1. 檢查是否有驗證碼圖片
            if page.ele('css:img#ContentPlaceHolder1_CaptchaImage'):
                log("⚠️ 嚴重警告：偵測到「圖形驗證碼」！")
                log("👉 您的帳號可能被鎖定，或該網站強制要求輸入驗證碼。")
                log("👉 解決方案：需要串接 OCR (ddddocr) 才能破解。")

            # 2. 檢查常見錯誤訊息
            body_text = page.ele('tag:body').text
            error_keywords = ["密碼錯誤", "無此帳號", "驗證碼", "錯誤", "必須", "Invalid"]
            found_errors = [k for k in error_keywords if k in body_text]
            
            if found_errors:
                log(f"⚠️ 偵測到錯誤關鍵字: {found_errors}")
            else:
                log("❓ 未發現明顯錯誤文字，請檢查截圖 03_result.png 看是否有彈窗警告。")
            
            # 印出部分 HTML 幫助 Debug
            print("-" * 20)
            print("Page Title:", page.title)
            print("-" * 20)

    except Exception as e:
        log(f"🔥 發生錯誤: {e}")
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
