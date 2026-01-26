#!/usr/bin/env python3
"""
Archive the current iteration of dataset_light.jsonl to dataset_light_test.jsonl
with iteration classification, then reset dataset_light.jsonl for the next iteration.
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATASET_PATH = os.path.join(OUTPUT_DIR, "dataset_light.jsonl")
TEST_PATH = os.path.join(OUTPUT_DIR, "dataset_light_test.jsonl")

def get_next_iteration():
    """Determine the next iteration number."""
    if not os.path.exists(TEST_PATH):
        return 1
    
    max_iteration = 0
    try:
        with open(TEST_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    iteration = record.get('_iteration', 0)
                    if iteration > max_iteration:
                        max_iteration = iteration
                except:
                    pass
    except:
        pass
    
    return max_iteration + 1

def archive_iteration():
    """Archive current iteration and reset dataset."""
    
    if not os.path.exists(DATASET_PATH):
        print("❌ dataset_light.jsonl niet gevonden!")
        return
    
    # Read current dataset
    records = []
    try:
        with open(DATASET_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    except Exception as e:
        print(f"❌ Fout bij lezen dataset_light.jsonl: {e}")
        return
    
    if not records:
        print("⚠️  dataset_light.jsonl is leeg, niets om te archiveren")
        return
    
    # Get iteration number
    iteration = get_next_iteration()
    timestamp = datetime.now().isoformat()
    
    # Add iteration metadata to each record
    print(f"\n📊 Archiveren van iteratie {iteration}...")
    print(f"   Records: {len(records)}")
    print(f"   Timestamp: {timestamp}")
    
    archived_records = []
    for record in records:
        record['_iteration'] = iteration
        record['_archived_at'] = timestamp
        archived_records.append(json.dumps(record, ensure_ascii=False))
    
    # Append to test file
    try:
        with open(TEST_PATH, 'a', encoding='utf-8') as f:
            for record_json in archived_records:
                f.write(record_json + '\n')
        print(f"✓ {len(archived_records)} records gearchiveerd naar dataset_light_test.jsonl")
    except Exception as e:
        print(f"❌ Fout bij schrijven naar dataset_light_test.jsonl: {e}")
        return
    
    # Clear current dataset
    try:
        with open(DATASET_PATH, 'w', encoding='utf-8') as f:
            pass  # Empty file
        print(f"✓ dataset_light.jsonl gereset en klaar voor volgende iteratie")
    except Exception as e:
        print(f"❌ Fout bij resetten dataset_light.jsonl: {e}")
        return
    
    # Show summary
    test_records = 0
    try:
        with open(TEST_PATH, 'r', encoding='utf-8') as f:
            test_records = sum(1 for line in f if line.strip())
    except:
        pass
    
    print(f"\n📈 Totaal records in dataset_light_test.jsonl: {test_records}")
    print(f"✅ Klaar! Je kunt nu opnieuw beginnen met iteratie {iteration + 1}\n")

if __name__ == "__main__":
    archive_iteration()
