# Contributing to the Project

## Welcome Contributors! 🎉

We're thrilled that you're interested in contributing to our project. This document provides guidelines to help you get started.

## Code of Conduct

Please be respectful, inclusive, and considerate of others. We aim to maintain a welcoming environment for everyone.

## How to Contribute

### Reporting Issues

1. Check existing issues to avoid duplicates
2. Use the issue template provided
3. Provide clear, detailed information about the problem

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Write or update tests as needed
5. Ensure all tests pass
6. Submit a pull request with a clear description of your changes

### Development Setup

1. Clone the repository
2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```
3. Install development dependencies
   ```bash
   pip install -e .[dev]
   ```
4. Run tests
   ```bash
   pytest
   ```

## Coding Standards

- Follow PEP 8 style guidelines
- Write clear, concise, and documented code
- Add type hints
- Include docstrings for all functions and classes
- Write unit tests for new functionality

## Release Process

- We use semantic versioning
- Changelog updates are required for significant changes
- All releases are published to PyPI

## Questions?

If you have questions, please open an issue or reach out to the maintainers.

Thank you for contributing! 🚀
