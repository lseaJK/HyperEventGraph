#!/usr/bin/env python3
"""
Quick database initialization script for testing the web interface.
"""

import sys
import sqlite3
from pathlib import Path

def create_minimal_database():
    """Create a minimal database with sample data."""
    
    project_root = Path(__file__).resolve().parent
    db_path = project_root / "master_state.db"
    
    print(f"Creating minimal database at: {db_path}")
    
    # Create database and table
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_state (
            id TEXT PRIMARY KEY,
            source_text TEXT NOT NULL,
            current_status TEXT NOT NULL,
            triage_confidence REAL,
            assigned_event_type TEXT,
            extraction_result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add sample data
    sample_data = [
        ('test_001', '某公司发布了新产品，预计将带来显著收益。', 'pending_triage'),
        ('test_002', '两家公司签署了战略合作协议。', 'pending_extraction'), 
        ('test_003', '市场分析师预测该行业将迎来快速增长。', 'completed'),
        ('test_004', '新技术突破将改变行业格局。', 'pending_triage'),
        ('test_005', '公司发布季度财报，收入超预期。', 'pending_extraction'),
    ]
    
    cursor.executemany(
        "INSERT OR REPLACE INTO master_state (id, source_text, current_status) VALUES (?, ?, ?)",
        sample_data
    )
    
    conn.commit()
    conn.close()
    
    print("Database created successfully!")
    
    # Verify
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT current_status, COUNT(*) FROM master_state GROUP BY current_status")
    status_counts = cursor.fetchall()
    
    print("\nStatus summary:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
    
    conn.close()

if __name__ == "__main__":
    create_minimal_database()
