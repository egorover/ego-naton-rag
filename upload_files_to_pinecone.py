import os
import requests
import json
import sys
from pathlib import Path
from typing import List, Dict

DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/pinecone-upload"


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read_txt_files_from_directory(directory: str = "./data") -> List[Dict]:
    """
    Читает все .txt файлы из указанной директории.
    
    Args:
        directory: Путь к директории с .txt файлами
    
    Returns:
        Список словарей с данными файлов
    """
    files_data = []
    data_directory = Path(directory)

    if not data_directory.is_dir():
        raise FileNotFoundError(f"Directory {directory} does not exist")

    txt_files = sorted(
        (path for path in data_directory.iterdir() if path.is_file() and path.suffix.lower() == ".txt"),
        key=lambda path: path.name.casefold(),
    )

    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {directory}")

    for filepath in txt_files:
        content = filepath.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError(f"File {filepath.name} is empty")
        files_data.append({
            "fileName": filepath.name,
            "text": content
        })
        print(f"✓ Прочитан файл: {filepath.name} ({len(content)} символов)")

    return files_data


def upload_to_pinecone(files_data: List[Dict], webhook_url: str, namespace: str = "default") -> Dict:
    """
    Загружает файлы в Pinecone через n8n webhook.
    
    Args:
        files_data: Список словарей с данными файлов
        webhook_url: URL webhook из n8n
        namespace: Namespace в Pinecone
    
    Returns:
        Ответ от API
    """
    payload = {
        "files": files_data,
        "namespace": namespace
    }
    
    print(f"\n📤 Отправка {len(files_data)} файлов в Pinecone...")
    print(f"   Webhook URL: {webhook_url}")
    print(f"   Namespace: {namespace}")
    
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=300
        )
        if not response.ok:
            print(f"\n❌ n8n вернул HTTP {response.status_code}")
            print("Тело ответа:")
            print(response.text)
        response.raise_for_status()
        
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            body_preview = response.text[:2000] or "<empty response body>"
            content_type = response.headers.get("Content-Type", "<not set>")
            raise RuntimeError(
                "n8n вернул ответ, который не удалось разобрать как JSON. "
                f"HTTP {response.status_code}; Content-Type: {content_type}; "
                f"тело ответа: {body_preview}"
            ) from e

        if not isinstance(result, dict):
            raise RuntimeError(
                f"Ожидался JSON-объект от n8n, получено: {type(result).__name__}"
            )

        total_files = result.get("totalFiles")
        total_upserted = result.get("totalUpserted")
        file_results = result.get("fileResults")
        if result.get("status") != "success":
            raise RuntimeError(f"n8n не подтвердил успешную загрузку: {json.dumps(result, ensure_ascii=False)}")
        if total_files != len(files_data):
            raise RuntimeError(
                f"n8n обработал {total_files!r} файлов, ожидалось {len(files_data)}"
            )
        if not isinstance(total_upserted, int) or total_upserted <= 0:
            raise RuntimeError(f"n8n не подтвердил количество загруженных документов: {result}")
        if not isinstance(file_results, list) or len(file_results) != len(files_data):
            raise RuntimeError(f"n8n вернул неполную статистику по файлам: {result}")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("upserted"), int)
            or item["upserted"] <= 0
            for item in file_results
        ):
            raise RuntimeError(f"Не все файлы дали загруженные документы: {result}")
        if sum(item["upserted"] for item in file_results) != total_upserted:
            raise RuntimeError(f"Общий счётчик не совпадает с результатами файлов: {result}")

        print(f"\n✅ Успешно загружено!")
        print(f"   Обработано файлов: {total_files}")
        print(f"   Документов загружено: {total_upserted}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Ошибка при запросе к API: {e}") from e


def main():
    """
    Основная функция для загрузки файлов из /data в Pinecone.
    """
    configure_console_encoding()
    # Настройки
    DATA_DIR = os.getenv("DATA_DIR", "./data")
    WEBHOOK_URL = os.getenv("N8N_UPLOAD_WEBHOOK_URL", DEFAULT_WEBHOOK_URL)
    NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")
    
    print("=" * 80)
    print("📁 Загрузка файлов из директории в Pinecone")
    print("=" * 80)
    print(f"Директория: {DATA_DIR}")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Namespace: {NAMESPACE}")
    print("=" * 80)
    
    try:
        # Читаем файлы
        files_data = read_txt_files_from_directory(DATA_DIR)
        
        if not files_data:
            print("❌ Нет файлов для загрузки")
            return
        
        # Загружаем в Pinecone
        result = upload_to_pinecone(files_data, WEBHOOK_URL, NAMESPACE)
        
        # Выводим детальную статистику
        if result.get('fileResults'):
            print("\n📊 Детальная статистика по файлам:")
            for file_result in result['fileResults']:
                print(f"   Файл #{file_result['fileIndex']}: {file_result['upserted']} векторов")
        
        print("\n✅ Все файлы успешно обработаны!")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
