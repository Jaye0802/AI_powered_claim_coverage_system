"""
Streamlined AI Claims System
Clean implementation with flexible processing options and proper database handling

policy_id	policy_number	policy_active_flag	policy_status	policy_status_reason	policy_type_id	policy_type	line_of_business	term_effective_date	term_expiration_date	written_premium	written_fees	annual_premium	annual_fees	commission_rate	policy_system_tags	revision_id	revision_state	revision_date	commit_date	create_date	claim_id	claim_number	claim_active_flag	claim_status	claim_type	loss_cause	loss_date	date_reported	date_added	last_modified	claim_description	loss_location_address	loss_location_address_city	loss_location_address_state	loss_location_address_zip	claim_system_tags	cat_code	cat_location	claim_item_id	claim_item_name	coverage_deductible	loss_reserve	adjusting_reserve	legal_reserve	subrogation_reserve	salvage_reserve	reinsurance_reserve	claim_item_description




"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from contextlib import contextmanager
import sqlite3
import pandas as pd

from openai import OpenAI
from pydantic import BaseModel, Field

# Import configuration
try:
    from config import (
        DATABASE_PATH, EXCEL_PATH, EXCEL_SHEET, DEFAULT_MODEL,
        AI_TEMPERATURE, AI_SEED, DEFAULT_TEST_CLAIMS, 
        DEFAULT_COVERAGE_LIMIT, DEFAULT_DEDUCTIBLE, POLICY_TYPE_COVERAGES,
        EXCEL_FIELD_MAPPING
    )
except ImportError:
    # Fallback defaults if config file is missing
    DATABASE_PATH = "bc_real.db"
    EXCEL_PATH = "BklSQL.xlsx"
    EXCEL_SHEET = "PoliciesNClaims"
    DEFAULT_MODEL = "gpt-4o"
    AI_TEMPERATURE = 0
    AI_SEED = 42
    DEFAULT_TEST_CLAIMS = 3
    DEFAULT_COVERAGE_LIMIT = 100000.0
    DEFAULT_DEDUCTIBLE = 1000.0
    POLICY_TYPE_COVERAGES = {
        "auto": ["Collision Damage", "Theft", "Liability"],
        "home": ["Fire Damage", "Water Damage", "Liability"],
        "default": ["General Coverage"]
    }
    EXCEL_FIELD_MAPPING = {
        "claim_cols": ['claim_id', 'policy_id', 'claim_status', 'claim_type', 
                      'loss_cause', 'loss_date', 'claim_description', 'loss_reserve'],
        "policy_cols": ['policy_id', 'policy_number', 'policy_type_id', 'policy_type',
                       'term_effective_date', 'term_expiration_date']
    }

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============= Core Data Models =============
@dataclass
class Policy:
    """Policy data model"""
    policy_id: str
    policy_term_id: str
    policy_type_id: str
    primary_insured_id: str
    effective_date: date
    expiration_date: date
    carrier: str
    agency_id: str
    policy_number: str

@dataclass
class Coverage:
    """Coverage data model"""
    coverage_id: str
    item_id: str
    policy_term_id: str
    coverage_type: str
    item_type: str
    limit: float
    deductible: float
    exclusion_text: str
    conditions: str

@dataclass
class Claim:
    """Claim data model without pre-determined outcomes"""
    claim_id: str
    policy_id: str
    date_of_loss: date
    claim_amount: float
    claim_status: str
    description: str
    peril_type: str
    claim_category: str

class CoverageAnalysis(BaseModel):
    """AI analysis of coverage matching"""
    is_time_valid: bool
    matching_coverage_types: List[str]
    exclusion_triggered: bool
    exclusion_details: str
    conditions_met: bool
    condition_details: str
    confidence_score: float = Field(ge=0.0, le=1.0)

class ClaimAssessment(BaseModel):
    """Final claim assessment with AI reasoning"""
    claim_id: str
    is_covered: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    applicable_coverages: List[str] = []
    estimated_payout: Optional[float] = Field(default=None, ge=0.0)
    step_by_step_analysis: Dict[str, Any]

# ============= Database Adapter =============
class BCDataAdapter:
    """Database adapter with smart Excel import handling"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        self.excel_path = EXCEL_PATH
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with proper error handling"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database with optimized schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Core tables with proper constraints
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    policy_term_id TEXT NOT NULL,
                    policy_type_id TEXT NOT NULL,
                    primary_insured_id TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    expiration_date TEXT NOT NULL,
                    carrier TEXT NOT NULL,
                    agency_id TEXT NOT NULL,
                    policy_number TEXT UNIQUE NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coverages (
                    coverage_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    policy_term_id TEXT NOT NULL,
                    coverage_type TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    "limit" REAL NOT NULL,
                    deductible REAL NOT NULL,
                    exclusion_text TEXT,
                    conditions TEXT,
                    FOREIGN KEY (policy_term_id) REFERENCES policies(policy_term_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    date_of_loss TEXT NOT NULL,
                    claim_amount REAL NOT NULL,
                    claim_status TEXT NOT NULL,
                    description TEXT,
                    peril_type TEXT,
                    claim_category TEXT,
                    approved_amount REAL,
                    denial_reason TEXT,
                    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
                )
            ''')
            
            # Track data imports to avoid duplicates
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS import_log (
                    import_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT NOT NULL,
                    file_modified_time TEXT NOT NULL,
                    import_timestamp TEXT NOT NULL,
                    records_imported INTEGER NOT NULL
                )
            ''')
            
            # Performance indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_policy_term ON coverages(policy_term_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_policy_id ON claims(policy_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_claim_status ON claims(claim_status)')
            
            conn.commit()
    
    def needs_data_import(self) -> bool:
        """Check if Excel data needs to be imported/updated"""
        if not os.path.exists(self.excel_path):
            logger.warning(f"Excel file {self.excel_path} not found")
            return False
            
        # Get file modification time
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(self.excel_path)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM import_log 
                WHERE source_file = ? AND file_modified_time = ?
            ''', (self.excel_path, file_mod_time))
            
            result = cursor.fetchone()
            # If no record exists for this file version, we need to import
            return result['count'] == 0
    
    def import_berkeley_data_if_needed(self) -> Dict[str, Any]:
        """Smart import: only imports if needed"""
        if not self.needs_data_import():
            logger.info("Data is up to date, skipping import")
            return {"success": True, "message": "Data already up to date", "imported": False}
        
        return self.import_berkeley_data()
    
    def import_berkeley_data(self) -> Dict[str, Any]:
        """Import data from BklSQL.xlsx file"""
        try:
            logger.info(f"Reading Excel file: {self.excel_path}")
            df = pd.read_excel(self.excel_path, sheet_name=EXCEL_SHEET)
            logger.info(f"Loaded {len(df)} rows from Excel")
            
            # Process and import the data
            stats = self._process_berkeley_data(df)
            
            # Log the import
            self._log_import(df)
            
            return {
                "success": True,
                "stats": stats,
                "message": f"Successfully imported data from {self.excel_path}",
                "imported": True
            }
            
        except FileNotFoundError:
            error_msg = f"File not found: {self.excel_path}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "imported": False}
        except Exception as e:
            error_msg = f"Error importing data: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "imported": False}
    
    def _log_import(self, df: pd.DataFrame):
        """Log the import for tracking"""
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(self.excel_path)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO import_log (source_file, file_modified_time, import_timestamp, records_imported)
                VALUES (?, ?, ?, ?)
            ''', (self.excel_path, file_mod_time, datetime.now().isoformat(), len(df)))
            conn.commit()
    
    def _process_berkeley_data(self, df: pd.DataFrame) -> Dict[str, int]:
        """Process and import Berkeley data, only adding new records"""
        stats = {"policies": 0, "claims": 0, "coverages": 0, "skipped": 0}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get existing IDs to avoid duplicates
            cursor.execute("SELECT policy_id FROM policies")
            existing_policies = {row[0] for row in cursor.fetchall()}
            
            cursor.execute("SELECT claim_id FROM claims")
            existing_claims = {row[0] for row in cursor.fetchall()}
            
            cursor.execute("SELECT coverage_id FROM coverages")
            existing_coverages = {row[0] for row in cursor.fetchall()}
            
            # Process policies
            policy_cols = EXCEL_FIELD_MAPPING["policy_cols"]
            policies_df = df[policy_cols].drop_duplicates(subset=['policy_id'])
            
            for _, row in policies_df.iterrows():
                if row['policy_id'] in existing_policies:
                    stats["skipped"] += 1
                    continue
                    
                try:
                    effective_date = pd.to_datetime(row['term_effective_date'])
                    expiration_date = pd.to_datetime(row['term_expiration_date'])
                    
                    policy_data = (
                        row['policy_id'],
                        f"TERM-{row['policy_id']}",
                        row['policy_type_id'],
                        f"INS-{row['policy_id']}",
                        effective_date.strftime('%Y-%m-%d'),
                        expiration_date.strftime('%Y-%m-%d'),
                        'Berkeley Insurance',
                        'AGY-001',
                        row['policy_number']
                    )
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', policy_data)
                    
                    if cursor.rowcount > 0:
                        stats["policies"] += 1
                        
                except Exception as e:
                    logger.warning(f"Error processing policy {row['policy_id']}: {e}")
                    continue
            
            # Process claims
            claim_cols = EXCEL_FIELD_MAPPING["claim_cols"]
            claims_df = df[df['claim_id'].notna()][claim_cols].drop_duplicates(subset=['claim_id'])
            
            for _, row in claims_df.iterrows():
                if row['claim_id'] in existing_claims:
                    stats["skipped"] += 1
                    continue
                    
                try:
                    # Handle dates
                    loss_date = row['loss_date']
                    if pd.notna(loss_date):
                        if isinstance(loss_date, (int, float)):
                            loss_date = pd.to_datetime('1900-01-01') + pd.Timedelta(days=loss_date-2)
                        else:
                            loss_date = pd.to_datetime(loss_date)
                        loss_date_str = loss_date.strftime('%Y-%m-%d')
                    else:
                        loss_date_str = date.today().strftime('%Y-%m-%d')
                    
                    # Handle claim amount
                    claim_amount = 0.0
                    if pd.notna(row['loss_reserve']):
                        claim_amount = float(row['loss_reserve'])
                    
                    if claim_amount == 0.0 and pd.notna(row['claim_type']):
                        claim_type = str(row['claim_type']).lower()
                        if 'liability' in claim_type:
                            claim_amount = 15000.0
                        elif 'collision' in claim_type or 'damage' in claim_type:
                            claim_amount = 8000.0
                        elif 'theft' in claim_type:
                            claim_amount = 12000.0
                        else:
                            claim_amount = 5000.0
                    
                    claim_data = (
                        row['claim_id'],
                        row['policy_id'],
                        loss_date_str,
                        claim_amount,
                        'pending',
                        row['claim_description'] if pd.notna(row['claim_description']) else '',
                        row['loss_cause'] if pd.notna(row['loss_cause']) else 'Unknown',
                        row['claim_type'] if pd.notna(row['claim_type']) else 'General',
                        None,
                        None
                    )
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', claim_data)
                    
                    if cursor.rowcount > 0:
                        stats["claims"] += 1
                        
                except Exception as e:
                    logger.warning(f"Error processing claim {row['claim_id']}: {e}")
                    continue
            
            # Generate coverages only for new policies
            for _, policy_row in policies_df.iterrows():
                if policy_row['policy_id'] not in existing_policies:
                    try:
                        policy_claims = df[df['policy_id'] == policy_row['policy_id']]
                        coverage_types = set()
                        
                        for _, claim_row in policy_claims.iterrows():
                            if pd.notna(claim_row['claim_type']):
                                coverage_types.add(claim_row['claim_type'])
                            if pd.notna(claim_row['loss_cause']):
                                coverage_types.add(claim_row['loss_cause'])
                        
                        if not coverage_types:
                            policy_type = str(policy_row.get('policy_type', '')).lower()
                            if 'auto' in policy_type:
                                coverage_types = set(POLICY_TYPE_COVERAGES['auto'])
                            elif 'home' in policy_type:
                                coverage_types = set(POLICY_TYPE_COVERAGES['home'])
                            else:
                                coverage_types = set(POLICY_TYPE_COVERAGES['default'])
                        
                        for coverage_type in coverage_types:
                            coverage_id = f"COV-{policy_row['policy_id']}-{coverage_type.replace(' ', '_')}"
                            
                            if coverage_id in existing_coverages:
                                continue
                            
                            deductible = DEFAULT_DEDUCTIBLE
                            relevant_claims = policy_claims[policy_claims['claim_type'] == coverage_type]
                            if not relevant_claims.empty:
                                deductible_val = relevant_claims['coverage_deductible'].iloc[0]
                                if pd.notna(deductible_val):
                                    deductible = float(deductible_val)
                            
                            coverage_data = (
                                coverage_id,
                                f"ITEM-{policy_row['policy_id']}",
                                f"TERM-{policy_row['policy_id']}",
                                coverage_type,
                                'Vehicle' if 'auto' in str(policy_row.get('policy_type', '')).lower() else 'Dwelling',
                                DEFAULT_COVERAGE_LIMIT,
                                deductible,
                                'Standard exclusions apply',
                                'Standard conditions apply'
                            )
                            
                            cursor.execute('''
                                INSERT OR IGNORE INTO coverages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', coverage_data)
                            
                            if cursor.rowcount > 0:
                                stats["coverages"] += 1
                                
                    except Exception as e:
                        logger.warning(f"Error processing coverages for policy {policy_row['policy_id']}: {e}")
                        continue
            
            conn.commit()
        
        logger.info(f"Added: {stats['policies']} policies, {stats['claims']} claims, {stats['coverages']} coverages")
        logger.info(f"Skipped {stats['skipped']} existing records")
        return stats
    
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Retrieve policy by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM policies WHERE policy_id = ?", (policy_id,))
            row = cursor.fetchone()
            
            if row:
                return Policy(
                    policy_id=row['policy_id'],
                    policy_term_id=row['policy_term_id'],
                    policy_type_id=row['policy_type_id'],
                    primary_insured_id=row['primary_insured_id'],
                    effective_date=datetime.strptime(row['effective_date'], '%Y-%m-%d').date(),
                    expiration_date=datetime.strptime(row['expiration_date'], '%Y-%m-%d').date(),
                    carrier=row['carrier'],
                    agency_id=row['agency_id'],
                    policy_number=row['policy_number']
                )
        return None
    
    def get_coverages_by_policy(self, policy_term_id: str) -> List[Coverage]:
        """Retrieve all coverages for a policy term"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM coverages WHERE policy_term_id = ?", (policy_term_id,))
            rows = cursor.fetchall()
            
            coverages = []
            for row in rows:
                coverages.append(Coverage(
                    coverage_id=row['coverage_id'],
                    item_id=row['item_id'],
                    policy_term_id=row['policy_term_id'],
                    coverage_type=row['coverage_type'],
                    item_type=row['item_type'],
                    limit=row['limit'],
                    deductible=row['deductible'],
                    exclusion_text=row['exclusion_text'] or "",
                    conditions=row['conditions'] or ""
                ))
            return coverages
    
    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Retrieve claim by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
            row = cursor.fetchone()
            
            if row:
                return Claim(
                    claim_id=row['claim_id'],
                    policy_id=row['policy_id'],
                    date_of_loss=datetime.strptime(row['date_of_loss'], '%Y-%m-%d').date(),
                    claim_amount=row['claim_amount'],
                    claim_status=row['claim_status'],
                    description=row['description'],
                    peril_type=row['peril_type'],
                    claim_category=row['claim_category']
                )
        return None
    
    def get_claims(self, limit: Optional[int] = None) -> List[str]:
        """Get claim IDs with optional limit for testing"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT claim_id FROM claims ORDER BY claim_id"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query)
            return [row['claim_id'] for row in cursor.fetchall()]

# ============= AI Agent Helper Functions =============
def add_additional_properties_false(schema):
    """Ensure schema doesn't allow additional properties for strict JSON"""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
        for key, value in schema.items():
            if isinstance(value, dict):
                add_additional_properties_false(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        add_additional_properties_false(item)
    return schema

def chat_completion_with_structured_json(client, *, model, messages, schema_dict, temperature=None, seed=None):
    """Call OpenAI with structured JSON output"""
    schema_dict = add_additional_properties_false(schema_dict.copy())
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "response_schema",
                    "strict": True,
                    "schema": schema_dict
                }
            },
            temperature=temperature if temperature is not None else AI_TEMPERATURE,
            seed=seed if seed is not None else AI_SEED,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.warning(f"Structured output failed: {e}")
        return {}

# ============= AI Claims Agent =============
class ClaimsCoverageAgent:
    """AI agent for claims assessment without bias"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = None):
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=api_key)
        self.model = model or DEFAULT_MODEL

    def analyze_coverage_match(self, claim: Claim, policy: Policy, coverages: List[Coverage]) -> CoverageAnalysis:
        """Analyze if claim matches available coverages"""
        coverage_info = []
        for cov in coverages:
            coverage_info.append({
                "coverage_type": cov.coverage_type,
                "limit": cov.limit,
                "deductible": cov.deductible,
                "exclusions": cov.exclusion_text,
                "conditions": cov.conditions
            })
        
        prompt = f"""
        You are an expert insurance claims analyst. Analyze this claim against policy coverages objectively.

        CLAIM DETAILS:
        - Claim ID: {claim.claim_id}
        - Date of Loss: {claim.date_of_loss}
        - Claim Amount: ${claim.claim_amount:,.2f}
        - Description: {claim.description}
        - Peril Type: {claim.peril_type}
        - Category: {claim.claim_category}

        POLICY DETAILS:
        - Policy ID: {policy.policy_id}
        - Policy Type: {policy.policy_type_id}
        - Effective: {policy.effective_date}
        - Expires: {policy.expiration_date}

        AVAILABLE COVERAGES:
        {json.dumps(coverage_info, indent=2)}

        Analyze step by step:
        1. Is the loss date within policy period?
        2. Which coverage types match the peril/category?
        3. Do any exclusions apply?
        4. Are coverage conditions met?

        Provide objective analysis without predetermined conclusions.
        """
        
        try:
            result = chat_completion_with_structured_json(
                self.client,
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an objective insurance claims analysis AI. Analyze facts without bias."},
                    {"role": "user", "content": prompt}
                ],
                schema_dict=CoverageAnalysis.model_json_schema(),
                temperature=AI_TEMPERATURE,
                seed=AI_SEED,
            )
            return CoverageAnalysis.model_validate(result)
        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            # Return neutral analysis on failure
            return CoverageAnalysis(
                is_time_valid=False,
                matching_coverage_types=[],
                exclusion_triggered=False,
                exclusion_details="Analysis failed - manual review required",
                conditions_met=False,
                condition_details="Analysis failed - manual review required",
                confidence_score=0.0
            )
    
    def calculate_payout_and_final_decision(self, claim: Claim, coverages: List[Coverage], analysis: CoverageAnalysis) -> ClaimAssessment:
        """Calculate payout and make final decision based on analysis"""
        denial_reasons = []
        
        # Check eligibility conditions
        if not analysis.is_time_valid:
            denial_reasons.append("Loss date outside policy period")
        if analysis.exclusion_triggered:
            denial_reasons.append(f"Exclusion applies: {analysis.exclusion_details}")
        if not analysis.conditions_met:
            denial_reasons.append(f"Conditions not met: {analysis.condition_details}")

        # Find matching coverages
        matching_coverages = [c for c in coverages if c.coverage_type in analysis.matching_coverage_types]
        
        if not matching_coverages and not denial_reasons:
            denial_reasons.append("No matching coverage found")

        # Determine outcome
        is_covered = len(denial_reasons) == 0 and len(matching_coverages) > 0
        selected_coverage = None
        payout_amount = None

        if is_covered:
            # Select best coverage (highest limit, lowest deductible)
            selected_coverage = max(matching_coverages, 
                                  key=lambda c: (c.limit, -c.deductible))
            
            # Calculate payout
            claim_amt = Decimal(str(claim.claim_amount))
            limit_amt = Decimal(str(selected_coverage.limit))
            deduct_amt = Decimal(str(selected_coverage.deductible))
            
            payout = min(claim_amt, limit_amt) - deduct_amt
            if payout < Decimal('0'):
                payout = Decimal('0')
            payout_amount = float(payout.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        # Create reasoning
        if is_covered:
            reasoning = f"Claim approved under {selected_coverage.coverage_type} coverage"
        else:
            reasoning = f"Claim denied. Reasons: {'; '.join(denial_reasons)}"

        # Build assessment
        assessment = ClaimAssessment(
            claim_id=claim.claim_id,
            is_covered=is_covered,
            confidence_score=analysis.confidence_score,
            reasoning=reasoning,
            applicable_coverages=[selected_coverage.coverage_type] if selected_coverage else [],
            estimated_payout=payout_amount,
            step_by_step_analysis={
                "time_validation": "Valid" if analysis.is_time_valid else "Invalid",
                "coverage_matching": f"Found: {', '.join(analysis.matching_coverage_types)}" if analysis.matching_coverage_types else "No matches",
                "exclusion_check": analysis.exclusion_details,
                "conditions_check": analysis.condition_details,
                "payout_calculation": f"${payout_amount:,.2f}" if payout_amount else "No payout"
            }
        )
        
        return assessment

# ============= Main System =============
class ClaimsCoverageSystem:
    """Main claims coverage assessment system"""
    
    def __init__(self, openai_key: str = None, db_path: str = None):
        """Initialize the system with data adapter and AI agent"""
        self.data_adapter = BCDataAdapter(db_path or DATABASE_PATH)
        self.ai_agent = ClaimsCoverageAgent(openai_key or os.getenv("OPENAI_API_KEY"))
        
    def ensure_data_loaded(self) -> bool:
        """Ensure data is loaded and up to date"""
        result = self.data_adapter.import_berkeley_data_if_needed()
        if result["success"]:
            if result["imported"]:
                logger.info("Data imported successfully")
            return True
        else:
            logger.error(f"Failed to ensure data: {result.get('error', 'Unknown error')}")
            return False
    
    def process_claim(self, claim_id: str) -> Dict[str, Any]:
        """Process a single claim and return assessment"""
        claim = self.data_adapter.get_claim(claim_id)
        if not claim:
            return {"error": f"Claim not found: {claim_id}"}
        
        policy = self.data_adapter.get_policy(claim.policy_id)
        if not policy:
            return {"error": f"Policy not found: {claim.policy_id}"}
        
        coverages = self.data_adapter.get_coverages_by_policy(policy.policy_term_id)
        if not coverages:
            return {"error": f"No coverages found for policy: {policy.policy_id}"}
        
        logger.info(f"Processing claim {claim_id}")
        
        # AI analysis
        coverage_analysis = self.ai_agent.analyze_coverage_match(claim, policy, coverages)

        # Enforce deterministic time validity
        # is_time_valid_local = policy.effective_date <= claim.date_of_loss <= policy.expiration_date
        # if coverage_analysis.is_time_valid != is_time_valid_local:
        #     logger.info(
        #         f"Overriding AI time validity: AI={coverage_analysis.is_time_valid}, local={is_time_valid_local}"
        #     )
        #     print(f"policy effective date: {policy.effective_date}")
        #     print(f"policy expiration date: {policy.expiration_date}")
        #     print(f"claim date of loss: {claim.date_of_loss}")
        #     coverage_analysis.is_time_valid = is_time_valid_local

        is_time_valid_local = True
        try:
            today = date.today()
            # Sanity window: after 1900-01-01 and not after today
            if claim.date_of_loss < date(1900, 1, 1) or claim.date_of_loss > today:
                is_time_valid_local = False
        except Exception:
            is_time_valid_local = False

        if coverage_analysis.is_time_valid != is_time_valid_local:
            logger.info(
                f"Overriding AI time validity (term dates ignored): "
                f"AI={coverage_analysis.is_time_valid}, local={is_time_valid_local}"
            )
            print("NOTE: Ignoring policy term dates for time validity per business rule.")
            print(f"claim date of loss: {claim.date_of_loss}")
            coverage_analysis.is_time_valid = is_time_valid_local

        final_assessment = self.ai_agent.calculate_payout_and_final_decision(
            claim, coverages, coverage_analysis
        )
        
        return {
            "claim_info": {
                "claim_id": claim.claim_id,
                "policy_id": claim.policy_id,
                "date_of_loss": claim.date_of_loss.isoformat(),
                "claim_amount": claim.claim_amount,
                "description": claim.description,
                "category": claim.claim_category
            },
            "assessment": {
                "is_covered": final_assessment.is_covered,
                "confidence_score": final_assessment.confidence_score,
                "reasoning": final_assessment.reasoning,
                "estimated_payout": final_assessment.estimated_payout,
                "applicable_coverages": final_assessment.applicable_coverages,
                "analysis_details": final_assessment.step_by_step_analysis
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def process_claims(self, claim_ids: Union[str, List[str], int] = None) -> pd.DataFrame:
        """
        Process claims flexibly:
        - Single claim ID (str): process one claim
        - List of claim IDs: process specific claims  
        - Integer: process first N claims (for testing)
        - None: process all claims
        """
        if isinstance(claim_ids, str):
            # Single claim
            claim_list = [claim_ids]
        elif isinstance(claim_ids, list):
            # Specific claims
            claim_list = claim_ids
        elif isinstance(claim_ids, int):
            # First N claims for testing
            claim_list = self.data_adapter.get_claims(limit=claim_ids)
        else:
            # All claims
            claim_list = self.data_adapter.get_claims()
        
        logger.info(f"Processing {len(claim_list)} claims")
        
        results = []
        for i, claim_id in enumerate(claim_list, 1):
            try:
                logger.info(f"Processing claim {i}/{len(claim_list)}: {claim_id}")
                result = self.process_claim(claim_id)
                
                if "error" not in result:
                    results.append({
                        "claim_id": claim_id,
                        "is_covered": result["assessment"]["is_covered"],
                        "confidence": result["assessment"]["confidence_score"],
                        "payout": result["assessment"]["estimated_payout"],
                        "reasoning": result["assessment"]["reasoning"],
                        "coverages": ", ".join(result["assessment"]["applicable_coverages"])
                    })
                else:
                    logger.error(f"Error processing {claim_id}: {result['error']}")
                    
            except Exception as e:
                logger.error(f"Exception processing claim {claim_id}: {e}")
        
        return pd.DataFrame(results)

# ============= Main Execution =============
def main():
    """Main function for testing the system"""
    print("=== BC Claims Assessment System ===\n")
    
    # Initialize system
    try:
        system = ClaimsCoverageSystem()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set your OpenAI API key in the .env file or OPENAI_API_KEY environment variable")
        return
    
    # Ensure data is loaded
    print("Checking data status...")
    if not system.ensure_data_loaded():
        print("Failed to load data. Please check the Excel file and database.")
        return
    
    # Test with a few claims first
    print(f"Testing with {DEFAULT_TEST_CLAIMS} sample claims...")
    test_results = system.process_claims(DEFAULT_TEST_CLAIMS)  # Process first N claims
    
    if not test_results.empty:
        print("\n=== Sample Results ===")
        for _, row in test_results.iterrows():
            status = "COVERED" if row['is_covered'] else "DENIED"
            payout_str = f"${row['payout']:,.2f}" if row['payout'] else "No payout"
            print(f"Claim {row['claim_id']}: {status} - {payout_str}")
            print(f"  Reason: {row['reasoning']}")
            print(f"  Confidence: {row['confidence']:.1%}")
            print()
        
        # Ask user if they want to process more
        choice = input("Process all claims? (y/n): ").lower().strip()
        if choice == 'y':
            print("\nProcessing all claims...")
            all_results = system.process_claims()  # Process all claims
            
            if not all_results.empty:
                print(f"\n=== Summary of {len(all_results)} Claims ===")
                covered_count = all_results['is_covered'].sum()
                total_payout = all_results['payout'].sum()
                avg_confidence = all_results['confidence'].mean()
                
                print(f"Claims covered: {covered_count}/{len(all_results)} ({covered_count/len(all_results):.1%})")
                print(f"Total payout: ${total_payout:,.2f}")
                print(f"Average confidence: {avg_confidence:.1%}")
                
                # Save results
                output_file = f"claims_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                all_results.to_csv(output_file, index=False)
                print(f"\nResults saved to: {output_file}")
    else:
        print("No claims found to process.")

if __name__ == "__main__":
    main()
