import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re

# ------------------------------------------------------
#                 1. Загрузка данных
# ------------------------------------------------------

df = pd.read_csv("ozon_data.csv", encoding="utf-8-sig")

print("Размер датасета:", df.shape)
print(df.head())


# ------------------------------------------------------
#                 2. Предобработка
# ------------------------------------------------------

# очистка цены от символов
df["Цена"] = (
    df["Цена_raw"]
    .astype(str)
    .str.replace("₽", "", regex=False)
    .str.replace(" ", "", regex=False)
    .str.extract(r"(\d+)")
)
df["Цена"] = pd.to_numeric(df["Цена"], errors="coerce")

# рейтинг в число
df["Рейтинг"] = pd.to_numeric(df["Рейтинг"], errors="coerce")

# дата (строка)
df["Дата_первого_отзыва_clean"] = df["Дата_первого_отзыва"].astype(str).str.strip()

# обработка русской даты → datetime
MONTHS = {
    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12"
}


def parse_russian_date(text):
    if not isinstance(text, str):
        return None
    parts = text.split()
    if len(parts) != 3:
        return None
    day, month, year = parts
    month = MONTHS.get(month.lower(), None)
    if month is None:
        return None
    return f"{year}-{month}-{int(day):02d}"


df["Дата_dt"] = df["Дата_первого_отзыва_clean"].apply(parse_russian_date)
df["Дата_dt"] = pd.to_datetime(df["Дата_dt"], errors="coerce")

# удаление дубликатов
df = df.drop_duplicates(subset=["Ссылка"])

# удаляем строки без имени/цены/рейтинга (после приведения типов!)
df = df.dropna(subset=["Наименование", "Цена", "Рейтинг"])

print("После очистки:", df.shape)


# ------------------------------------------------------
#              3. Пользовательские метрики
# ------------------------------------------------------

# если len_review уже есть в csv — оставим; если нет, пересчитаем
if "len_review" not in df.columns:
    df["len_review"] = df["Текст_отзыва"].astype(str).apply(len)
else:
    df["len_review"] = df["len_review"].fillna(
        df["Текст_отзыва"].astype(str).apply(len)
    )

df["has_review"] = df["Текст_отзыва"].apply(lambda x: x != "Отзывы не найдены.")
df["price_log"] = np.log1p(df["Цена"])

# Группы рейтингов
df["rating_group"] = pd.cut(
    df["Рейтинг"],
    bins=[0, 3, 4, 4.5, 5],
    labels=["плохие", "средние", "хорошие", "отличные"],
    include_lowest=True
)

df["year_review"] = df["Дата_dt"].dt.year


def detect_theme(text):
    text = str(text).lower()
    if any(word in text for word in ["камера", "фото", "видео"]):
        return "камера"
    if any(word in text for word in ["батаре", "аккумуля"]):
        return "батарея"
    if any(word in text for word in ["экран", "дисплей"]):
        return "экран"
    if any(word in text for word in ["скорост", "быстр", "лаг"]):
        return "производительность"
    return "прочее"


df["theme"] = df["Текст_отзыва"].apply(detect_theme)


# ------------------------------------------------------
#              4. 15 характеристик данных
# ------------------------------------------------------

print("\n=== 15 аналитических характеристик ===")

print("1) Средняя цена:", df["Цена"].mean())
print("2) Медианная цена:", df["Цена"].median())
print("3) Минимальная цена:", df["Цена"].min())
print("4) Максимальная цена:", df["Цена"].max())
print("5) Средний рейтинг:", df["Рейтинг"].mean())
print("6) Распределение рейтингов (первые значения):\n", df["Рейтинг"].value_counts().head())
print("7) Кол-во товаров с отзывами:", df["has_review"].sum())
print("8) Средняя длина отзывов:", df["len_review"].mean())
print("9) Самый распространённый продавец:", df["Продавец"].mode()[0])
print("10) Топ-5 продавцов:\n", df["Продавец"].value_counts().head())
print("11) Корреляция цена–рейтинг:\n", df[["Цена", "Рейтинг"]].corr())
print("12) Самые частые темы отзывов:\n", df["theme"].value_counts())
print("13) Кол-во отзывов по годам:\n", df["year_review"].value_counts().sort_index())
print("14) Средний рейтинг по темам:\n", df.groupby("theme")["Рейтинг"].mean())
print("15) Средняя цена по продавцам (топ-5):\n", df.groupby("Продавец")["Цена"].mean().sort_values(ascending=False).head())


