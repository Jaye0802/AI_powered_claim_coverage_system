# BriteCore Claims Coverage Assessment System

A streamlined AI-powered claims assessment system that processes insurance claims efficiently and flexibly with comprehensive monitoring and validation.

## Features

- **Smart Data Import**: Only imports Excel data when needed (file has changed)
- **Flexible Processing**: Process single claims, multiple claims, or all claims
- **AI Agent Analysis**: Objective claim assessment without pre-determined outcomes
- **Clean Architecture**: Well-commented, maintainable code
- **Robust Error Handling**: Graceful fallbacks when AI analysis fails
- **Performance Optimized**: Database indexes and efficient data processing
- **Data Validation**: Comprehensive data quality checking
- **Performance Monitoring**: Real-time performance tracking and optimization

## Quick Start

1. **Manual Setup**:
```bash
pip install -r requirements.txt
```

2. **Add your OpenAI API key to `.env`**:
```
OPENAI_API_KEY=your_api_key_here
```

3. **Run the system**:
```bash
python claims_system_clean.py
```

## System Architecture

### Core Files
- **`claims_system_clean.py`** - Main system with AI agent and database handling
- **`config.py`** - Configuration settings and defaults
- **`requirements.txt`** - Python package dependencies

### Utility Files
- **`data_validator.py`** - Data quality validation and integrity checks
- **`performance_monitor.py`** - Performance monitoring and benchmarking
- **`test_claims_system.py`** - Comprehensive test suite with mock AI mode


## Usage Examples

### Basic Usage
```python
from claims_system_clean import ClaimsCoverageSystem

# Initialize system
system = ClaimsCoverageSystem()
system.ensure_data_loadedx()

# Process single claim
result = system.process_claims("claim_id")

# Process multiple claims
results = system.process_claims(["id1", "id2", "id3"])

# Process first N claims (testing)
results = system.process_claims(5)

# Process all claims (production)
results = system.process_claims()
```

### Data Validation

The system includes a validation module (`data_validator.py`) to:
- check schema consistency
- validate date ranges and data types
- detect missing or inconsistent fields

```bash
python data_validator.py
```


### Performance Monitoring
```bash
python performance_monitor.py
```

### Run Tests
```bash
python test_claims_system.py
```

## Configuration

All settings are centralized in `config.py`:

```python
# Database settings
# Place this input file `BklSQL.xlsx` in the project root directory before running the system
DATABASE_PATH = "bt_real.db"
EXCEL_PATH = "BklSQL.xlsx" 

# AI settings
DEFAULT_MODEL = "gpt-4o"
AI_TEMPERATURE = 0

# Processing settings
DEFAULT_TEST_CLAIMS = 3
BATCH_SIZE = 100
```


