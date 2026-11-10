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

[Unreleased]: https://github.com/flynet/pyDownloader/compare/v0.0.0...HEAD
