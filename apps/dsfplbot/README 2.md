# DSFPLBot — исправленная версия (18.02.2026)

## 📋 Анализ и исправления

### Критические баги (исправлены)

| # | Файл | Проблема | Исправление |
|---|------|----------|-------------|
| 1 | `main.py` | Смешение табов и пробелов на `await ensure_user_fpl_table()` → **SyntaxError** при запуске | Переписан полностью, убрана несуществующая функция |
| 2 | `main.py` | Дублированный импорт `from apps.dsfplbot.database` внутри функции | Импорт перенесён в начало, единый блок |
| 3 | `database.py` | Функции `save_user_fpl_id`, `get_user_fpl_id`, `init_games_tables`, `add_score`, `get_scores` определены **2-3 раза** | Все дубликаты удалены, единый `init_db()` |
| 4 | `database.py` | `ensure_user_fpl_table()` не существовала, но вызывалась в main | Единый `init_db()` создаёт ВСЕ таблицы, включая `fpl_links` |
| 5 | `handlers.py` | Мёртвый код в `dssdtempo_get_weeks` повторён **4 раза** после `return ConversationHandler.END` | Удалены все дубликаты, оставлен один рабочий блок |
| 6 | `handlers.py` | `s[rank]`, `s[total_points]`, `s[form]` — синтаксическая ошибка (нужно `s["rank"]`) | Исправлено на `s.get("rank")` |
| 7 | `fpl_data_reader.py` | Запросы к таблицам `league_standings`, `managers`, `manager_history` — **не существуют** в парсере | Исправлено: `league_standings_1125782`, добавлена проверка `_table_exists()` |
| 8 | `questions.json` | Файл в текстовом формате, `json.load()` выбрасывает исключение | `fun.py` переписан с regex-парсером для текстового формата |
| 9 | `requirements.txt` | Полностью пустой — зависимости не устанавливаются | Заполнен всеми необходимыми пакетами |
| 10 | `config.py` | Хардкод токена бота в открытом виде | Убран, токен только из `TELEGRAM_BOT_TOKEN` |

### Улучшения

- **Обработка ошибок**: все функции обёрнуты в try/except с информативными сообщениями
- **LRI из парсера**: `dssdtempo` теперь читает реальный LRI из `lri_scores`
- **Fallback для темпа**: если `manager_history` нет — используется `form_5gw` с пометкой
- **Длинные сообщения**: автоматическое разбиение на части (Telegram лимит 4096 символов)
- **Callback-кнопки**: правильная маршрутизация во всех разделах (Fun, HoF, Other)

---

## 🚀 Инструкция по деплою

### 1. Замена файлов в репозитории

Скопируйте **все файлы** из этого архива в директорию `apps/dsfplbot/` вашего репозитория `DSFPLBot`, заменяя существующие.

**Важно**: НЕ копируйте `.bak.*` файлы — они не нужны.

### 2. Убедитесь, что переменные окружения установлены

В Railway → Settings → Variables:

```
TELEGRAM_BOT_TOKEN=<ваш токен>
FPL_LEAGUE_ID=1125782
ADMIN_USER_ID=74099420
DB_PATH=/data/dsfpl.db
FPL_PARSER_DB_PATH=/data/fpl_data.db
DISABLE_PARSER=1
```

### 3. Редеплой с очисткой кэша

**Вариант A** (Railway CLI):
```bash
railway up --no-cache
```

**Вариант B** (веб-интерфейс Railway):
1. Зайдите в проект → сервис DSFPLBot
2. Нажмите "Redeploy" с опцией "No cache"

### 4. Проверка

```bash
railway logs -s DSFPLBot --tail 50
```

Ожидаемый вывод:
```
=== DSFPLBot STARTING ===
Healthcheck server started on port 8080
Importing modules...
All modules imported successfully
Running post_init...
Database initialized (all tables ensured)
Legacy CSV imported from ...
post_init complete
Bot started
Polling started, bot is running
```

### 5. Тестирование в Telegram

1. `/start` — должен показать список команд с дедлайном
2. `/link` → ввести FPL ID → должно сохраниться без ошибок
3. `/dssdtempo` → ввести 5 → должна показаться таблица с LRI
4. `/fun` → DoubleQuiz → должны появиться вопросы
5. `/halloffame` → выбрать сезон → должна показаться таблица
6. `/other` → настройки → переключить уведомления

---

## 📈 План дальнейшего развития

### Приоритет 1: Добавить `manager_history` в парсер

Парсер DSDeepParser должен собирать очки менеджеров по турам. Endpoint FPL API:
```
GET https://fantasy.premierleague.com/api/entry/{entry_id}/history/
```
Ответ содержит `entry_history` — массив с очками за каждый тур.

**Предлагаемая таблица**:
```sql
CREATE TABLE IF NOT EXISTS manager_history (
    entry_id INTEGER,
    event INTEGER,
    points INTEGER,
    total_points INTEGER,
    rank INTEGER,
    overall_rank INTEGER,
    event_transfers INTEGER,
    event_transfers_cost INTEGER,
    bank INTEGER,
    PRIMARY KEY (entry_id, event)
);
```

### Приоритет 2: Полноценная модель DSSD (21 фактор)

Недостающие данные для полноценного LRI:
- **xG, xA, non_penalty_xG** — нужны данные из FBRef или Understat
- **transfers_in_round** — из bootstrap-static (`transfers_in_event`)
- **opponent_elo** — уже есть в `raw_team_elo`
- **captain_diversity, chips_used, cbit** — вычисляются из picks менеджеров
- **volatility, form_trend** — вычисляются из `manager_history`

### Приоритет 3: Расширение игр

- GTD: полная реализация с сохранением прогнозов и подсчётом результатов
- Чемпионат прогнозов: прогнозы на матчи тура
- Рассылка ежедневного квиза в чат лиги

---

## 📁 Структура файлов

```
apps/dsfplbot/
├── main.py              # Точка входа, healthcheck + бот
├── config.py            # Конфигурация из env vars
├── handlers.py          # Обработчики команд
├── database.py          # Своя БД (fpl_links, игры, HoF)
├── fpl_data_reader.py   # Чтение из БД парсера
├── fpl_api.py           # Прямые запросы к FPL API
├── cache.py             # TTL-кэш для API
├── dssd.py              # LRI + советы
├── dssd_advice.py       # Персональные рекомендации
├── afterdl.py           # Отчёт после дедлайна
├── aftertour.py         # Итоги тура
├── fun.py               # Игры (DoubleQuiz, GTD)
├── halloffame.py        # Зал славы
├── other.py             # Настройки
├── utils.py             # Утилиты
├── requirements.txt     # Зависимости
├── railway.json         # Деплой-конфиг
├── railway.toml         # Билд-конфиг
├── questions.json       # Вопросы для квиза (текстовый формат)
└── FPL League History.csv
```
