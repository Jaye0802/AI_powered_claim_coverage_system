"""
Performance Monitor for Claims System
Tracks system performance and provides optimization recommendations
"""

import time
import psutil
import sqlite3
from typing import Dict, List
from datetime import datetime
import logging

from claims_system_clean import ClaimsCoverageSystem, BCDataAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor system performance and resource usage"""
    
    def __init__(self):
        self.metrics = {}
        self.start_time = None
        self.start_memory = None
    
    def start_monitoring(self):
        """Start performance monitoring"""
        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self) -> Dict[str, any]:
        """Stop monitoring and return metrics"""
        if self.start_time is None:
            return {}
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        self.metrics = {
            "duration_seconds": end_time - self.start_time,
            "memory_start_mb": self.start_memory,
            "memory_end_mb": end_memory,
            "memory_delta_mb": end_memory - self.start_memory,
            "cpu_percent": psutil.cpu_percent(),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Performance monitoring completed: {self.metrics['duration_seconds']:.2f}s")
        return self.metrics
    
    def benchmark_data_import(self) -> Dict[str, any]:
        """Benchmark data import performance"""
        print("=== Data Import Performance Test ===")
        
        adapter = BCDataAdapter()
        
        self.start_monitoring()
        result = adapter.import_berkeley_data()
        metrics = self.stop_monitoring()
        
        if result["success"]:
            stats = result["stats"]
            records_per_second = sum(stats.values()) / metrics["duration_seconds"]
            
            performance_report = {
                "import_result": result,
                "performance": metrics,
                "records_processed": sum(stats.values()),
                "records_per_second": records_per_second,
                "efficiency_rating": self._rate_import_efficiency(metrics, sum(stats.values()))
            }
            
            print(f"Import completed successfully")
            print(f"Records processed: {sum(stats.values()):,}")
            print(f"Duration: {metrics['duration_seconds']:.2f} seconds")
            print(f"Processing rate: {records_per_second:,.0f} records/second")
            print(f"Memory usage: {metrics['memory_delta_mb']:.1f} MB")
            print(f"Efficiency: {performance_report['efficiency_rating']}")
            
            return performance_report
        else:
            print(f"Import failed: {result['error']}")
            return {"error": result["error"], "performance": metrics}
    
    def benchmark_claim_processing(self, num_claims: int = 5) -> Dict[str, any]:
        """Benchmark claim processing performance"""
        print(f"\n=== Claim Processing Performance Test ({num_claims} claims) ===")
        
        try:
            system = ClaimsCoverageSystem()
            system.ensure_data_loaded()
            
            self.start_monitoring()
            results = system.process_claims(num_claims)
            metrics = self.stop_monitoring()
            
            if not results.empty:
                claims_per_second = len(results) / metrics["duration_seconds"]
                
                performance_report = {
                    "claims_processed": len(results),
                    "performance": metrics,
                    "claims_per_second": claims_per_second,
                    "success_rate": len(results) / num_claims,
                    "efficiency_rating": self._rate_processing_efficiency(metrics, len(results))
                }
                
                print(f"Processing completed successfully")
                print(f"Claims processed: {len(results)}")
                print(f"Duration: {metrics['duration_seconds']:.2f} seconds")
                print(f"Processing rate: {claims_per_second:.2f} claims/second")
                print(f"Memory usage: {metrics['memory_delta_mb']:.1f} MB")
                print(f"Efficiency: {performance_report['efficiency_rating']}")
                
                return performance_report
            else:
                print("No claims processed")
                return {"error": "No claims processed", "performance": metrics}
                
        except Exception as e:
            print(f"Processing failed: {e}")
            return {"error": str(e), "performance": self.stop_monitoring()}
    
    def _rate_import_efficiency(self, metrics: Dict, total_records: int) -> str:
        """Rate import efficiency"""
        records_per_second = total_records / metrics["duration_seconds"]
        memory_per_record = metrics["memory_delta_mb"] / total_records * 1000  # KB per record
        
        if records_per_second > 10000 and memory_per_record < 1:
            return "Excellent"
        elif records_per_second > 5000 and memory_per_record < 2:
            return "Good"
        elif records_per_second > 1000 and memory_per_record < 5:
            return "Fair"
        else:
            return "Needs Optimization"
    
    def _rate_processing_efficiency(self, metrics: Dict, num_claims: int) -> str:
        """Rate processing efficiency"""
        claims_per_second = num_claims / metrics["duration_seconds"]
        memory_per_claim = metrics["memory_delta_mb"] / num_claims if num_claims > 0 else 0
        
        if claims_per_second > 2 and memory_per_claim < 10:
            return "Excellent"
        elif claims_per_second > 1 and memory_per_claim < 20:
            return "Good"
        elif claims_per_second > 0.5 and memory_per_claim < 50:
            return "Fair"
        else:
            return "Needs Optimization"
    
    def analyze_database_performance(self) -> Dict[str, any]:
        """Analyze database performance and structure"""
        print("\n=== Database Performance Analysis ===")
        
        adapter = BCDataAdapter()
        analysis = {}
        
        with adapter.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check database size
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0] / 1024 / 1024  # MB
            
            # Check index usage
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]
            
            # Check table sizes
            tables = ['policies', 'claims', 'coverages']
            table_sizes = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                table_sizes[table] = cursor.fetchone()[0]
            
            # Test query performance
            query_times = {}
            
            # Test policy lookup
            start = time.time()
            cursor.execute("SELECT * FROM policies LIMIT 100")
            cursor.fetchall()
            query_times["policy_lookup"] = time.time() - start
            
            # Test claim with policy join
            start = time.time()
            cursor.execute("""
                SELECT c.*, p.policy_number 
                FROM claims c 
                JOIN policies p ON c.policy_id = p.policy_id 
                LIMIT 100
            """)
            cursor.fetchall()
            query_times["claim_policy_join"] = time.time() - start
            
            # Test coverage lookup
            start = time.time()
            cursor.execute("SELECT * FROM coverages WHERE policy_term_id LIKE 'TERM-%' LIMIT 100")
            cursor.fetchall()
            query_times["coverage_lookup"] = time.time() - start
        
        analysis = {
            "database_size_mb": db_size,
            "indexes": indexes,
            "table_sizes": table_sizes,
            "query_performance": query_times,
            "performance_rating": self._rate_db_performance(db_size, query_times)
        }
        
        print(f"Database size: {db_size:.1f} MB")
        print(f"Table sizes: {table_sizes}")
        print(f"Indexes: {len(indexes)} active")
        print(f"Query performance:")
        for query, time_taken in query_times.items():
            print(f"  {query}: {time_taken:.4f}s")
        print(f"Overall rating: {analysis['performance_rating']}")
        
        return analysis
    
    def _rate_db_performance(self, size_mb: float, query_times: Dict) -> str:
        """Rate database performance"""
        avg_query_time = sum(query_times.values()) / len(query_times)
        
        if avg_query_time < 0.001 and size_mb < 100:
            return "Excellent"
        elif avg_query_time < 0.01 and size_mb < 500:
            return "Good"
        elif avg_query_time < 0.1 and size_mb < 1000:
            return "Fair"
        else:
            return "Needs Optimization"
    
    def generate_optimization_recommendations(self) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        # Analyze current metrics
        db_analysis = self.analyze_database_performance()
        
        if db_analysis["database_size_mb"] > 500:
            recommendations.append("Consider database partitioning for large datasets")
        
        if max(db_analysis["query_performance"].values()) > 0.1:
            recommendations.append("Add more specific indexes for slow queries")
        
        if len(db_analysis["indexes"]) < 5:
            recommendations.append("Add indexes on frequently queried columns")
        
        recommendations.extend([
            "Implement connection pooling for concurrent access",
            "Consider caching frequently accessed policy data",
            "Implement batch processing for large claim volumes",
            "Add query optimization for complex joins",
            "Consider read replicas for reporting queries"
        ])
        
        return recommendations

def main():
    """Run comprehensive performance testing"""
    print("Claims System Performance Monitor")
    print("=" * 50)
    
    monitor = PerformanceMonitor()
    
    # Test data import performance
    import_perf = monitor.benchmark_data_import()
    
    # Test claim processing performance
    processing_perf = monitor.benchmark_claim_processing(5)
    
    # Analyze database performance
    db_perf = monitor.analyze_database_performance()
    
    # Generate recommendations
    print("\n=== Optimization Recommendations ===")
    recommendations = monitor.generate_optimization_recommendations()
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    print("\n" + "=" * 50)
    print("Performance testing completed!")

if __name__ == "__main__":
    main()
