# validation-sigma5

A validation test suite for Sigma5 hardware that runs electrical, application POST, and communication POST tests to verify device functionality.

## Overview

This validation application performs automated testing of Sigma5 devices through the following test suites:

- **Electrical Test**: Validates power rails, voltage levels, and current consumption under various power conditions
- **Application POST Test**: Verifies hardware components including accelerometer, altimeter, GPS, and external flash
- **Communication POST Test**: Tests communication interfaces and related hardware components

Tests are configured via environment variables and can be enabled/disabled independently.

## Installation

### Prerequisites

- Access to the Concord monorepo
- MTIB (Motion Test Interface Board) client access
- Storage client access (for firmware flashing)

### Development Setup

1. **Run the setup command** (creates venv, installs dependencies, and copies .env.example):
    ```bash
    nx run validation-sigma5:setup
    ```

   Or manually:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    cp .env.example .env
    ```

2. **Configure environment variables**:
    Edit `.env` file with appropriate values for:
    - `MTIB_HOST` and `MTIB_PORT` - MTIB client connection
    - `TEST_ENABLE_ELECTRICAL` - Enable/disable electrical tests
    - `TEST_ENABLE_APP_POST` - Enable/disable application POST tests
    - `TEST_ENABLE_COMM_POST` - Enable/disable communication POST tests
    - `LOG_PATH` - Logging directory path

3. **Run the validation tests**:
    ```bash
    source .venv/bin/activate
    python src/main.py
    ```


