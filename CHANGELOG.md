# Changelog

All notable changes to the ClaryAI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite with `test_all.py` for verifying all functionality
- Detailed documentation for asynchronous processing in README.md
- CHANGELOG.md file to track changes

### Fixed
- Fixed asynchronous processing with Redis queue and worker
- Improved error handling in worker.py for file processing
- Fixed database schema creation for API keys and tasks
- Fixed status endpoint to properly retrieve task results from Redis

### Changed
- Updated documentation to reflect the new features and improvements
- Improved code organization and removed unused imports
- Enhanced logging for better debugging and monitoring
- Updated GitHub repository references from 'clary' to 'claryai'

## [0.1.0] - 2023-05-07

### Added
- Initial release of ClaryAI
- Document parsing with Unstructured.io
- Support for multiple file types (PDF, DOCX, JPG, PNG, PPTX, TXT, etc.)
- Structured JSON output for enterprise use cases
- Zero data retention with immediate deletion of temporary files
- Three-way matching for invoices, purchase orders, and goods receipt notes
- Table parsing with custom TableTransformer
- Docker Compose setup for easy deployment
- Redis integration for caching and asynchronous processing
- Support for any LLM model via a generic interface