# ------------------------------------------------------
#                   5. ГРАФИКИ
# ------------------------------------------------------

plt.style.use("ggplot")

# 1 — распределение цен
plt.figure(figsize=(10, 5))
plt.hist(df["Цена"], bins=40)
plt.title("Распределение цен")
plt.xlabel("Цена")
plt.ylabel("Количество товаров")
plt.show()
print("\nВывод: большинство товаров сконцентрировано в одном ценовом диапазоне.")

# 2 — распределение рейтингов
plt.figure(figsize=(10, 5))
plt.hist(df["Рейтинг"], bins=20)
plt.title("Распределение рейтингов")
plt.xlabel("Рейтинг")
plt.ylabel("Количество товаров")
plt.show()
print("Вывод: рейтинг смещён в сторону высоких значений (4+).")

# 3 — средняя цена по продавцам (топ-10)
top_sellers = df["Продавец"].value_counts().head(10).index
plt.figure(figsize=(12, 5))
df[df["Продавец"].isin(top_sellers)].groupby("Продавец")["Цена"].mean().plot(kind="bar")
plt.title("Средняя цена у топ-10 продавцов")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
print("Вывод: у некоторых продавцов средняя цена заметно выше средней по выборке.")

# 4 — длина отзывов
plt.figure(figsize=(10, 5))
plt.hist(df["len_review"], bins=40)
plt.title("Длина отзывов")
plt.xlabel("Длина текста")
plt.ylabel("Количество товаров")
plt.show()
print("Вывод: преобладают короткие и средние по длине отзывы.")

# 5 — цена vs рейтинг
plt.figure(figsize=(8, 5))
plt.scatter(df["Цена"], df["Рейтинг"], s=10, alpha=0.6)
plt.title("Зависимость цены от рейтинга")
plt.xlabel("Цена")
plt.ylabel("Рейтинг")
plt.show()
print("Вывод: явной линейной зависимости цена–рейтинг не наблюдается.")

# 6 — темы отзывов
plt.figure(figsize=(8, 4))
df["theme"].value_counts().plot(kind="bar")
plt.title("Темы отзывов")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
print("Вывод: чаще всего пользователи затрагивают тему ... (камера/батарея/экран — смотри график).")

# 7 — средний рейтинг по темам
plt.figure(figsize=(8, 4))
df.groupby("theme")["Рейтинг"].mean().plot(kind="bar")
plt.title("Средний рейтинг по темам отзывов")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
print("Вывод: по некоторым темам рейтинг выше (например, ...).")

# 8 — кол-во товаров по годам отзывов
plt.figure(figsize=(8, 4))
df["year_review"].value_counts().sort_index().plot(kind="bar")
plt.title("Годы первых отзывов")
plt.xlabel("Год")
plt.ylabel("Количество товаров")
plt.tight_layout()
plt.show()
print("Вывод: основная масса отзывов приходится на последние годы.")

# 9 — boxplot: цена по темам
plt.figure(figsize=(10, 5))
df.boxplot(column="Цена", by="theme")
plt.title("Распределение цен по темам отзывов")
plt.suptitle("")
plt.xlabel("Тема")
plt.ylabel("Цена")
plt.tight_layout()
plt.show()
print("Вывод: по разным темам разброс цен заметно отличается.")


# ------------------------------------------------------
#              6. Подготовка к GigaChat
# ------------------------------------------------------

sample_for_giga = df.sample(200, random_state=42)[["Текст_отзыва", "theme", "Рейтинг"]]
sample_for_giga.to_csv("giga_input.csv", index=False, encoding="utf-8-sig")

print("\nФайл giga_input.csv создан — можно отправлять 200 строк в GigaChat.")