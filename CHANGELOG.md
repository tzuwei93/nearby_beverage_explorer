# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-08-02

### Changed
- Web ui modifications
    - Renamed "Latest Change" to "Rating Difference" for clarity
    - Updated rating difference calculation to show the difference between highest and lowest ratings in the past 6 months, and the rating history shows the highest, lowest, and latest ratings in the past 6 months
    - Added pagination to the data table (5 rows per page)
    - Improved tooltips to better explain the rating difference calculation
    - Enhanced the footer with GitHub repository link

## [0.1.1]

### Changed
- Resolved issue [#1](https://github.com/william0537/nearby_beverage_explorer/issues/1), which mainly decouple business identity from Google place_id. 

## [0.1.0]

### Added
- Initial project setup
- Basic data pipeline for collecting place information from Google Places API
- Basic web interface using Vue.js
- AWS infrastructure setup (Lambda, S3, Step Functions)
- Initial documentation

[Unreleased]: https://github.com/william0537/nearby_beverage_explorer/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/william0537/nearby_beverage_explorer/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/william0537/nearby_beverage_explorer/compare/v0.1.0...v0.1.1
