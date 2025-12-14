import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, BrowserContext

# --- 設定區 ---
LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"

# Selectors
SEL_SWAL_CONFIRM = "button.swal2-confirm"
SEL_USERNAME = "input#ContentPlaceHolder1_loginid"
SEL_PASSWORD = "input#loginpw"
SEL_LOGIN_BTN = "input#login_but"
# 假設登入成功後會有登出按鈕，或者 URL 會改變，這裡預留一個檢查點
SEL_LOGOUT_BTN = "a:has-text('登出')" 

ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")
CF_WAIT_SECONDS = int(os.getenv("CF_WAIT_SECONDS", "6"))

# 真人 User-Agent (Chrome 120 on Windows)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def save_screenshot(page: Page, name: str) -> str:
    """輔助函式：存截圖並回傳路徑"""
    try:
        path = ART_DIR / name
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception as e:
        print(f"截圖失敗 {name}: {e}")
        return ""

def handle_popups(page: Page):
    """
    處理 SweetAlert2 彈窗與可能的全站公告。
    邏輯：
    1. 快速檢查是否有 swal2 按鈕，有就點。
    2. 如果輸入框還沒出現 (被遮擋)，嘗試按 Enter 關閉可能的原生層。
    """
    print("檢查彈跳視窗...")
    
    # 嘗試最多 3 輪，每輪間隔稍短
    for i in range(3):
        try:
            # 1. 優先處理 SweetAlert
            swal_btn = page.locator(SEL_SWAL_CONFIRM).first
            if swal_btn.is_visible(timeout=1000):
                print(f"[{i}] 發現 SweetAlert，點擊確認...")
                swal_btn.click()
                page.wait_for_timeout(500) # 等待動畫消失
                continue
            
            # 2. 如果登入框還不可見，嘗試按 Enter (盲解其他遮罩)
            if not page.locator(SEL_USERNAME).is_visible():
                print(f"[{i}] 登入框被遮擋，嘗試按 Enter...")
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)
            else:
                # 登入框可見，應該沒有彈窗了
                print("登入框已可見，停止處理彈窗。")
                break
                
        except Exception as e:
            print(f"處理彈窗時發生輕微異常 (可忽略): {e}")

def check_cloudflare(page: Page):
    """
    檢查是否有明顯的 Cloudflare 阻擋
    """
    print("檢查 Cloudflare 狀態...")
    # 稍微等待讓 JS 執行
    page.wait_for_timeout(2000) 
    
    # 檢查常見的 Challenge 特徵
    cf_selectors = [
        "iframe[src*='challenges.cloudflare.com']",
        "#cf-challenge-running",
        "div.cf-turnstile"
    ]
    
    found = False
    for sel in cf_selectors:
        if page.locator(sel).count() > 0:
            print(f"⚠️ 偵測到 Cloudflare 元件: {sel}")
            found = True
            break
            
    save_screenshot(page, "check_cloudflare.png")
    
    if found:
        print(f"等待 {CF_WAIT_SECONDS} 秒讓 Cloudflare 驗證通過...")
        page.wait_for_timeout(CF_WAIT_SECONDS * 1000)
    else:
        print("未偵測到明顯阻擋，繼續執行。")

def run():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("缺少 BOOKING_USERNAME 或 BOOKING_PASSWORD")

    with sync_playwright() as p:
        # --- 啟動瀏覽器 (加入 Stealth 參數) ---
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", # 重要：隱藏自動化特徵
                "--no-sandbox",
                "--disable-infobars",
                "--disable-setuid-sandbox"
            ]
        )
        
        # 設定 Context (視窗大小與 User-Agent)
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=USER_AGENT,
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        
        # 開啟 Trace (除錯神器)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        
        page = context.new_page()

        try:
            print(f"前往: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            save_screenshot(page, "01_loaded.png")

            # 1. 處理彈窗
            handle_popups(page)
            
            # 2. 檢查 Cloudflare (並截圖)
            check_cloudflare(page)

            # 3. 填寫登入資訊
            print("填寫登入資訊...")
            # 確保輸入框是可以操作的狀態
            page.wait_for_selector(SEL_USERNAME, state="visible", timeout=10000)
            
            # 模擬人類輸入速度 (非必要，但有助於繞過某些簡單偵測)
            page.fill(SEL_USERNAME, USERNAME)
            page.wait_for_timeout(300) 
            page.fill(SEL_PASSWORD, PASSWORD)
            
            save_screenshot(page, "02_filled.png")

            # 4. 點擊登入
            print("點擊登入...")
            # 有時候 click 會因為 overlay 失敗，這裡用 force=True 或者 js click 會比較保險，但先試標準 click
            page.click(SEL_LOGIN_BTN)
            
            # 5. 驗證結果
            # 這裡需要等待導航完成或特定元素出現
            # 因為點擊按鈕後通常會 PostBack，我們等待網路閒置或 URL 改變
            try:
                # 這裡設定等待導航，如果只是 AJAX 則需要改用 wait_for_response 或 wait_for_selector
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass # 有時候 PostBack 不會觸發完整的 load event

            save_screenshot(page, "03_after_login.png")
            
            # 簡單判斷：如果還在登入頁且有錯誤訊息? 或是 URL 變了?
            # 假設 URL 改變即成功 (您可以根據實際情況調整判斷邏輯)
            if "login" not in page.url or page.locator("text='登出'").count() > 0:
                 print("✅ 登入似乎成功 (URL 改變或發現登出按鈕)")
            else:
                 print("❓ 登入狀態未明，請檢查截圖 03_after_login.png")

        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
            save_screenshot(page, "99_error.png")
            raise
        finally:
            # 匯出 Trace zip
            trace_path = ART_DIR / "trace.zip"
            context.tracing.stop(path=str(trace_path))
            print(f"Trace 已儲存至: {trace_path}")
            browser.close()

if __name__ == "__main__":
    run()
