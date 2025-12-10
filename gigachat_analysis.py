import os
import time
import json
import pandas as pd
from gigachat import GigaChat

# ============================================================
# 1. ЗАГРУЗКА ОТЗЫВОВ
# ============================================================

df = pd.read_csv("giga_input.csv", encoding="utf-8-sig").head(200)

if "Текст_отзыва" not in df.columns:
    raise ValueError("Файл giga_input.csv должен содержать колонку 'Текст_отзыва'")

texts = df["Текст_отзыва"].tolist()
print(f"\nЗагружено {len(texts)} отзывов для анализа.\n")

# ============================================================
# 2. ИНИЦИАЛИЗАЦИЯ КЛИЕНТА GigaChat
# ============================================================

auth_key = os.getenv("GIGACHAT_AUTH_KEY")

if not auth_key:
    raise ValueError(
        "❌ Переменная среды GIGACHAT_AUTH_KEY не найдена.\n"
        "Установите её командой (PowerShell):\n\n"
        '   setx GIGACHAT_AUTH_KEY "ВАШ_ТОКЕН"\n'
    )

client = GigaChat(credentials=auth_key, verify_ssl_certs=False)


# ============================================================
# 3. ФУНКЦИЯ АНАЛИЗА ОТДЕЛЬНОГО ОТЗЫВА
# ============================================================

def analyze_text(text):
    prompt = f"""
Ты — аналитик отзывов. Проанализируй текст и верни СТРОГО JSON:

{{
  "sentiment": "positive/neutral/negative",
  "emotions": ["emotion1"],
  "topics": ["topic1"],
  "quality": 1–10,
  "summary": "краткое резюме"
}}

Текст:
\"\"\"{text}\"\"\"
"""

    # -------------------------------
    # 3 попытки при сетевых ошибках
    # -------------------------------
    for attempt in range(3):
        try:
            response = client.chat(prompt)
            break
        except Exception as e:
            print(f"⚠ Ошибка сети (попытка {attempt + 1}/3): {e}")
            time.sleep(2)
    else:
        return {
            "sentiment": None,
            "emotions": None,
            "topics": None,
            "quality": None,
            "summary": "Ошибка сети"
        }

    # -------------------------------
    # ПРАВИЛЬНОЕ получение текста ответа
    # -------------------------------
    try:
        raw = response.choices[0].message.content
    except Exception:
        print("⚠ Не удалось извлечь content из ответа:", response)
        return {
            "sentiment": None,
            "emotions": None,
            "topics": None,
            "quality": None,
            "summary": str(response)
        }

    # -------------------------------
    # Очистка мусора
    # -------------------------------
    clean = (
        raw.replace("```json", "")
        .replace("```", "")
        .replace("json", "")
        .strip()
    )

    # -------------------------------
    # Извлечение JSON по фигурным скобкам
    # -------------------------------
    if "{" in clean and "}" in clean:
        start = clean.index("{")
        end = clean.rindex("}") + 1
        json_text = clean[start:end]
    else:
        print("⚠ JSON не найден, ответ модели:", clean)
        return {
            "sentiment": None,
            "emotions": None,
            "topics": None,
            "quality": None,
            "summary": clean
        }

    # -------------------------------
    # Попытка распарсить JSON
    # -------------------------------
    try:
        return json.loads(json_text)
    except Exception:
        print("⚠ Ошибка JSON! Модель прислала:\n", raw)
        return {
            "sentiment": None,
            "emotions": None,
            "topics": None,
            "quality": None,
            "summary": raw
        }


# ============================================================
# 4. АНАЛИЗ ВСЕХ 200 ОТЗЫВОВ
# ============================================================

results = []

for i, text in enumerate(texts, start=1):
    print(f"[{i}/200] Анализ...")

    data = analyze_text(text)

    results.append({
        "Текст_отзыва": text,
        "sentiment": data.get("sentiment"),
        "emotions": data.get("emotions"),
        "topics": data.get("topics"),
        "quality": data.get("quality"),
        "summary": data.get("summary"),
    })

    time.sleep(1)


# ============================================================
# 5. СОХРАНЕНИЕ ИТОГОВ В CSV
# ============================================================

df_out = pd.DataFrame(results)
df_out.to_csv("giga_output.csv", index=False, encoding="utf-8-sig")

print("\n🎉 Готово! Файл giga_output.csv успешно сохранён.\n")