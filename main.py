import time
import random
import re
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


# ======================================================
#                      НАСТРОЙКИ
# ======================================================
TARGET_URL = "https://www.ozon.ru/category/smartfony-15502/"
OUTPUT_FILE = "ozon_data.csv"
MAX_ITEMS_TO_SCRAPE = 1500     # сколько товаров нужно


# ======================================================
#              НАСТРОЙКА SELENIUM
# ======================================================
options = Options()
# options.add_argument("--headless")

options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
)
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)


# ======================================================
#            ФУНКЦИЯ ПОЛУЧЕНИЯ ПРОДАВЦА
# ======================================================
def get_seller(driver):

    try:
        seller_el = driver.find_element(
            By.XPATH,
            "//*[contains(@class, 'b35_3_16') and string-length(text()) > 3]"
        )
        txt = seller_el.text.strip()
        if txt:
            return txt
    except:
        pass

    try:
        go_btn = driver.find_element(By.XPATH, "//span[contains(text(), 'Перейти')]")
        prev = go_btn.find_element(By.XPATH, "./preceding::span[1]")
        txt = prev.text.strip()
        if txt:
            return txt
    except:
        pass

    return "Не найден"


# ======================================================
#            ПАРСИНГ СТРАНИЦЫ ОТЗЫВОВ
# ======================================================
def parse_review_page(driver):
    review_text = None
    rating_value = None
    first_review_date = None
    price_raw = None

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
    except:
        body_text = ""

    # ===== Цена =====
    try:
        price_raw = driver.find_element(
            By.XPATH, "//span[contains(text(), '₽')]"
        ).text.strip()
    except:
        price_raw = None

    # ===== Рейтинг =====
    try:
        rating_el = driver.find_element(
            By.XPATH,
            "//*[contains(@class, 'zM_28') and contains(text(), '/')]"
        )
        rating_text = rating_el.text.strip()

        m = re.search(r"(\d+[\.,]?\d*)\s*/\s*5", rating_text)
        if m:
            rating_value = float(m.group(1).replace(",", "."))
    except:
        pass

    # fallback — по всему тексту
    if rating_value is None and body_text:
        m = re.search(r"(\d+[\.,]?\d*)\s*/\s*5", body_text)
        if m:
            rating_value = float(m.group(1).replace(",", "."))

    # ===== Дата =====
    # формат: 7 декабря 2025
    months = ("января|февраля|марта|апреля|мая|июня|июля|августа|"
              "сентября|октября|ноября|декабря")

    try:
        matches = re.findall(
            rf"\b\d{{1,2}}\s+(?:{months})\s+\d{{4}}\b",
            body_text, flags=re.IGNORECASE
        )
        if matches:
            first_review_date = matches[0]
    except:
        pass

    # ===== Текст отзывов =====
    try:
        review_elements = driver.find_elements(
            By.XPATH,
            "//div//span[string-length(text()) > 40]"
        )
        texts = [el.text.strip() for el in review_elements[:3]]
        review_text = " || ".join(texts)
    except:
        review_text = None

    return review_text, rating_value, first_review_date, price_raw


# ======================================================
#             ГЛУБОКИЙ СКРОЛЛ (INFINITE SCROLL)
# ======================================================
print("Открываю категорию…")
driver.get(TARGET_URL)
time.sleep(5)

links = set()
last_height = 0
same_height_count = 0
NEED = MAX_ITEMS_TO_SCRAPE

print("Начинаю глубокую прокрутку…")

for i in range(400):
    driver.execute_script("window.scrollBy(0, 2500);")
    time.sleep(1.3)

    # собираем ссылки
    items = driver.find_elements(
        By.XPATH,
        "//a[contains(@href, '/product/') and not(contains(@href, '/reviews/'))]"
    )

    for item in items:
        href = item.get_attribute("href")
        if href:
            links.add(href.split("?")[0])

    print(f"Скролл {i+1}/400 — собрано {len(links)} ссылок")

    if len(links) >= NEED:
        print("Достигнуто нужное количество ссылок!")
        break

    # конец ленты?
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        same_height_count += 1
        if same_height_count > 5:
            print("Похоже, товаров больше нет — достигнут конец ленты.")
            break
    else:
        same_height_count = 0

    last_height = new_height


print(f"\nИТОГО НАЙДЕНО ССЫЛОК: {len(links)}\n")


# ======================================================
#         ПАРСИНГ КАЖДОГО ТОВАРА
# ======================================================
data = []

for idx, link in enumerate(list(links)[:MAX_ITEMS_TO_SCRAPE]):

    # промежуточное сохранение → каждые 50 товаров
    if idx % 50 == 0 and idx > 0:
        pd.DataFrame(data).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print("Промежуточное сохранение. Пауза 25 сек.")
        time.sleep(25)

    try:
        # ----- Загружаем карточку -----
        driver.get(link)
        time.sleep(random.uniform(2.0, 3.5))

        try:
            title = driver.find_element(By.TAG_NAME, "h1").text
        except:
            title = "Название не найдено"

        seller = get_seller(driver)

        # ----- Переход на отзывы -----
        reviews_url = link + "reviews/"
        driver.get(reviews_url)
        time.sleep(random.uniform(3, 5))

        review_text, rating, date_first, price_raw = parse_review_page(driver)

        row = {
            "Наименование": title,
            "Продавец": seller,
            "Цена_raw": price_raw,
            "Рейтинг": rating,
            "Дата_первого_отзыва": date_first,
            "Ссылка": link,
            "Текст_отзыва": review_text
        }

        data.append(row)

        print(
            f"[{idx+1}] {title[:50]}... | {seller} | Рейтинг={rating} | Дата={date_first}"
        )

    except Exception as e:
        print(f"[{idx+1}] Ошибка на товаре: {e}")
        continue


# ======================================================
#               ФИНАЛЬНОЕ СОХРАНЕНИЕ
# ======================================================
df = pd.DataFrame(data)
df["len_review"] = df["Текст_отзыва"].apply(lambda x: len(str(x)))

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print("\n===================================")
print("     ГОТОВО! Данные сохранены.     ")
print("===================================\n")
