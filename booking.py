import os
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import stealth_sync  # 記得 import

# --- 設定區 ---
LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"
SEL_SWAL_CONFIRM = "button.swal2-confirm"
SEL_USERNAME = "input#ContentPlaceHolder1_loginid"
SEL_PASSWORD = "input#loginpw"
SEL_LOGIN_BTN = "input#login_but"

ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")
CF_WAIT_SECONDS = int(os.getenv("CF_WAIT_SECONDS", "10"))

# 與 Xvfb 設定一致的 User Agent
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def save_screenshot(page: Page, name: str):
    try:
        path = ART_DIR / name
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass

def random_mouse_move(page: Page, times=5):
    """
    模擬人類隨機移動滑鼠，這對 Cloudflare Turnstile 非常重要。
    它會偵測滑鼠是否「瞬移」(機器人) 還是有軌跡 (人類)。
    """
    print("滑鼠隨機移動中 (模擬真人)...")
    for _ in range(times):
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        # steps 參數讓移動有過程，而不是瞬移
        page.mouse.move(x, y, steps=random.randint(5, 15))
        page.wait_for_timeout(random.randint(100, 300))

def handle_popups(page: Page):
    print("檢查彈窗...")
    for i in range(3):
        try:
            # 1. SweetAlert
            if page.locator(SEL_SWAL_CONFIRM).first.is_visible(timeout=1000):
                print(f"[{i}] 點擊 SweetAlert...")
                page.locator(SEL_SWAL_CONFIRM).first.click()
                page.wait_for_timeout(500)
            
            # 2. 隨機動動滑鼠
            random_mouse_move(page, times=2)
            
            # 3. 嘗試按 Enter 消除原生遮罩
            if not page.locator(SEL_USERNAME).is_visible():
                page.keyboard.press("Enter")
        except Exception:
            pass
        
        # 如果登入框出來了就跳出
        if page.locator(SEL_USERNAME).is_visible():
            break

def run():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("缺少帳號密碼 Secret")

    with sync_playwright() as p:
        # --- 關鍵設定 ---
        # 1. headless=False (配合 Xvfb)
        # 2. 移除 AutomationControlled 特徵
        browser = p.chromium.launch(
            headless=False, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080}, # 配合 Xvfb 解析度
            user_agent=USER_AGENT,
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        
        # 開啟 Trace
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        
        # --- 啟用 Stealth 模式 ---
        stealth_sync(page)

        try:
            print(f"前往登入頁: {LOGIN_URL}")
            # 用 commit 確保載入完成
            page.goto(LOGIN_URL, wait_until="commit", timeout=60000)
            
            # Cloudflare 等待期 (Combined Dance)
            print(f"等待 {CF_WAIT_SECONDS} 秒並進行滑鼠模擬 (繞過 Cloudflare)...")
            start_time = time.time()
            while time.time() - start_time < CF_WAIT_SECONDS:
                random_mouse_move(page, times=3)
                # 檢查是否有 Turnstile iframe，有的話嘗試 hover
                frames = page.frames
                for frame in frames:
                    if "cloudflare" in frame.url or "turnstile" in frame.url:
                        try:
                            # 嘗試把滑鼠移到 iframe 上
                            box = frame.frame_element().bounding_box()
                            if box:
                                cx = box['x'] + box['width'] / 2
                                cy = box['y'] + box['height'] / 2
                                page.mouse.move(cx, cy, steps=10)
                        except:
                            pass
            
            save_screenshot(page, "01_after_cf_wait.png")

            # 處理彈窗
            handle_popups(page)

            # 檢查登入框是否出現
            print("嘗試填寫帳密...")
            page.wait_for_selector(SEL_USERNAME, state="visible", timeout=20000)
            
            # 模擬人類輸入 (打字有間隔)
            page.click(SEL_USERNAME)
            page.keyboard.type(USERNAME, delay=random.randint(50, 150))
            
            page.wait_for_timeout(500)
            
            page.click(SEL_PASSWORD)
            page.keyboard.type(PASSWORD, delay=random.randint(50, 150))
            
            save_screenshot(page, "02_filled.png")

            print("點擊登入...")
            # 有時候用 JS click 比較不會被上方遮罩擋住
            page.click(SEL_LOGIN_BTN)
            
            # 等待跳轉
            print("等待結果...")
            page.wait_for_timeout(5000)
            save_screenshot(page, "03_result.png")

            content = page.content()
            if "登出" in content or "login" not in page.url:
                print("✅ 登入似乎成功")
            else:
                print("❓ 未偵測到登入成功訊號，請檢查截圖")

        except Exception as e:
            print(f"❌ Error: {e}")
            save_screenshot(page, "99_error.png")
            raise
        finally:
            trace_path = ART_DIR / "trace.zip"
            context.tracing.stop(path=str(trace_path))
            browser.close()

if __name__ == "__main__":
    run()
