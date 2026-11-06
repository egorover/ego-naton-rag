# Pinecone RAG Workflows for n8n

Два n8n workflow и Python-клиенты для загрузки текстовых документов в Pinecone и семантического поиска по ним. n8n обрабатывает запросы через вебхуки, а Pinecone использует встроенную модель для создания embeddings.

> Этот репозиторий не запускает n8n. Предполагается, что у вас уже есть доступный экземпляр n8n и настроенный Pinecone index.

## Содержание

- [Возможности](#возможности)
- [Структура проекта](#структура-проекта)
- [Требования](#требования)
- [Настройка n8n и Pinecone](#настройка-n8n-и-pinecone)
- [Запуск Python-клиентов](#запуск-python-клиентов)
- [Формат API](#формат-api)
- [Демонстрация](#демонстрация)
- [Безопасность](#безопасность)
- [Лицензия](#лицензия)

## Возможности

- Пакетная загрузка `.txt` файлов через webhook n8n.
- Разбиение документов на фрагменты по 600 символов с перекрытием 100 символов.
- Семантический поиск до 5 фрагментов по умолчанию.
- Проверка количества загруженных документов в ответе upload workflow.
- Повторная загрузка тех же файлов обновляет документы с теми же ID.

## Структура проекта

```text
.
|-- data/                       # Демонстрационные текстовые документы
|-- Screenshots/                # Скриншоты workflow и результатов
|-- workflows/
|   |-- workflow1-pinecone-upload.json
|   `-- workflow2-pinecone-search.json
|-- upload_files_to_pinecone.py # Клиент загрузки файлов из data/
|-- test_search_api.py          # Клиент поиска с интерактивным режимом
`-- README.md
```

JSON-файлы в `workflows/` — экспорты холстов n8n:

- `5.05.3 DS - Pinecone Upload Workflow`
- `5.05.4 DS - Pinecone Search Workflow`

Экспортируйте их из n8n после изменений, чтобы обновить локальные копии. Импорт JSON создаёт отдельный workflow; он не обновляет существующий автоматически.

## Требования

- Python 3.9 или новее.
- Доступный экземпляр n8n с активированными workflow.
- Pinecone index с поддержкой Documents API и подходящей схемой документов.
- Credential Pinecone, настроенный в n8n.

## Настройка n8n и Pinecone

1. Импортируйте экспортированные JSON-файлы в n8n либо настройте эквивалентные workflow на холсте.
2. В n8n создайте credential типа **HTTP Header Auth** с именем `Pinecone Header Auth`, заголовком `Api-Key` и вашим Pinecone API key.
3. Привяжите credential к HTTP Request узлам загрузки и поиска.
4. Укажите host своего Pinecone index в URL обоих HTTP Request узлов.
5. Убедитесь, что workflow используют заголовок `X-Pinecone-Api-Version: 2026-07` и активированы.

Текущая конфигурация использует Pinecone Documents API:

- Загрузка: `POST /namespaces/{namespace}/documents/upsert`.
- Поиск: `POST /namespaces/{namespace}/documents/search`.
- Поле текста документа: `chunk_text`, с интегрированной моделью `llama-text-embed-v2` (1024 измерения).
- Дополнительные поля: `title`, `source`, `chunk_index`.

Не добавляйте отдельное поле `embedding`: используемая схема индекса ожидает текст в `chunk_text` и создаёт embedding встроенной моделью Pinecone. Отдельный ProxyAPI key этим workflow не требуется.

## Запуск Python-клиентов

По умолчанию скрипты обращаются к активным локальным вебхукам:

- `http://localhost:5678/webhook/pinecone-upload`
- `http://localhost:5678/webhook/pinecone-search`

### Windows PowerShell

Откройте PowerShell в папке проекта или выполните:

```powershell
Set-Location C:\Dev\n8n\ego-naton-rag
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install requests
```

Загрузка всех `.txt` файлов из `data/`:

```powershell
.\.venv\Scripts\python.exe .\upload_files_to_pinecone.py
```

Поиск:

```powershell
.\.venv\Scripts\python.exe .\test_search_api.py
```

Клиент поиска сначала запускает два встроенных тестовых запроса, затем предлагает вводить собственные запросы. Для выхода введите `exit`.

Переопределение адреса n8n, папки данных или namespace на текущую PowerShell-сессию:

```powershell
$env:N8N_UPLOAD_WEBHOOK_URL = "https://your-n8n.example.com/webhook/pinecone-upload"
$env:N8N_WEBHOOK_URL = "https://your-n8n.example.com/webhook/pinecone-search"
$env:DATA_DIR = "C:\path\to\documents"
$env:PINECONE_NAMESPACE = "default"
```

Задавайте только переменные, которые нужно изменить. После запуска их можно удалить из текущей сессии:

```powershell
Remove-Item Env:N8N_UPLOAD_WEBHOOK_URL, Env:N8N_WEBHOOK_URL, Env:DATA_DIR, Env:PINECONE_NAMESPACE -ErrorAction SilentlyContinue
```

Чтобы видеть прохождение узлов для production webhook, откройте соответствующий workflow в n8n и смотрите его **Executions**. Для тестового URL `/webhook-test/...` сначала запустите **Listen for test event** в узле Webhook; тестовый listener временный.

## Формат API

### Загрузка

`POST /webhook/pinecone-upload`

```json
{
  "files": [
    {
      "fileName": "document.txt",
      "text": "Текст документа"
    }
  ],
  "namespace": "default"
}
```

Загрузчик `upload_files_to_pinecone.py` автоматически читает непустые `.txt` файлы из `data/` в UTF-8. Успешный ответ содержит статус и число загруженных документов:

```json
{
  "status": "success",
  "totalFiles": 1,
  "totalUpserted": 1,
  "fileResults": [
    {"fileIndex": 1, "upserted": 1}
  ]
}
```

### Поиск

`POST /webhook/pinecone-search`

```json
{
  "query": "Как начать работу с продуктом?",
  "namespace": "default"
}
```

Ответ — массив найденных фрагментов с оценкой, источником и индексом чанка:

```json
[
  {
    "text": "Текст найденного фрагмента",
    "score": 0.95,
    "source": "document",
    "chunk_index": 0,
    "id": "chunk_document_0"
  }
]
```

## Демонстрация

Скриншоты запуска и результатов находятся в [Screenshots](Screenshots/):

- [Загрузка в Pinecone](Screenshots/5.05_12_Загрузка_Pinecone.png)
- [Ответ upload workflow](Screenshots/5.05_11_Respond_Output_Upload.png)
- [Запуск upload workflow](Screenshots/5.05_10_Запуск_Upload.png)
- [Ответ search workflow](Screenshots/5.05_14_Respond_Output_Search.png)
- [Запуск search workflow](Screenshots/5.05_13_Запуск_Search.png)
- [Успешная загрузка из PowerShell](Screenshots/5.05_15_PS_Успешная_Загрузка.png)
- [Успешный поиск из PowerShell](Screenshots/5.05_16_PS_Успешный_Поиск.png)

## Безопасность

- Не добавляйте в репозиторий Pinecone API key, n8n credentials, пароли, `.env` и реальные клиентские документы.
- Храните Pinecone API key только в credential n8n. Python-клиентам он не нужен.
- Перед публикацией экспортов n8n проверьте JSON на личные метаданные, URL внутренних сервисов и идентификаторы аккаунтов.
- Проверьте скриншоты на адреса электронной почты, URL и данные, которые не следует публиковать.

## Лицензия

В репозитории пока нет файла лицензии. До добавления лицензии не предполагается разрешение на повторное использование проекта. Добавьте файл `LICENSE`, если хотите явно разрешить использование кода на определённых условиях.