import os
import time
import sys
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ElementNotFoundError

# --- 設定區 ---
LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"
ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")

def log(msg):
    """即時輸出 Log，並包含時間戳記"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush() # 強制刷新緩衝區，確保 GitHub Actions 能即時看到

def run():
    log("🚀 腳本開始執行")
    
    # 1. 設定瀏覽器選項
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage') # 避免記憶體不足崩潰
    co.set_browser_path('/usr/bin/google-chrome') # 明確指定路徑

    # 設定連線逾時，避免卡在啟動
    co.set_timeouts(base=10, page_load=30)

    try:
        log("1. 正在啟動 DrissionPage (Chrome)...")
        page = ChromiumPage(co)
        log("✅ 瀏覽器啟動成功")
    except Exception as e:
        log(f"❌ 瀏覽器啟動失敗: {e}")
        return

    try:
        log(f"2. 前往網址: {LOGIN_URL}")
        # retry=1, interval=1 代表失敗只重試一次
        page.get(LOGIN_URL, retry=1, interval=1, timeout=20)
        log("✅ 頁面載入完成 (或已達逾時)")
        
        # 立即截圖
        page.get_screenshot(str(ART_DIR / "01_loaded.png"))
        log("📸 已截圖 01_loaded.png")

        # 3. 檢查目前頁面標題與 URL，判斷狀況
        log(f"ℹ️ 目前 URL: {page.url}")
        log(f"ℹ️ 目前 Title: {page.title}")

        # 4. 偵測 Cloudflare
        log("3. 檢查是否有 Cloudflare 驗證...")
        # 檢查常見 CF 特徵
        if "Just a moment" in page.title or page.ele("xpath://iframe[contains(@src, 'cloudflare')]", timeout=2):
            log("⚠️ 偵測到 Cloudflare 阻擋畫面！")
            page.get_screenshot(str(ART_DIR / "98_cloudflare_detected.png"))
            
            # 嘗試簡單繞過 (等待)
            log("⏳ 等待 5 秒...")
            time.sleep(5)
            
            # 再次檢查
            if "Just a moment" in page.title:
                log("❌ Cloudflare 驗證未通過，程式將終止")
                # 這裡不報錯，讓它正常結束以便我們看 Artifacts
                return 

        # 5. 尋找登入框
        log("4. 尋找登入輸入框...")
        
        # 使用極短 timeout (5秒)，找不到就報錯，不要空等
        ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=5)
        
        if not ele_user:
            log("❌ 找不到使用者名稱輸入框！可能還在 Cloudflare 畫面或版面已變更")
            page.get_screenshot(str(ART_DIR / "99_not_found.png"))
            log("📸 已截圖 99_not_found.png")
            
            # 嘗試印出頁面原始碼的前 500 字，幫忙除錯
            print("--- Page Source Head ---")
            print(page.html[:500])
            print("------------------------")
            return

        log("✅ 找到輸入框，開始輸入...")
        ele_pass = page.ele('css:input#loginpw')
        ele_btn = page.ele('css:input#login_but')

        # 處理可能的彈窗 (Swal)
        swal = page.ele('css:button.swal2-confirm', timeout=2)
        if swal:
            log("👉 發現彈窗，點擊確認")
            swal.click()
            time.sleep(1)

        ele_user.input(USERNAME)
        ele_pass.input(PASSWORD)
        log("✅ 帳密已填寫")
        page.get_screenshot(str(ART_DIR / "02_filled.png"))

        log("5. 點擊登入按鈕...")
        ele_btn.click()
        
        log("⏳ 等待跳轉 (5秒)...")
        time.sleep(5)
        page.get_screenshot(str(ART_DIR / "03_result.png"))
        log(f"ℹ️ 登入後 URL: {page.url}")

        if "login" not in page.url:
            log("🎉 登入成功！")
        else:
            log("❓ 似乎還在登入頁，請檢查截圖 03_result.png")

    except Exception as e:
        log(f"🔥 發生未預期的錯誤: {e}")
        try:
            page.get_screenshot(str(ART_DIR / "crash_dump.png"))
        except:
            pass
        raise
    finally:
        log("🛑 關閉瀏覽器")
        page.quit()

if __name__ == "__main__":
    run()
