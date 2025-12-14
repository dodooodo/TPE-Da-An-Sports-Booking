import os
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# --- 修正 Import 問題：加入防呆機制 ---
# 嘗試多種路徑匯入，如果都失敗則標記為 None，稍後改用手動 Patch
stealth_sync = None
try:
    from playwright_stealth import stealth_sync
except ImportError:
    try:
        # 這是解決您遇到的錯誤的關鍵：直接從子模組匯入
        from playwright_stealth.stealth import stealth_sync
    except ImportError:
        print("⚠️ 警告: 無法匯入 playwright_stealth，將改用手動 JS Patch 模式")
        stealth_sync = None

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
    """模擬人類隨機移動滑鼠"""
    print("滑鼠隨機移動中...")
    for _ in range(times):
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        page.mouse.move(x, y, steps=random.randint(5, 15))
        page.wait_for_timeout(random.randint(100, 300))

def apply_stealth(page: Page):
    """
    統一處理隱身邏輯：
    1. 優先使用套件 (stealth_sync)
    2. 若套件失敗，手動移除 navigator.webdriver 特徵
    """
    if stealth_sync:
        print("🛡️ 啟用 Playwright Stealth (套件模式)")
        stealth_sync(page)
    else:
        print("🛡️ 啟用 Playwright Stealth (手動 Patch 模式)")
        # 這是最核心的反偵測腳本：移除 webdriver 屬性
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

def handle_popups(page: Page):
    print("檢查彈窗...")
    for i in range(3):
        try:
            if page.locator(SEL_SWAL_CONFIRM).first.is_visible(timeout=1000):
                print(f"[{i}] 點擊 SweetAlert...")
                page.locator(SEL_SWAL_CONFIRM).first.click()
                page.wait_for_timeout(500)
            
            random_mouse_move(page, times=1)
            
            if not page.locator(SEL_USERNAME).is_visible():
                page.keyboard.press("Enter")
        except Exception:
            pass
        
        if page.locator(SEL_USERNAME).is_visible():
            break

def run():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("缺少帳號密碼 Secret")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # 配合 Xvfb
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        
        # --- 套用隱身設定 ---
        apply_stealth(page)

        try:
            print(f"前往登入頁: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="commit", timeout=60000)
            
            print(f"等待 {CF_WAIT_SECONDS} 秒並模擬真人行為...")
            start_time = time.time()
            while time.time() - start_time < CF_WAIT_SECONDS:
                random_mouse_move(page, times=3)
                # 簡單的 iframe 互動嘗試
                try:
                    for frame in page.frames:
                        if "cloudflare" in frame.url or "turnstile" in frame.url:
                            box = frame.frame_element().bounding_box()
                            if box:
                                cx = box['x'] + box['width'] / 2
                                cy = box['y'] + box['height'] / 2
                                page.mouse.move(cx, cy, steps=10)
                except:
                    pass
            
            save_screenshot(page, "01_after_cf_wait.png")

            handle_popups(page)

            print("嘗試填寫帳密...")
            page.wait_for_selector(SEL_USERNAME, state="visible", timeout=20000)
            
            page.click(SEL_USERNAME)
            page.keyboard.type(USERNAME, delay=random.randint(50, 150))
            page.wait_for_timeout(300)
            
            page.click(SEL_PASSWORD)
            page.keyboard.type(PASSWORD, delay=random.randint(50, 150))
            
            save_screenshot(page, "02_filled.png")

            print("點擊登入...")
            page.click(SEL_LOGIN_BTN)
            
            print("等待結果...")
            page.wait_for_timeout(5000)
            save_screenshot(page, "03_result.png")

            if "登出" in page.content() or "login" not in page.url:
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
