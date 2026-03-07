"""
Скрипт извлечения BSL функций для fine-tuning и RAG
Извлекает функции и процедуры из BSL файлов с комментариями
"""
import re
import json
import hashlib
from pathlib import Path
from typing import Generator
from tqdm import tqdm


def extract_functions(content: str) -> Generator[dict, None, None]:
    """Извлечение функций и процедур из BSL кода"""

    # Паттерн для поиска функций и процедур (русские и английские)
    pattern = r'''
        (?P<comment>(?://[^\n]*\n|/\*[\s\S]*?\*/\s*)*)?\s*  # Комментарии перед
        (?P<type>Функция|Процедура|Function|Procedure)\s+
        (?P<name>\w+)\s*
        \((?P<params>[^)]*)\)\s*
        (?P<export>Экспорт|Export)?\s*
        (?P<body>[\s\S]*?)
        (?P<end>КонецФункции|КонецПроцедуры|EndFunction|EndProcedure)
    '''

    for match in re.finditer(pattern, content, re.VERBOSE | re.IGNORECASE):
        func_type = match.group('type')
        name = match.group('name')
        params = match.group('params').strip()
        export = match.group('export') is not None
        body = match.group('body').strip()
        comment = match.group('comment') or ''
        end_keyword = match.group('end')

        # Полный код функции
        full_code = f"{func_type} {name}({params})"
        if export:
            full_code += " Экспорт" if 'Функция' in func_type or 'Процедура' in func_type else " Export"
        full_code += f"\n{body}\n{end_keyword}"

        yield {
            'type': func_type,
            'name': name,
            'params': params,
            'export': export,
            'comment': comment.strip(),
            'body': body,
            'code': full_code,
            'has_comment': bool(comment.strip())
        }


def create_training_example(func: dict, file_path: str = '') -> dict:
    """Создание примера для обучения в формате Alpaca"""

    func_type = 'функцию' if 'Функция' in func['type'] or 'Function' in func['type'] else 'процедуру'

    if func['comment']:
        instruction = f"Напиши {func_type} {func['name']} на языке 1С (BSL). {func['comment']}"
    else:
        instruction = f"Напиши {func_type} {func['name']}({func['params']}) на языке 1С (BSL)."

    return {
        'instruction': instruction,
        'input': '',
        'output': func['code'],
        'metadata': {
            'name': func['name'],
            'type': func['type'],
            'export': func['export'],
            'has_comment': func['has_comment'],
            'file': file_path
        }
    }


def create_rag_chunk(func: dict, file_path: str) -> dict:
    """Создание чанка для RAG индексации"""
    return {
        'content': func['code'],
        'metadata': {
            'name': func['name'],
            'type': func['type'],
            'export': func['export'],
            'params': func['params'],
            'file': file_path,
            'has_comment': func['has_comment']
        }
    }


def process_folder(folder_path: str, output_prefix: str, max_examples: int = None):
    """Обработка папки с BSL файлами"""
    folder = Path(folder_path)
    bsl_files = list(folder.rglob("*.bsl"))

    print(f"Найдено {len(bsl_files)} BSL файлов")

    training_examples = []
    rag_chunks = []
    seen_hashes = set()

    stats = {
        'files_processed': 0,
        'functions_found': 0,
        'with_comments': 0,
        'exported': 0,
        'duplicates_skipped': 0
    }

    for bsl_file in tqdm(bsl_files, desc="Обработка файлов"):
        try:
            # Пробуем разные кодировки
            content = None
            for encoding in ['utf-8-sig', 'utf-8', 'cp1251', 'cp866']:
                try:
                    content = bsl_file.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                continue

            relative_path = str(bsl_file.relative_to(folder))

            for func in extract_functions(content):
                # Дедупликация по хешу кода
                code_hash = hashlib.md5(func['code'].encode()).hexdigest()
                if code_hash in seen_hashes:
                    stats['duplicates_skipped'] += 1
                    continue
                seen_hashes.add(code_hash)

                stats['functions_found'] += 1
                if func['has_comment']:
                    stats['with_comments'] += 1
                if func['export']:
                    stats['exported'] += 1

                # Создаём примеры
                training_examples.append(create_training_example(func, relative_path))
                rag_chunks.append(create_rag_chunk(func, relative_path))

                if max_examples and len(training_examples) >= max_examples:
                    break

            stats['files_processed'] += 1

            if max_examples and len(training_examples) >= max_examples:
                break

        except Exception as e:
            print(f"Ошибка обработки {bsl_file}: {e}")

    # Сохраняем результаты
    training_file = f"{output_prefix}_training.json"
    rag_file = f"{output_prefix}_rag.json"

    with open(training_file, 'w', encoding='utf-8') as f:
        json.dump(training_examples, f, ensure_ascii=False, indent=2)

    with open(rag_file, 'w', encoding='utf-8') as f:
        json.dump(rag_chunks, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Статистика:")
    print(f"  Обработано файлов: {stats['files_processed']}")
    print(f"  Найдено функций/процедур: {stats['functions_found']}")
    print(f"  С комментариями: {stats['with_comments']} ({100*stats['with_comments']/max(1,stats['functions_found']):.1f}%)")
    print(f"  Экспортных: {stats['exported']}")
    print(f"  Пропущено дубликатов: {stats['duplicates_skipped']}")
    print(f"\nСохранено:")
    print(f"  Training: {training_file} ({len(training_examples)} примеров)")
    print(f"  RAG: {rag_file} ({len(rag_chunks)} чанков)")

    return stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Использование: python extract_dataset.py <папка_с_bsl> <output_prefix> [max_examples]")
        print("Пример: python extract_dataset.py D:\\1C-Enterprise_Framework\\src D:\\1C-Enterprise_Framework\\data\\datasets\\bsl 10000")
        sys.exit(1)

    folder = sys.argv[1]
    output = sys.argv[2]
    max_ex = int(sys.argv[3]) if len(sys.argv) > 3 else None

    process_folder(folder, output, max_ex)
