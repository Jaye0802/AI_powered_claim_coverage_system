# Configuration for BC Claims System

# Database settings
DATABASE_PATH = "bc_real.db"
EXCEL_PATH = "BklSQL.xlsx"
EXCEL_SHEET = "PoliciesNClaims"

# AI settings
DEFAULT_MODEL = "gpt-4o"
AI_TEMPERATURE = 0
AI_SEED = 42

# Processing settings
DEFAULT_TEST_CLAIMS = 3
BATCH_SIZE = 100

# Output settings
RESULTS_FILE_PREFIX = "claims_results"
LOG_LEVEL = "INFO"

# Default coverage limits and deductibles
DEFAULT_COVERAGE_LIMIT = 100000.0
DEFAULT_DEDUCTIBLE = 1000.0

# Coverage mappings for different policy types
POLICY_TYPE_COVERAGES = {
    "auto": ["Collision Damage", "Theft", "Liability"],
    "home": ["Fire Damage", "Water Damage", "Liability"],
    "default": ["General Coverage"]
}

# Field mappings from Excel to database
EXCEL_FIELD_MAPPING = {
    "claim_cols": [
        'claim_id', 'policy_id', 'claim_status', 'claim_type', 
        'loss_cause', 'loss_date', 'claim_description', 'loss_reserve'
    ],
    "policy_cols": [
        'policy_id', 'policy_number', 'policy_type_id', 'policy_type',
        'term_effective_date', 'term_expiration_date'
    ]
}
