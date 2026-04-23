from datetime import datetime
import pytz
import difflib
import random
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


# ---------------------------------------
# FORMAT UTC OFFSET
# ---------------------------------------
def format_offset(offset_hours):
    offset_hours = float(offset_hours)
    sign = "+" if offset_hours >= 0 else "-"
    abs_hours = abs(offset_hours)
    h = int(abs_hours)
    m = int(round((abs_hours - h) * 60))
    return f"{sign}{h}" if m == 0 else f"{sign}{h}:{m:02d}"


# ---------------------------------------
# SAFE CLICK
# ---------------------------------------
def safe_click(locator):
    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible", timeout=15000)
    locator.scroll_into_view_if_needed()
    locator.page.wait_for_load_state("networkidle")
    try:
        locator.click(timeout=10000)
    except:
        locator.click(force=True)


# ---------------------------------------
# DROPDOWN FILTER + SELECT
# ---------------------------------------
def type_in_dropdown_filter_dynamic(page, filter_text):
    filter_input = page.locator("input.p-dropdown-filter").last
    filter_input.wait_for(state="visible", timeout=5000)
    filter_input.click()
    filter_input.clear()

    # Human typing simulation
    for char in filter_text:
        filter_input.type(char, delay=random.randint(60, 140))

    page.wait_for_timeout(600)

    aria_owns = filter_input.get_attribute("aria-owns")
    options_locator = page.locator(f"#{aria_owns} li.p-dropdown-item")
    options_locator.first.wait_for(state="visible", timeout=5000)

    all_options = options_locator.all_inner_texts()

    # Exact match
    if filter_text in all_options:
        matched = filter_text
    else:
        matches = difflib.get_close_matches(filter_text, all_options, n=1, cutoff=0.4)
        if matches:
            matched = matches[0]
            print(f"⚠ Fuzzy match: {filter_text} → {matched}")
        else:
            print("❌ No timezone match found")
            return

    option = page.locator(f"#{aria_owns} li.p-dropdown-item:has-text('{matched}')")
    safe_click(option)
    print(f"✅ Selected: {matched}")


# ---------------------------------------
# SETTINGS PAGE LOGIC
# ---------------------------------------
def settings(page, example_zone):
    try:
        page.locator("button:has(img[src*='white_logo.png'])").click()
        page.wait_for_timeout(1000)
        page.locator("#audit-settings-link").click()
        page.wait_for_timeout(1000)

        page.locator("a[href='/home/company']").first.click()
        page.wait_for_timeout(1000)

        safe_click(page.locator("p-dropdown[formcontrolname='timeZone']"))

        type_in_dropdown_filter_dynamic(page, example_zone)
        page.wait_for_timeout(1000)
        page.locator("button:has-text('Update')").click()
        page.wait_for_timeout(1000)
        page.wait_for_timeout(1000)
        print("✅ Timezone Updated")

    except PlaywrightTimeoutError:
        print("❌ Settings navigation failed")


