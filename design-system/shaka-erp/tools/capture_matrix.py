"""Capture the redesign's standard screens into a folder (one scheme and width per run).

    SCHEME=dark W=768 <playwright-python> design-system/shaka-erp/tools/capture_matrix.py .impeccable/review/<task>/en

Needs Playwright (`pip install playwright && playwright install chromium`) and a logged-in
`session_id` cookie value in `.impeccable/session_id` (gitignored); Claude never types passwords.
For fa_IR, switch the user's language, then rerun into a `fa` folder. Deep links use the
legacy `/web#action=<id>` form because `/shaka/action-…` routes aren't parsed (router.js:188).
Action ids are from the `shaka_design` DB: 334 leads, 337 pipeline, 87 settings, 125 Discuss,
715 Budget Plan, 707 Category Manager.
"""
import os, sys, pathlib
from playwright.sync_api import sync_playwright

B = "http://localhost:8069"
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SID = pathlib.Path(".impeccable/session_id").read_text().strip()
SCHEME = os.environ.get("SCHEME", "light")
W = int(os.environ.get("W", "1440"))


def settle(p):
    p.wait_for_load_state("load")
    p.wait_for_timeout(1800)


def shot(p, name):
    p.screenshot(path=str(OUT / f"{name}-{SCHEME}-{W}.png"))
    print("ok", name)


def go(p, path, name, sel=None):
    try:
        p.goto(B + path); settle(p)
        if sel:
            p.wait_for_selector(sel, timeout=10000)
        p.wait_for_timeout(500)
        shot(p, name)
    except Exception as e:
        print("FAIL", name, e)


with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": W, "height": 900}, color_scheme=SCHEME)
    ctx.add_cookies([{"name": "session_id", "value": SID, "url": B}])
    if SCHEME == "dark":
        ctx.add_cookies([{"name": "color_scheme", "value": "dark", "url": B}])
    p = ctx.new_page()

    go(p, "/shaka", "01-home-menu", ".o_home_menu, .o_app")
    try:
        p.keyboard.press("Control+k"); p.wait_for_selector(".o_command_palette", timeout=5000)
        p.wait_for_timeout(500); shot(p, "02-command-palette"); p.keyboard.press("Escape")
    except Exception as e:
        print("FAIL palette", e)
    go(p, "/web#action=334&view_type=list", "03-list", ".o_list_view")
    go(p, "/web#action=337", "05-kanban", ".o_kanban_view")
    try:
        p.goto(B + "/web#model=project.task&id=2&view_type=form"); settle(p); p.wait_for_selector(".o_form_view", timeout=10000)
        shot(p, "04-form-chatter-statusbar")
        p.locator(".o_cp_action_menus button").first.click(); p.wait_for_timeout(700); shot(p, "07-dropdown")
        p.locator(".o-dropdown--menu .o-dropdown-item", has_text="Delete").first.click()
        p.wait_for_selector(".modal-dialog", timeout=8000); p.wait_for_timeout(700); shot(p, "06-dialog")
        p.locator(".modal-footer button", has_text="Cancel").first.click()
    except Exception as e:
        print("FAIL form/dropdown/dialog", e)
    go(p, "/web#action=87", "08-settings", ".o_setting_container, .settings")
    go(p, "/web#action=125", "09-discuss", ".o-mail-Discuss")
    go(p, "/web#action=715", "11-budget-plan", ".o_action")
    try:
        p.click(".o_control_panel_main_buttons .o_list_button_add, .o-kanban-button-new", timeout=5000); settle(p); shot(p, "11b-budget-plan-form")
    except Exception as e:
        print("FAIL budget form", e)
    go(p, "/web#action=707", "12-category-manager")

    lp = br.new_context(viewport={"width": W, "height": 900}, color_scheme=SCHEME).new_page()
    lp.goto(B + "/web/login?db=shaka_design"); settle(lp)
    lp.screenshot(path=str(OUT / f"10-login-{SCHEME}-{W}.png")); print("ok login")
    br.close()
