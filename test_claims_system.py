"""
Test script for the Claims Coverage System
Demonstrates functionality with and without AI analysis
"""

import os
import sys
from datetime import datetime, date

# Add the current directory to the path so we can import our module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from claims_system_clean import ClaimsCoverageSystem, BCDataAdapter

def test_data_loading():
    """Test data loading functionality"""
    print("=== Testing Data Loading ===")
    
    adapter = BCDataAdapter()
    
    # Test if data needs import
    needs_import = adapter.needs_data_import()
    print(f"Needs data import: {needs_import}")
    
    # Test data import
    result = adapter.import_berkeley_data_if_needed()
    print(f"Import result: {result}")
    
    # Test data retrieval
    claims = adapter.get_claims(limit=5)
    print(f"Sample claims: {claims}")
    
    if claims:
        claim = adapter.get_claim(claims[0])
        print(f"Sample claim details: {claim}")
        
        policy = adapter.get_policy(claim.policy_id)
        print(f"Associated policy: {policy}")
        
        coverages = adapter.get_coverages_by_policy(policy.policy_term_id)
        print(f"Policy coverages: {len(coverages)} found")
    
    return True

def test_system_without_ai():
    """Test the system with mock AI responses"""
    print("\n=== Testing System (Mock AI Mode) ===")
    
    # Create a mock system that doesn't use OpenAI
    class MockClaimsCoverageSystem:
        def __init__(self):
            self.data_adapter = BCDataAdapter()
        
        def ensure_data_loaded(self):
            return True
        
        def process_claim_basic(self, claim_id: str):
            """Basic claim processing without AI"""
            claim = self.data_adapter.get_claim(claim_id)
            if not claim:
                return {"error": f"Claim not found: {claim_id}"}
            
            policy = self.data_adapter.get_policy(claim.policy_id)
            if not policy:
                return {"error": f"Policy not found: {claim.policy_id}"}
            
            coverages = self.data_adapter.get_coverages_by_policy(policy.policy_term_id)
            if not coverages:
                return {"error": f"No coverages found for policy: {policy.policy_id}"}
            
            # Basic rule-based assessment
            # is_time_valid = policy.effective_date <= claim.date_of_loss <= policy.expiration_date
            # Time validity (UPDATED): ignore policy term dates for coverage; only sanity-check loss date
            is_time_valid = True
            try:
                today = datetime.today().date()
                if claim.date_of_loss < date(1900, 1, 1) or claim.date_of_loss > today:
                    is_time_valid = False
            except Exception:
                is_time_valid = False

            # Find matching coverage based on peril type
            matching_coverages = []
            for coverage in coverages:
                if (claim.peril_type.lower() in coverage.coverage_type.lower() or 
                    claim.claim_category.lower() in coverage.coverage_type.lower()):
                    matching_coverages.append(coverage)
            
            is_covered = is_time_valid and len(matching_coverages) > 0
            
            # Calculate payout if covered
            payout = None
            if is_covered and matching_coverages:
                best_coverage = max(matching_coverages, key=lambda c: c.limit)
                payout = min(claim.claim_amount, best_coverage.limit) - best_coverage.deductible
                payout = max(0, payout)
            
            reasoning = []
            if not is_time_valid:
                reasoning.append("Loss date outside policy period")
            if not matching_coverages:
                reasoning.append("No matching coverage found")
            if is_covered:
                reasoning.append(f"Covered under {matching_coverages[0].coverage_type}")
            
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
                    "is_covered": is_covered,
                    "confidence_score": 0.8 if is_covered else 0.9,  # Mock confidence
                    "reasoning": "; ".join(reasoning) if reasoning else "Basic rule-based assessment",
                    "estimated_payout": payout,
                    "applicable_coverages": [c.coverage_type for c in matching_coverages],
                    "analysis_details": {
                        "time_validation": "Valid" if is_time_valid else "Invalid",
                        "coverage_matching": f"Found: {len(matching_coverages)} matches",
                        "exclusion_check": "Not evaluated (mock mode)",
                        "conditions_check": "Not evaluated (mock mode)",
                        "payout_calculation": f"${payout:.2f}" if payout else "No payout"
                    }
                },
                "timestamp": datetime.now().isoformat()
            }
    
    # Test with mock system
    mock_system = MockClaimsCoverageSystem()
    
    # Get some test claims
    claims = mock_system.data_adapter.get_claims(limit=3)
    print(f"Testing with {len(claims)} claims")
    
    for claim_id in claims:
        result = mock_system.process_claim_basic(claim_id)
        if "error" not in result:
            status = "COVERED" if result["assessment"]["is_covered"] else "DENIED"
            payout = result["assessment"]["estimated_payout"]
            payout_str = f"${payout:,.2f}" if payout else "No payout"
            
            print(f"\nClaim {claim_id}: {status} - {payout_str}")
            print(f"  Reason: {result['assessment']['reasoning']}")
            print(f"  Confidence: {result['assessment']['confidence_score']:.1%}")
        else:
            print(f"\nClaim {claim_id}: ERROR - {result['error']}")

