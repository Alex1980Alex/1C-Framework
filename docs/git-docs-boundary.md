# Проверка Git и документации

Пакет работает с Python 3.11+ и Git без pipeline-каталога и клиентских хуков оснастки. Установка и доверие к новой копии требуют отдельной приёмки.
В командах `<package>` — абсолютный путь проверенной распаковки, `<target>` — абсолютный путь проверяемого Git-репозитория; пути с пробелами заключайте в кавычки.

Сборка из доверенного дерева: `python -I -B scripts/git_docs_package.py build --source "<source>" --output "<external>/git-docs.zip" --source-base <full-SHA>`.
Исходный каталог и новый выходной ZIP задавайте абсолютными путями; ZIP должен находиться вне исходного дерева. Рядом создаётся `git-docs.zip.manifest.json`.
`source_base` сообщает происхождение, а не одобрение. Получите ожидаемый SHA256 манифеста по независимому доверенному каналу; пересчитанный SHA скачанного рядом манифеста сам по себе доверия не даёт.
До распаковки проверьте архив уже доверенной копией проверяющего кода:
`python -I -B "<trusted-checker>/scripts/git_docs_package.py" verify --archive "<external>/git-docs.zip" --trusted-manifest "<external>/git-docs.zip.manifest.json" --expected-manifest-sha256 <independently-trusted-SHA256>`.
После PASS распакуйте в новый каталог, сохраняя структуру путей. Не перезаписывайте существующую установку. Манифест храните отдельно от пакета.
Проверка ZIP не удостоверяет собственный bootstrap: Python/stdlib, entry scripts, `scripts/git_docs_source_loader.py` и `src/harness/git_docs_delivery.py` должны быть доверенными заранее. Не запускайте непроверенную копию для подтверждения её же доверенности.
Runtime использует точные исходные байты, обходя затеняющие Python-пакеты и `.pyc`; обычный CLI и commit-hook сами по себе не закрепляют внешний манифест. Изменения распакованного дерева требуют повторной проверки.

Индекс: `python -I -B "<package>/scripts/git_docs_verify.py" --root "<target>" --mode index`.
Диапазон: `python -I -B "<package>/scripts/git_docs_verify.py" --root "<target>" --mode range --base <full-SHA> --head <full-SHA>`; код и документ могут быть в разных коммитах.
Результат — JSON v1: rc0 PASS, rc1 FAIL, rc2 UNKNOWN. Авторство `not_assessed`, качество текста требует ревью. Другой индекс задаётся явно: `--index-path "<absolute-path-inside-private-git-dir>"`.

Перед установкой сохраните байты и права активного `pre-commit`, его SHA256 и значение/источник `git config --show-origin --get core.hooksPath`; путь hook определите из целевого репозитория через `git rev-parse --git-path hooks/pre-commit`.
Шаблон `scripts/git_hooks/pre-commit.git-docs.example` рассчитан на расположение `<package>/scripts/git_hooks/pre-commit`. До копирования сравните разрешённые абсолютные пути: установочная копия и активный hook должны быть разными файлами; при совпадении выберите отдельный каталог распаковки. Не добавляйте вызов hook самого себя. Создайте установочную копию, предварительно сохранив существующий файл; Unix: `chmod +x "<package>/scripts/git_hooks/pre-commit"`.
В существующий активный `pre-commit` добавьте вызов этой абсолютной копии последним после обработчиков, меняющих индекс; ненулевой код передайте Git. Существующие обработчики и `core.hooksPath` сохраните.
Если активного hook нет, создайте только этот `pre-commit` с `#!/bin/sh` и строкой `exec "<package>/scripts/git_hooks/pre-commit"`; Unix: `chmod +x "<active-hooks>/pre-commit"`. Шаблон использует `PYTHON`, затем venv пакета, затем `python` из PATH.
Hook проверяет delta индекса относительно текущего HEAD; amend не доказывает корректность всего переписанного коммита. Включение hook в одном репозитории не подключает его в других.
CI запускает доверенный checker из base checkout; PR-код не исполняется. Remote run и доверие к bootstrap принимаются отдельно.

Возврат: восстановите сохранённые байты и права изменённого hook. Если hook или установочная копия созданы заново, удалите только записанный при установке собственный файл после сверки его SHA256; при расхождении сохраните его для ручного разбора. Остальные hooks и `core.hooksPath` оставьте на месте; пакет удаляйте только из отдельного нового каталога после отключения всех его потребителей.
Справки только исходного репозитория (в ZIP не входят): `docs/roadmap/261114_ROADMAP_CODEX_GIT_DOCS_STABLE_BOUNDARY.md`, `pipeline/git-docs-p3-261115/02-design.md`.
