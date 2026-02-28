# Локальный запуск проекта для тестирования функциональности

Ниже — пошаговая инструкция, как поднять проект на локальном компьютере, проверить API, фронтенд и прогнать автотесты.

## 1) Что нужно установить заранее

- Python **3.11+**
- PostgreSQL (локально)
- Git
- (Опционально) `make` для удобных команд

Проверка версий:

```bash
python3 --version
psql --version
git --version
```

## 2) Клонирование репозитория и виртуальное окружение

```bash
git clone <repo-url>
cd Eclipse-for-FF
python3.11 -m venv venv
source venv/bin/activate
```

> Для Windows (PowerShell): `venv\Scripts\Activate.ps1`

## 3) Установка зависимостей

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

или через `make`:

```bash
make dev-install
```

## 4) Настройка переменных окружения

```bash
cp .env.example .env
```

Минимально проверьте в `.env`:

- `DATABASE_URL` (по умолчанию указывает на локальный PostgreSQL)
- `SECRET_KEY` (поставьте длинное случайное значение)

Пример локального подключения к БД (уже есть в `.env.example`):

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/eclipse_game
```

## 5) Создание БД и миграции

Убедитесь, что PostgreSQL запущен, затем:

```bash
make dev-db
make migrate
```

Альтернатива без `make`:

```bash
createdb eclipse_game
alembic upgrade head
```

## 6) Запуск приложения

```bash
make run
```

или напрямую:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

После запуска:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Frontend: http://localhost:8000/static/index.html

## 7) Быстрая проверка, что всё работает

### Проверка health endpoint

```bash
curl http://localhost:8000/health
```

Ожидаемо: JSON с `status` и HTTP 200.

### Базовая проверка фронтенда

Откройте в браузере:

- http://localhost:8000/static/index.html

Проверьте, что загружается игровое поле и нет ошибок 500 в DevTools/Network.

## 8) Запуск автотестов

Полный прогон:

```bash
make test
```

или:

```bash
pytest
```

С покрытием:

```bash
make test-cov
```

## 9) Частые проблемы и как исправить

### Ошибка подключения к PostgreSQL

- Проверьте, что сервис PostgreSQL запущен.
- Сверьте логин/пароль/порт в `DATABASE_URL`.
- Попробуйте подключиться вручную: `psql -h localhost -U postgres -d eclipse_game`.

### Миграции не применяются

- Убедитесь, что активировано `venv`.
- Проверьте, что `alembic.ini` в корне проекта.
- Повторите: `alembic upgrade head`.

### Порт 8000 занят

Запустите на другом порту:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## 10) Полезные команды для разработки

```bash
make lint        # проверка ruff
make lint-fix    # автоисправления ruff
make migrate-down
```

---

Если цель — именно проверить игровую функциональность (создание игры, ходы, бой, исследования), начинайте со Swagger (`/docs`) и тестов из `tests/` для соответствующих модулей.
