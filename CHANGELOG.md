# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-10-03

### Added
- MSAL device code authentication support for XMLA connections
- Comprehensive XMLA authentication solution documentation
- .NET Framework compatibility fixes for pythonnet on Windows
- Early PATH initialization for ADOMD.NET assemblies
- Power BI public client ID support (Power Query for Excel)
- Token scope validation and inspection utilities
- Cleaner test output with reduced warning noise

### Changed
- ADOMD.NET assembly loading now prefers net472/net48 over net8.0 for Windows compatibility
- Connection test script suppresses verbose warnings by default
- Assembly resolvers simplified to reduce debug output
- Token acquisition workflow prioritizes MSAL over Azure CLI for proper scopes

### Fixed
- **CRITICAL**: XMLA authentication now works with MSAL device code flow
- pythonnet import errors with .NET Core assemblies (`System.MarshalByRefObject` not found)
- Assembly loading order issues causing "No module named 'Microsoft.AnalysisServices'"
- Azure CLI token scope limitations (missing Dataset.Read.All permissions)
- Connection string format compatibility with ADOMD.NET on Windows

### Documentation
- Added `docs/XMLA_AUTH_SOLUTION.md` - comprehensive authentication solution guide
- Updated `docs/XMLA_AUTH_NOTES.md` - workspace-specific configuration notes
- Documented .NET Framework vs .NET Core compatibility issues
- Explained why DAX Studio works but Azure CLI fails
- Added troubleshooting section for common pythonnet/ADOMD issues

### Technical Details
- Root cause: Azure CLI tokens only contain `user_impersonation` scope, not `Dataset.Read.All`
- Solution: Use MSAL PublicClientApplication with Power BI public client ID (a672d62c-fc7b-4e81-a576-e60dc46e951d)
- Requires tenant admin approval for delegated Dataset.Read.All permission
- ADOMD net8.0 assemblies incompatible with pythonnet's .NET Framework runtime
- Must add ADOMD directory to PATH before importing clr/pythonnet

## [1.0.0] - 2025-01-18

### Added
- Integration tests for real Power BI connectivity
- Environment-based integration test configuration
- Interactive test runner with safety checks
- GitHub Actions CI/CD workflow for automated testing
- Comprehensive integration test documentation
- Test markers for unit vs integration test separation
- Makefile for simplified development workflow
- Enhanced error handling and validation in tests

### Changed
- Updated .env.example with integration test configuration
- Improved test structure with proper pytest markers
- Enhanced documentation with integration testing guide

### Security
- Secure handling of test credentials via environment variables
- Clear separation of test and production configurations

## [1.0.0] - 2024-06-21

### Added
- Initial release of Power BI MCP Server
- Natural language to DAX query generation
- Service Principal authentication
- Async performance optimizations
- Comprehensive error handling
- Support for GPT-4o-mini model
- Table and schema discovery
- Custom DAX execution
- Intelligent question suggestions

### Security
- Secure credential handling via environment variables
- No hardcoded secrets in codebase