# ---------------------------------------
# 🔥 DYNAMIC 23:00 NEAREST LOGIC
# ---------------------------------------
def timezone(page):

    # 👉 Paste your FULL timezone list here
    my_timezones = [

# ================= AFRICA =================
"Africa/Abidjan","Africa/Accra","Africa/Addis_Ababa","Africa/Algiers",
"Africa/Asmara","Africa/Bamako","Africa/Bangui","Africa/Banjul",
"Africa/Bissau","Africa/Blantyre","Africa/Brazzaville","Africa/Bujumbura",
"Africa/Cairo","Africa/Casablanca","Africa/Ceuta","Africa/Conakry",
"Africa/Dakar","Africa/Dar_es_Salaam","Africa/Djibouti","Africa/Douala",
"Africa/El_Aaiun","Africa/Freetown","Africa/Gaborone","Africa/Harare",
"Africa/Johannesburg","Africa/Juba","Africa/Kampala","Africa/Khartoum",
"Africa/Kigali","Africa/Kinshasa","Africa/Libreville","Africa/Lome",
"Africa/Luanda","Africa/Lubumbashi","Africa/Lusaka","Africa/Malabo",
"Africa/Maputo","Africa/Maseru","Africa/Mbabane","Africa/Mogadishu",
"Africa/Monrovia","Africa/Nairobi","Africa/Ndjamena","Africa/Niamey",
"Africa/Nouakchott","Africa/Ouagadougou","Africa/Porto-Novo",
"Africa/Sao_Tome","Africa/Tripoli","Africa/Tunis","Africa/Windhoek",

# ================= AMERICA =================
"America/Adak","America/Anchorage","America/Anguilla","America/Antigua",
"America/Araguaina","America/Argentina/Buenos_Aires",
"America/Argentina/Catamarca","America/Argentina/Cordoba",
"America/Argentina/Jujuy","America/Argentina/La_Rioja",
"America/Argentina/Mendoza","America/Argentina/Rio_Gallegos",
"America/Argentina/Salta","America/Argentina/San_Juan",
"America/Argentina/San_Luis","America/Argentina/Tucuman",
"America/Argentina/Ushuaia","America/Aruba","America/Asuncion",
"America/Atikokan","America/Bahia","America/Bahia_Banderas",
"America/Barbados","America/Belem","America/Belize",
"America/Blanc-Sablon","America/Boa_Vista","America/Boise",
"America/Cambridge_Bay","America/Campo_Grande","America/Cancun",
"America/Caracas","America/Cayenne","America/Cayman",
"America/Chicago","America/Chihuahua","America/Costa_Rica",
"America/Creston","America/Cuiaba","America/Curacao",
"America/Danmarkshavn","America/Dawson","America/Dawson_Creek",
"America/Denver","America/Detroit","America/Dominica",
"America/Edmonton","America/Eirunepe","America/El_Salvador",
"America/Fortaleza","America/Glace_Bay","America/Grand_Turk",
"America/Grenada","America/Guadeloupe","America/Guatemala",
"America/Guayaquil","America/Guyana","America/Halifax",
"America/Havana","America/Hermosillo",
"America/Indiana/Indianapolis","America/Indiana/Knox",
"America/Indiana/Marengo","America/Indiana/Petersburg",
"America/Indiana/Tell_City","America/Indiana/Vevay",
"America/Indiana/Vincennes","America/Indiana/Winamac",
"America/Inuvik","America/Iqaluit","America/Jamaica",
"America/Juneau","America/Kentucky/Louisville",
"America/Kentucky/Monticello","America/La_Paz","America/Lima",
"America/Los_Angeles","America/Lower_Princes",
"America/Maceio","America/Managua","America/Manaus",
"America/Martinique","America/Matamoros","America/Mazatlan",
"America/Menominee","America/Merida","America/Metlakatla",
"America/Mexico_City","America/Miquelon","America/Moncton",
"America/Monterrey","America/Montevideo","America/Montserrat",
"America/Nassau","America/New_York","America/Nome",
"America/Noronha","America/North_Dakota/Beulah",
"America/North_Dakota/Center","America/North_Dakota/New_Salem",
"America/Ojinaga","America/Panama","America/Pangnirtung",
"America/Paramaribo","America/Phoenix","America/Port-au-Prince",
"America/Port_of_Spain","America/Porto_Velho",
"America/Puerto_Rico","America/Punta_Arenas",
"America/Rainy_River","America/Rankin_Inlet","America/Recife",
"America/Regina","America/Resolute","America/Rio_Branco",
"America/Santarem","America/Santiago","America/Santo_Domingo",
"America/Sao_Paulo","America/Scoresbysund","America/Sitka",
"America/St_Barthelemy","America/St_Johns","America/St_Kitts",
"America/St_Lucia","America/St_Thomas","America/St_Vincent",
"America/Swift_Current","America/Tegucigalpa","America/Thule",
"America/Thunder_Bay","America/Tijuana","America/Toronto",
"America/Tortola","America/Vancouver","America/Whitehorse",
"America/Winnipeg","America/Yakutat","America/Yellowknife",

# ================= ASIA =================
"Asia/Aden","Asia/Almaty","Asia/Amman","Asia/Anadyr",
"Asia/Aqtau","Asia/Aqtobe","Asia/Ashgabat","Asia/Atyrau",
"Asia/Baghdad","Asia/Bahrain","Asia/Baku","Asia/Bangkok",
"Asia/Barnaul","Asia/Beirut","Asia/Bishkek","Asia/Brunei",
"Asia/Chita","Asia/Choibalsan","Asia/Colombo","Asia/Damascus",
"Asia/Dhaka","Asia/Dili","Asia/Dubai","Asia/Dushanbe",
"Asia/Famagusta","Asia/Gaza","Asia/Hebron",
"Asia/Ho_Chi_Minh","Asia/Hong_Kong","Asia/Hovd",
"Asia/Irkutsk","Asia/Jakarta","Asia/Jayapura",
"Asia/Jerusalem","Asia/Kabul","Asia/Kamchatka",
"Asia/Karachi","Asia/Kathmandu","Asia/Khandyga",
"Asia/Kolkata","Asia/Krasnoyarsk","Asia/Kuala_Lumpur",
"Asia/Kuching","Asia/Kuwait","Asia/Macau","Asia/Magadan",
"Asia/Makassar","Asia/Manila","Asia/Muscat",
"Asia/Nicosia","Asia/Novokuznetsk","Asia/Novosibirsk",
"Asia/Omsk","Asia/Oral","Asia/Phnom_Penh",
"Asia/Pontianak","Asia/Pyongyang","Asia/Qatar",
"Asia/Qostanay","Asia/Qyzylorda","Asia/Riyadh",
"Asia/Sakhalin","Asia/Samarkand","Asia/Seoul",
"Asia/Shanghai","Asia/Singapore","Asia/Srednekolymsk",
"Asia/Taipei","Asia/Tashkent","Asia/Tbilisi",
"Asia/Tehran","Asia/Thimphu","Asia/Tokyo",
"Asia/Tomsk","Asia/Ulaanbaatar","Asia/Urumqi",
"Asia/Ust-Nera","Asia/Vientiane","Asia/Vladivostok",
"Asia/Yakutsk","Asia/Yekaterinburg","Asia/Yerevan",

# ================= EUROPE =================
"Europe/Amsterdam","Europe/Andorra","Europe/Astrakhan",
"Europe/Athens","Europe/Belgrade","Europe/Berlin",
"Europe/Bratislava","Europe/Brussels","Europe/Bucharest",
"Europe/Budapest","Europe/Chisinau","Europe/Copenhagen",
"Europe/Dublin","Europe/Gibraltar","Europe/Guernsey",
"Europe/Helsinki","Europe/Isle_of_Man","Europe/Istanbul",
"Europe/Jersey","Europe/Kaliningrad","Europe/Kiev",
"Europe/Kirov","Europe/Lisbon","Europe/Ljubljana",
"Europe/London","Europe/Luxembourg","Europe/Madrid",
"Europe/Malta","Europe/Mariehamn","Europe/Minsk",
"Europe/Monaco","Europe/Moscow","Europe/Oslo",
"Europe/Paris","Europe/Podgorica","Europe/Prague",
"Europe/Riga","Europe/Rome","Europe/Samara",
"Europe/San_Marino","Europe/Sarajevo","Europe/Saratov",
"Europe/Simferopol","Europe/Skopje","Europe/Sofia",
"Europe/Stockholm","Europe/Tallinn","Europe/Tirane",
"Europe/Ulyanovsk","Europe/Uzhgorod","Europe/Vaduz",
"Europe/Vatican","Europe/Vienna","Europe/Vilnius",
"Europe/Volgograd","Europe/Warsaw","Europe/Zagreb",
"Europe/Zaporozhye","Europe/Zurich",

# ================= AUSTRALIA =================
"Australia/Adelaide","Australia/Brisbane","Australia/Broken_Hill",
"Australia/Currie","Australia/Darwin","Australia/Eucla",
"Australia/Hobart","Australia/Lindeman","Australia/Lord_Howe",
"Australia/Melbourne","Australia/Perth","Australia/Sydney"
]

    utc_now = datetime.now(pytz.utc)
    target_seconds = 0  # 🎯 Midnight 00:00:00

    closest_zone = None
    smallest_diff = float("inf")

    for tz_name in my_timezones:
        try:
            tz = pytz.timezone(tz_name)
            local_time = utc_now.astimezone(tz)

            local_seconds = (
                local_time.hour * 3600 +
                local_time.minute * 60 +
                local_time.second
            )

            # 🔥 Circular 24-hour difference
            diff = min(
                abs(local_seconds - target_seconds),
                86400 - abs(local_seconds - target_seconds)
            )

            if diff < smallest_diff:
                smallest_diff = diff
                closest_zone = {
                    "timezone": tz_name,
                    "date_str": local_time.strftime("%Y-%m-%d"),
                    "time_str": local_time.strftime("%H:%M:%S"),
                    "offset": local_time.utcoffset().total_seconds() / 3600
                }

        except:
            continue

    if not closest_zone:
        print("❌ No valid timezone found")
        return

    print("🎯 Nearest to 00:00 selected")
    print(f"🕐 Selected Timezone : {closest_zone['timezone']}")
    print(f"📅 Local Date        : {closest_zone['date_str']}")
    print(f"🕐 Local Time        : {closest_zone['time_str']}")
    print(f"🌍 UTC Offset        : {format_offset(closest_zone['offset'])}")

    # 🔥 Pass timezone only (or pass date also if needed)
    settings(page, closest_zone["timezone"])

    