"""
Data Validation Utility for Claims System
Validates data quality and system integrity
"""

import sqlite3
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Tuple
import logging

from claims_system_clean import BCDataAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataValidator:
    """Validate data quality and system integrity"""
    
    def __init__(self, db_path: str = "bc_real_invalid.db"):
        self.adapter = BCDataAdapter(db_path)
    
    def validate_data_quality(self) -> Dict[str, any]:
        """Comprehensive data quality validation"""
        results = {
            "date_issues": [],
            "amount_issues": [],
            "relationship_issues": [],
            "data_completeness": {},
            "recommendations": []
        }
        
        with self.adapter.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check for date issues
            cursor.execute("""
                SELECT claim_id, date_of_loss 
                FROM claims 
                WHERE date_of_loss = '1900-01-01' OR date_of_loss < '2000-01-01'
            """)
            invalid_dates = cursor.fetchall()
            if invalid_dates:
                results["date_issues"] = [{"claim_id": row[0], "date": row[1]} for row in invalid_dates]
                results["recommendations"].append("Fix invalid loss dates - some claims have dates from 1900")
            
            # Check for amount issues
            cursor.execute("""
                SELECT claim_id, claim_amount 
                FROM claims 
                WHERE claim_amount = 0.0 OR claim_amount IS NULL
            """)
            zero_amounts = cursor.fetchall()
            if zero_amounts:
                results["amount_issues"] = [{"claim_id": row[0], "amount": row[1]} for row in zero_amounts]
                results["recommendations"].append("Review claims with zero amounts - may need manual assignment")
            
            # Check relationship integrity
            cursor.execute("""
                SELECT c.claim_id, c.policy_id 
                FROM claims c 
                LEFT JOIN policies p ON c.policy_id = p.policy_id 
                WHERE p.policy_id IS NULL
            """)
            orphaned_claims = cursor.fetchall()
            if orphaned_claims:
                results["relationship_issues"] = [{"claim_id": row[0], "policy_id": row[1]} for row in orphaned_claims]
                results["recommendations"].append("Fix orphaned claims - some claims reference non-existent policies")
            
            # Data completeness
            cursor.execute("SELECT COUNT(*) FROM policies")
            policy_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM claims")
            claim_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM coverages")
            coverage_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM claims WHERE description IS NOT NULL AND description != ''")
            claims_with_desc = cursor.fetchone()[0]
            
            results["data_completeness"] = {
                "total_policies": policy_count,
                "total_claims": claim_count,
                "total_coverages": coverage_count,
                "claims_with_description": claims_with_desc,
                "description_rate": claims_with_desc / claim_count if claim_count > 0 else 0
            }
            
            # Check date ranges
            cursor.execute("SELECT MIN(date_of_loss), MAX(date_of_loss) FROM claims")
            date_range = cursor.fetchone()
            results["data_completeness"]["date_range"] = {
                "earliest": date_range[0],
                "latest": date_range[1]
            }
            
            # Check amount ranges
            cursor.execute("SELECT MIN(claim_amount), MAX(claim_amount), AVG(claim_amount) FROM claims WHERE claim_amount > 0")
            amount_stats = cursor.fetchone()
            results["data_completeness"]["amount_stats"] = {
                "min": amount_stats[0],
                "max": amount_stats[1],
                "avg": amount_stats[2]
            }
        
        return results
    
    def suggest_data_fixes(self) -> List[str]:
        """Suggest specific fixes for data issues"""
        suggestions = []
        validation = self.validate_data_quality()
        
        if validation["date_issues"]:
            suggestions.append("Re-import data with proper Excel date parsing")
            suggestions.append("Consider using pd.to_datetime with Excel serial date conversion")
        
        if validation["amount_issues"]:
            suggestions.append("Implement business rules for default claim amounts by type")
            suggestions.append("Use industry averages for missing claim amounts")
        
        if validation["relationship_issues"]:
            suggestions.append("Add foreign key constraints to prevent orphaned records")
            suggestions.append("Implement data validation before insert")
        
        return suggestions
    
    def run_comprehensive_validation(self) -> None:
        """Run complete validation and print report"""
        print("=== Data Quality Validation Report ===\n")
        
        validation = self.validate_data_quality()
        
        # Date issues
        if validation["date_issues"]:
            print(f"Found {len(validation['date_issues'])} claims with invalid dates")
            print("Sample invalid dates:")
            for issue in validation["date_issues"][:5]:
                print(f"  Claim {issue['claim_id']}: {issue['date']}")
            print()
        else:
            print("No date issues found\n")
        
        # Amount issues
        if validation["amount_issues"]:
            print(f"Found {len(validation['amount_issues'])} claims with zero/null amounts")
            print("This may be normal for some claim types\n")
        else:
            print("No amount issues found\n")
        
        # Relationship issues
        if validation["relationship_issues"]:
            print(f"Found {len(validation['relationship_issues'])} orphaned claims")
            print("These claims reference non-existent policies\n")
        else:
            print("No relationship issues found\n")
        
        # Data completeness
        completeness = validation["data_completeness"]
        print("Data Completeness:")
        print(f"  Policies: {completeness['total_policies']:,}")
        print(f"  Claims: {completeness['total_claims']:,}")
        print(f"  Coverages: {completeness['total_coverages']:,}")
        print(f"  Claims with descriptions: {completeness['claims_with_description']:,} ({completeness['description_rate']:.1%})")
        
        if completeness["date_range"]["earliest"]:
            print(f"  Date range: {completeness['date_range']['earliest']} to {completeness['date_range']['latest']}")
        
        if completeness["amount_stats"]["avg"]:
            print(f"  Amount range: ${completeness['amount_stats']['min']:,.2f} to ${completeness['amount_stats']['max']:,.2f}")
            print(f"  Average claim: ${completeness['amount_stats']['avg']:,.2f}")
        
        print()
        
        # Recommendations
        if validation["recommendations"]:
            print("Recommendations:")
            for rec in validation["recommendations"]:
                print(f"  • {rec}")
            print()
        
        # Suggested fixes
        fixes = self.suggest_data_fixes()
        if fixes:
            print("Suggested Fixes:")
            for fix in fixes:
                print(f"  - {fix}")

def main():
    """Run data validation"""
    validator = DataValidator()
    validator.run_comprehensive_validation()

if __name__ == "__main__":
    main()
