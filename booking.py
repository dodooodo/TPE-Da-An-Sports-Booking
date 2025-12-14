import os
import time
import random
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions

# --- 設定區 ---
LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"
ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")
CF_WAIT_SECONDS = int(os.getenv("CF_WAIT_SECONDS", "10"))

def run():
    # 1. 設定瀏覽器選項
    co = ChromiumOptions()
    co.set_argument('--no-sandbox') # Linux 必要
    co.set_argument('--disable-gpu')
    # DrissionPage 預設就是 "有頭模式" (無須設定 headless=False，預設即是)
    # 它會自動處理 User-Agent 和隱藏特徵
    
    # 指向剛剛安裝的 Chrome 路徑 (通常是這個，若報錯可移除這行讓它自動抓)
    co.set_browser_path('/usr/bin/google-chrome')

    print("啟動 DrissionPage...")
    page = ChromiumPage(co)
    
    try:
        # 開啟截圖功能 (DrissionPage 截圖稍微不同)
        print(f"前往: {LOGIN_URL}")
        page.get(LOGIN_URL)
        
        # 2. 處理 Cloudflare
        # DrissionPage 對 Cloudflare 有較強的抗性，通常只要等待即可
        # 如果有 Turnstile，它通常不會顯示驗證碼，或者我們可以嘗試點擊
        print(f"等待 {CF_WAIT_SECONDS} 秒 Cloudflare 驗證...")
        time.sleep(CF_WAIT_SECONDS)
        
        page.get_screenshot(str(ART_DIR / "01_loaded.png"))

        # 3. 檢查是否有 Turnstile (iframe)
        # DrissionPage 尋找 iframe 非常簡單
        if page.ele("xpath://iframe[contains(@src, 'cloudflare')]", timeout=2):
            print("偵測到 Cloudflare iframe，嘗試點擊...")
            # 嘗試點擊 iframe 中心 (這是一個盲解策略)
            # 但通常 DrissionPage 不需要這步，它本身不會觸發機器人驗證
            pass

        # 4. 處理彈窗 (SweetAlert)
        # 語法：page.ele('css selector')
        confirm_btn = page.ele('css:button.swal2-confirm', timeout=2)
        if confirm_btn:
            print("點擊彈窗...")
            confirm_btn.click()
            time.sleep(1)

        # 嘗試消除原生遮罩
        if not page.ele(f'css:input#ContentPlaceHolder1_loginid', timeout=1):
            print("按 Enter 消除遮罩...")
            page.actions.type('ENTER')
        
        # 5. 登入
        print("輸入帳密...")
        ele_user = page.ele('css:input#ContentPlaceHolder1_loginid')
        ele_pass = page.ele('css:input#loginpw')
        ele_btn = page.ele('css:input#login_but')

        if ele_user:
            ele_user.input(USERNAME)
            time.sleep(0.5)
            ele_pass.input(PASSWORD)
            time.sleep(0.5)
            
            page.get_screenshot(str(ART_DIR / "02_filled.png"))
            
            print("點擊登入...")
            ele_btn.click()
            
            # 等待轉址
            time.sleep(5)
            page.get_screenshot(str(ART_DIR / "03_result.png"))
            
            if "login" not in page.url:
                print("✅ 登入成功 (URL 已變更)")
            else:
                print("❓ 登入狀態未明")
        else:
            print("❌ 找不到登入框，可能還卡在 Cloudflare")
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        page.get_screenshot(str(ART_DIR / "99_error.png"))
        raise
    finally:
        page.quit()

if __name__ == "__main__":
    run()
