from playwright.sync_api import TimeoutError


ENV_CONFIG = {
    "PRODUCTION": {
        "url": "https://app.stockount.com",
        "email": "rakeikoppanna-7429@yopmail.com",
        "password": "MeNx6G2S",
    },
    "STAGING": {
        "url": "https://yellow-river-0ebeae800.2.azurestaticapps.net",
        "email": "cucommugeuta-1374@yopmail.com",
        "password": "DWN83oxG",
    },
    "QA": {
        "url": "https://kind-mushroom-018e57a00.1.azurestaticapps.net",
        "email": "broiyeibricribrou-1186@yopmail.com",
        "password": "pVkW9FYo",
    },
    "DEV": {
        "url": "https://nice-water-001254c00.1.azurestaticapps.net",
        "email": "test@gmail.com",
        "password": "87654321",
    },
}


class LoginPage:
    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url.rstrip("/")

    def open(self):
        self.page.goto(
            f"{self.base_url}/#/authorization/login",
            wait_until="domcontentloaded",
        )

    def login(self, email, password):
        self.page.fill("input[formcontrolname='email']", email)
        self.page.fill("input[placeholder='Password']", password)
        self.page.click("button:has-text('Login')")

    def assert_dashboard_loaded(self):
        try:
            self.page.wait_for_selector("img[src*='Item_icon.svg']", timeout=20000)
        except TimeoutError as exc:
            self.page.screenshot(path="login_failure.png")
            raise Exception("Login failed or dashboard not loaded") from exc


def _launch_browser(playwright, browser_name):
    browser_name = browser_name.lower()
    if browser_name == "edge":
        browser = playwright.chromium.launch(
            channel="msedge",
            headless=False,
            args=["--start-maximized"],
            slow_mo=200,
        )
        context = browser.new_context(no_viewport=True)
    elif browser_name == "chrome":
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
            slow_mo=200,
        )
        context = browser.new_context(no_viewport=True)
    elif browser_name == "firefox":
        browser = playwright.firefox.launch(headless=False, slow_mo=200)
        context = browser.new_context(viewport=None)
    else:
        raise ValueError("Invalid browser_name: use edge/chrome/firefox")
    return browser, context


def login(playwright, browser_name="chrome", environment="QA", email=None, password=None):
    env = environment.upper()
    if env not in ENV_CONFIG:
        raise ValueError(f"Invalid environment: {environment}")

    config = ENV_CONFIG[env].copy()
    if email:
        config["email"] = email
    if password:
        config["password"] = password

    browser, context = _launch_browser(playwright, browser_name)
    page = context.new_page()

    login_page = LoginPage(page, base_url=config["url"])
    login_page.open()
    login_page.login(config["email"], config["password"])
    login_page.assert_dashboard_loaded()

    print(f"Logged in -> {env} using {browser_name.upper()}")
    print(f"Login successful | email: {config['email']}")
    return browser, page
