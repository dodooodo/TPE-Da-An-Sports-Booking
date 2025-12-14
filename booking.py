import os
import time
import sys
import random
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.common import Keys

# --- 設定區 ---
LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"
ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

# [新增] 擬人化隨機延遲
def human_delay(min_s=0.5, max_s=1.5):
    """
    模擬人類思考或手部移動的延遲
    """
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)

def run():
    log("🚀 腳本開始執行 (Humanized Version)")
    
    co = ChromiumOptions()
    # [建議] 如果是在本地跑，盡量不要用無頭模式 (Headless)，有頭模式特徵最真實
    # co.headless(False) 
    
    # 讓 DrissionPage 自動管理 UserAgent，使其與 Chrome 版本匹配
    co.auto_port() 
    
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_timeouts(base=10, page_load=60)

    try:
        page = ChromiumPage(co)
        page.set.auto_handle_alert(accept=True)
        
        log(f"前往: {LOGIN_URL}")
        page.get(LOGIN_URL, retry=1, timeout=30)
        page.wait.doc_loaded(timeout=15, raise_err=False)
        
        # [擬人化] 載入後不會馬上動作，人類會先看一眼
        human_delay(1.0, 2.0)

        # 處理遮罩
        log("處理遮罩...")
        try:
            # 優先嘗試點擊 swal
            btn = page.ele('css:button.swal2-confirm', timeout=1)
            if btn and btn.states.is_displayed:
                human_delay(0.3, 0.8) # 看到按鈕 -> 移動滑鼠 -> 點擊
                btn.click()
        except:
            pass

        # 備用：按 Enter
        for _ in range(3):
            ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=1)
            if ele_user and ele_user.states.is_displayed:
                break
            page.actions.type(Keys.ENTER)
            human_delay(0.2, 0.5)

        # 輸入帳密
        log("輸入帳密...")
        ele_user = page.ele('css:input#ContentPlaceHolder1_loginid', timeout=5)
        if not ele_user:
            log("❌ 找不到登入框")
            return

        # [擬人化] 輸入速度隨機化
        # DrissionPage 預設輸入很快，我們可以拆開來輸入，或至少在兩個欄位間加延遲
        ele_user.click() # 先點一下 focus
        human_delay(0.2, 0.5)
        ele_user.input(USERNAME)
        
        human_delay(0.5, 1.2) # 輸入完帳號，切換到密碼欄位的時間
        
        ele_pass = page.ele('css:input#loginpw')
        ele_pass.click()
        ele_pass.input(PASSWORD)
        
        human_delay(0.5, 1.0) # 輸入完密碼，準備點登入

        # 執行登入
        log("點擊登入...")
        ele_btn = page.ele('css:input#login_but')
        
        # [高級防禦] 有時候 CF 會偵測滑鼠是否真的懸停在按鈕上
        # page.actions.move_to(ele_btn) # 移動滑鼠到按鈕
        # human_delay(0.2, 0.4)
        
        ele_btn.click() # 這裡不需要 by_js=True，用模擬點擊更像真人
        
        # 等待結果
        log("等待跳轉...")
        # 這裡用較長的輪詢檢查
        for _ in range(15):
            time.sleep(1)
            if LOGIN_URL not in page.url and "login" not in page.url:
                log("🎉 登入成功！")
                break
        else:
            log("⚠️ URL 未變更，可能需要檢查截圖")
            page.get_screenshot(str(ART_DIR / "debug_result.png"))

    except Exception as e:
        log(f"🔥 Error: {e}")
    finally:
        page.quit()

if __name__ == "__main__":
    run()
