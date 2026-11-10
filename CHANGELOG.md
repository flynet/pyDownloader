# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [SemVer](https://semver.org/lang/ru/). Релиз = тег `vX.Y.Z` на `main`.

## [Unreleased]

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

[Unreleased]: https://github.com/flynet/pyDownloader/compare/v0.0.0...HEAD
