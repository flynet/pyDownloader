# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/). Релиз = тег `vX.Y.Z` на `main`.

## [Unreleased]

### Added
- Тёмная тема по умолчанию; для всех тем используется стиль Fusion, поэтому
  кнопки и меню рисуются одинаково на Windows 10/11.
- Точные подписанные URL: реестр запоминает URL каждого манифеста, сегмента и
  ключа из трафика браузера, а загрузчик предпочитает их построенным из
  плейлиста (CDN, подписывающий каждый путь, например phncdn).
- Определение HLS-«семейства»: три сегмента из одного каталога без плейлиста
  образуют карточку; план скачивания строится из записанных URL, init первым.
- YouTube: запрос inner-tube player API из самой страницы (клиент VISIONOS),
  выбор формата до 1080p, видео и звук range-блоками по 8 МБ, мультиплексирование
  FFmpeg без перекодирования.
- Наследование query-параметров манифеста относительными ссылками (подписи и
  токены CDN).

### Fixed
- Cookies страницы и CDN объединяются с перехваченными cookies запроса, а не
  заменяют их.
- Плейлист в каталоге уже найденного потока (второй вариант, аудиодорожка) не
  создаёт вторую карточку: его URL запоминается для загрузчика.

## [0.1.0] - 2026-11-10

### Added
- Парсер HLS: master/media, `EXT-X-MAP`, `EXT-X-BYTERANGE`, `EXT-X-KEY` (AES-128),
  `EXT-X-MEDIA`, разрешение и bandwidth вариантов.
- Парсер DASH: `BaseURL`-цепочки, несколько `Period`, `SegmentTemplate`
  (`$Number$`, `$Time$`, `$RepresentationID$`, `$Bandwidth$`), `SegmentTimeline`,
  `SegmentList`, `SegmentBase`, `ContentProtection`.
- `QualityFilter` (1080p), `DrmDetector` (Widevine/PlayReady/FairPlay/CommonEncryption),
  классификация кандидатов и реестр источников (дедуп по нормализованному URL,
  объединение Range-запросов MP4, пропуск сегментов найденных манифестов).
- Каркас репозитория: `pyproject.toml`, ruff, mypy, pre-commit, `ci.yml`.
- Перехват трафика через Playwright (Chrome → Edge → Chromium), потоковый разбор
  манифестов, фильтр live → DRM → качество → дедуп, скачивание сегментов
  (до 6 потоков), AES-128, склейка FFmpeg, строгая очередь задач.
- GUI на PySide6: карточки найденных источников с прогрессом внутри карточки,
  консоль с причинами пропуска, настройки, тёмная/светлая/системная тема,
  память размера и положения окна.
- Проверка обновлений через GitHub Releases: кэш, диалог с release notes,
  скачивание установщика, проверка SHA-256, запуск `/SILENT /CLOSEAPPLICATIONS`.
- Сборка: `build.ps1` (версия из тега, PyInstaller, FFmpeg в `bin`, SHA-256),
  `pydownloader.spec`, установщик Inno Setup 6 (`installer/pydownloader.iss`),
  `release.yml` с публикацией установщика и release notes из CHANGELOG.

[Unreleased]: https://github.com/flynet/pyDownloader/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/flynet/pyDownloader/releases/tag/v0.1.0