def test_flexibility():
    """Test the flexible processing options"""
    print("\n=== Testing Processing Flexibility ===")
    
    adapter = BCDataAdapter()
    
    # Test different ways to get claims
    print("All claims count:", len(adapter.get_claims()))
    print("First 5 claims:", adapter.get_claims(limit=5))
    
    # Demonstrate the flexible interface
    print("\nFlexible processing options demonstrated:")
    print("1. Single claim: system.process_claims('claim_id')")
    print("2. Multiple claims: system.process_claims(['claim1', 'claim2'])")
    print("3. First N claims: system.process_claims(5)  # for testing")
    print("4. All claims: system.process_claims()  # for production")

def generate_summary_report():
    """Generate a summary report of the data"""
    print("\n=== Data Summary Report ===")
    
    adapter = BCDataAdapter()
    
    # Get database statistics
    with adapter.get_connection() as conn:
        cursor = conn.cursor()
        
        # Count records
        cursor.execute("SELECT COUNT(*) as count FROM policies")
        policy_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM claims")
        claim_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM coverages")
        coverage_count = cursor.fetchone()['count']
        
        # Claim status breakdown
        cursor.execute("SELECT claim_status, COUNT(*) as count FROM claims GROUP BY claim_status")
        status_breakdown = cursor.fetchall()
        
        # Coverage type breakdown
        cursor.execute("SELECT coverage_type, COUNT(*) as count FROM coverages GROUP BY coverage_type ORDER BY count DESC LIMIT 10")
        coverage_breakdown = cursor.fetchall()
        
        # Claim amount statistics
        cursor.execute("SELECT AVG(claim_amount) as avg_amount, MIN(claim_amount) as min_amount, MAX(claim_amount) as max_amount FROM claims WHERE claim_amount > 0")
        amount_stats = cursor.fetchone()
    
    print(f"Database Statistics:")
    print(f"  Policies: {policy_count:,}")
    print(f"  Claims: {claim_count:,}")
    print(f"  Coverages: {coverage_count:,}")
    
    print(f"\nClaim Status Breakdown:")
    for row in status_breakdown:
        print(f"  {row['claim_status']}: {row['count']:,}")
    
    print(f"\nTop 10 Coverage Types:")
    for row in coverage_breakdown:
        print(f"  {row['coverage_type']}: {row['count']:,}")
    
    if amount_stats['avg_amount']:
        print(f"\nClaim Amount Statistics:")
        print(f"  Average: ${amount_stats['avg_amount']:,.2f}")
        print(f"  Minimum: ${amount_stats['min_amount']:,.2f}")
        print(f"  Maximum: ${amount_stats['max_amount']:,.2f}")

def main():
    """Run all tests"""
    print("Claims Coverage System - Test Suite")
    print("=" * 50)
    
    try:
        # Test 1: Data loading
        test_data_loading()
        
        # Test 2: System without AI
        test_system_without_ai()
        
        # Test 3: Flexibility demonstration
        test_flexibility()
        
        # Test 4: Summary report
        generate_summary_report()
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        print("\nTo run the full system with AI analysis:")
        print("1. Set your OpenAI API key in .env file")
        print("2. Run: python claims_system_clean.py")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
