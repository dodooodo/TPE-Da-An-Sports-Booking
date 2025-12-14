import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

LOGIN_URL = "https://www.cjcf.com.tw/CG02.aspx?module=login_page&files=login"

# 你提供的 selectors
SEL_SWAL_CONFIRM = "button.swal2-confirm"
SEL_USERNAME = "input#ContentPlaceHolder1_loginid"
SEL_PASSWORD = "input#loginpw"
SEL_LOGIN_BTN = "input#login_but"

ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = os.getenv("BOOKING_USERNAME", "")
PASSWORD = os.getenv("BOOKING_PASSWORD", "")

CF_WAIT_SECONDS = int(os.getenv("CF_WAIT_SECONDS", "6"))

def save_screenshot(page, name: str) -> str:
    path = ART_DIR / name
    page.screenshot(path=str(path), full_page=True)
    return str(path)

def try_swallow_popups(page, enter_times: int = 6) -> int:
    """
    你說有數個彈跳視窗需要 press Enter 數次 + 有 swal2-confirm 需要點。
    這裡做：
    - 每輪：先嘗試點 swal2-confirm（若存在且可見）→ 再按 Enter
    """
    pressed = 0
    for _ in range(enter_times):
        # 點 swal2-confirm（如果有）
        try:
            btn = page.locator(SEL_SWAL_CONFIRM)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=700)
        except Exception:
            pass

        # 按 Enter
        try:
            page.keyboard.press("Enter")
            pressed += 1
            page.wait_for_timeout(350)
        except Exception:
            break
    return pressed

def note_cloudflare_and_wait(page) -> str:
    """
    Cloudflare 驗證：
    - 我們不做繞過/破解
    - 先等待幾秒（你說需要等）
    - 嘗試偵測是否有明顯 challenge iframe（僅偵測、做註記）
    - 截圖留存
    """
    page.wait_for_timeout(CF_WAIT_SECONDS * 1000)

    candidates = [
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='turnstile']",
        "div.cf-turnstile",
        "iframe[title*='Cloudflare']",
    ]

    found = []
    for sel in candidates:
        try:
            if page.locator(sel).count() > 0:
                found.append(sel)
        except Exception:
            pass

    save_screenshot(page, "after_cf_wait.png")

    if found:
        return (
            "Cloudflare 可能存在驗證元件（僅偵測）："
            + ", ".join(found)
            + f"；已等待 {CF_WAIT_SECONDS}s 並截圖 after_cf_wait.png。"
        )
    return f"Cloudflare 未偵測到明顯驗證元件；已等待 {CF_WAIT_SECONDS}s 並截圖 after_cf_wait.png。"

def main():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("缺少 BOOKING_USERNAME 或 BOOKING_PASSWORD（請在 GitHub Secrets 設定）")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 可視情況調整 user agent / viewport（先保持簡單）
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        # 原生 JS dialog（alert/confirm）自動接受
        page.on("dialog", lambda d: d.accept())

        # 啟用 trace：失敗時更好查
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
            save_screenshot(page, "loaded_login_page.png")

            presses = try_swallow_popups(page, enter_times=6)
            save_screenshot(page, "after_popups.png")

            page.wait_for_selector(SEL_USERNAME, timeout=20_000)
            page.fill(SEL_USERNAME, USERNAME)

            page.wait_for_selector(SEL_PASSWORD, timeout=20_000)
            page.fill(SEL_PASSWORD, PASSWORD)

            cf_note = note_cloudflare_and_wait(page)

            page.wait_for_selector(SEL_LOGIN_BTN, timeout=20_000)
            page.click(SEL_LOGIN_BTN)

            # 目前還不知道「登入成功」的判斷條件，所以先用短暫等待 + 截圖
            page.wait_for_timeout(3000)
            save_screenshot(page, "after_click_login.png")

            print("✅ 完成：已執行登入流程")
            print(f"- Enter 次數：約 {presses}")
            print(f"- {cf_note}")
            print("- 已輸出 artifacts/ 內的截圖供檢查")

        except Exception:
            save_screenshot(page, "error_state.png")
            raise
        finally:
            # 永遠輸出 trace（成功/失敗都保留，方便下一步調整）
            trace_path = ART_DIR / "trace.zip"
            context.tracing.stop(path=str(trace_path))
            browser.close()

if __name__ == "__main__":
    main()
