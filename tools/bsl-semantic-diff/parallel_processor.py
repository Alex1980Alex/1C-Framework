#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Parallel Processor - параллельная обработка BSL файлов
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Результат обработки файла"""
    file_path: Path
    success: bool
    result: Any = None
    error: str = ""
    processing_time: float = 0.0


@dataclass
class BatchResult:
    """Результат пакетной обработки"""
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    total_time: float = 0.0
    results: List[ProcessingResult] = field(default_factory=list)


class BslParallelProcessor:
    """Параллельный процессор BSL файлов"""

    def __init__(self, max_workers: int = None):
        """
        Args:
            max_workers: Максимальное количество потоков (по умолчанию CPU count)
        """
        self.max_workers = max_workers or min(32, (multiprocessing.cpu_count() or 1) + 4)
        self._stats = {
            'files_processed': 0,
            'total_time': 0.0,
            'errors': 0
        }

    def process_files(
        self,
        files: List[Path],
        processor_func: Callable[[Path], Any],
        use_threads: bool = True,
        chunk_size: int = 10
    ) -> BatchResult:
        """
        Параллельная обработка списка файлов

        Args:
            files: Список файлов для обработки
            processor_func: Функция обработки (принимает Path, возвращает результат)
            use_threads: Использовать потоки (True) или процессы (False)
            chunk_size: Размер чанка для обработки

        Returns:
            BatchResult с результатами обработки
        """
        start_time = time.time()
        batch_result = BatchResult(total_files=len(files))

        if not files:
            return batch_result

        ExecutorClass = ThreadPoolExecutor if use_threads else ProcessPoolExecutor

        with ExecutorClass(max_workers=self.max_workers) as executor:
            # Отправляем задачи на выполнение
            future_to_file = {
                executor.submit(self._process_single, processor_func, f): f
                for f in files
            }

            # Собираем результаты
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    batch_result.results.append(result)
                    if result.success:
                        batch_result.successful += 1
                    else:
                        batch_result.failed += 1
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    batch_result.results.append(ProcessingResult(
                        file_path=file_path,
                        success=False,
                        error=str(e)
                    ))
                    batch_result.failed += 1

        batch_result.total_time = time.time() - start_time
        self._update_stats(batch_result)

        return batch_result

    def _process_single(self, processor_func: Callable, file_path: Path) -> ProcessingResult:
        """Обработка одного файла с замером времени"""
        start = time.time()
        try:
            result = processor_func(file_path)
            return ProcessingResult(
                file_path=file_path,
                success=True,
                result=result,
                processing_time=time.time() - start
            )
        except Exception as e:
            return ProcessingResult(
                file_path=file_path,
                success=False,
                error=str(e),
                processing_time=time.time() - start
            )

    def process_directory(
        self,
        directory: Path,
        processor_func: Callable[[Path], Any],
        pattern: str = "*.bsl",
        recursive: bool = True,
        use_threads: bool = True
    ) -> BatchResult:
        """
        Параллельная обработка всех файлов в директории

        Args:
            directory: Директория для сканирования
            processor_func: Функция обработки
            pattern: Паттерн поиска файлов
            recursive: Рекурсивный поиск
            use_threads: Использовать потоки

        Returns:
            BatchResult с результатами
        """
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))

        logger.info(f"Found {len(files)} files matching '{pattern}' in {directory}")

        return self.process_files(files, processor_func, use_threads)

    def compare_configurations(
        self,
        config1_path: Path,
        config2_path: Path,
        compare_func: Callable[[Path, Path], Any],
        file_pattern: str = "*.bsl"
    ) -> BatchResult:
        """
        Параллельное сравнение двух конфигураций

        Args:
            config1_path: Путь к первой конфигурации
            config2_path: Путь ко второй конфигурации
            compare_func: Функция сравнения (принимает два Path)
            file_pattern: Паттерн поиска файлов

        Returns:
            BatchResult с результатами сравнения
        """
        # Собираем файлы из обеих конфигураций
        files1 = {f.relative_to(config1_path): f for f in config1_path.rglob(file_pattern)}
        files2 = {f.relative_to(config2_path): f for f in config2_path.rglob(file_pattern)}

        all_relative = set(files1.keys()) | set(files2.keys())

        start_time = time.time()
        batch_result = BatchResult(total_files=len(all_relative))

        # Подготавливаем пары для сравнения
        pairs = []
        for rel_path in all_relative:
            f1 = files1.get(rel_path)
            f2 = files2.get(rel_path)
            pairs.append((rel_path, f1, f2))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._compare_pair, compare_func, rel, f1, f2): rel
                for rel, f1, f2 in pairs
            }

            for future in as_completed(futures):
                rel_path = futures[future]
                try:
                    result = future.result()
                    batch_result.results.append(result)
                    if result.success:
                        batch_result.successful += 1
                    else:
                        batch_result.failed += 1
                except Exception as e:
                    logger.error(f"Error comparing {rel_path}: {e}")
                    batch_result.failed += 1

        batch_result.total_time = time.time() - start_time
        return batch_result

    def _compare_pair(
        self,
        compare_func: Callable,
        rel_path: Path,
        file1: Optional[Path],
        file2: Optional[Path]
    ) -> ProcessingResult:
        """Сравнение пары файлов"""
        start = time.time()
        try:
            if file1 is None:
                # Файл добавлен во второй конфигурации
                result = {'status': 'added', 'path': str(file2)}
            elif file2 is None:
                # Файл удалён во второй конфигурации
                result = {'status': 'removed', 'path': str(file1)}
            else:
                # Сравниваем файлы
                result = compare_func(file1, file2)

            return ProcessingResult(
                file_path=file1 or file2,
                success=True,
                result=result,
                processing_time=time.time() - start
            )
        except Exception as e:
            return ProcessingResult(
                file_path=file1 or file2,
                success=False,
                error=str(e),
                processing_time=time.time() - start
            )

    def _update_stats(self, batch_result: BatchResult):
        """Обновление статистики"""
        self._stats['files_processed'] += batch_result.total_files
        self._stats['total_time'] += batch_result.total_time
        self._stats['errors'] += batch_result.failed

    def get_stats(self) -> Dict:
        """Получение статистики обработки"""
        stats = self._stats.copy()
        if stats['total_time'] > 0:
            stats['files_per_second'] = stats['files_processed'] / stats['total_time']
        else:
            stats['files_per_second'] = 0
        return stats

    def reset_stats(self):
        """Сброс статистики"""
        self._stats = {
            'files_processed': 0,
            'total_time': 0.0,
            'errors': 0
        }
