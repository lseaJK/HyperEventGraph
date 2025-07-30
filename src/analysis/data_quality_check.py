import json
import os
from collections import defaultdict

def analyze_data_quality(file_path):
    """
    Analyzes the data quality of a JSONL file containing structured events.

    Args:
        file_path (str): The path to the JSONL file.

    Returns:
        dict: A dictionary containing the analysis results.
    """
    total_lines = 0
    json_errors = 0
    missing_event_type = 0
    empty_entities = 0
    valid_records = 0
    
    event_type_distribution = defaultdict(int)
    micro_event_type_distribution = defaultdict(int)
    entity_type_distribution = defaultdict(int)
    role_distribution = defaultdict(int)
    entity_name_frequency = defaultdict(int)
    quantitative_metrics = defaultdict(int)


    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            total_lines += 1
            try:
                data = json.loads(line)
                
                # Check for key fields
                if not data.get('event_type'):
                    missing_event_type += 1
                
                if not data.get('involved_entities'):
                    empty_entities += 1
                
                if data.get('event_type') and data.get('involved_entities'):
                    valid_records += 1

                    # Step 2 & 3: Analyze entities, events, and roles
                    event_type_distribution[data['event_type']] += 1
                    if data.get('micro_event_type'):
                        micro_event_type_distribution[data['micro_event_type']] += 1

                    for entity in data.get('involved_entities', []):
                        if entity.get('entity_type'):
                            entity_type_distribution[entity['entity_type']] += 1
                        if entity.get('role_in_event'):
                            role_distribution[entity['role_in_event']] += 1
                        if entity.get('entity_name'):
                            entity_name_frequency[entity['entity_name']] += 1
                
                # Step 4: Analyze quantitative data
                if data.get('quantitative_data') and isinstance(data['quantitative_data'], dict):
                    if data['quantitative_data'].get('metric'):
                        quantitative_metrics[data['quantitative_data']['metric']] += 1


            except json.JSONDecodeError:
                json_errors += 1

    # Find potential entity name variations for normalization
    potential_duplicates = []
    entities = list(entity_name_frequency.keys())
    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            if entities[i] in entities[j] or entities[j] in entities[i]:
                 if entity_name_frequency[entities[i]] > 1 and entity_name_frequency[entities[j]] > 1:
                    potential_duplicates.append((entities[i], entities[j]))

    results = {
        "total_lines": total_lines,
        "valid_records": valid_records,
        "json_errors": json_errors,
        "missing_event_type": missing_event_type,
        "empty_entities": empty_entities,
        "event_type_distribution": dict(sorted(event_type_distribution.items(), key=lambda item: item[1], reverse=True)),
        "micro_event_type_distribution": dict(sorted(micro_event_type_distribution.items(), key=lambda item: item[1], reverse=True)),
        "entity_type_distribution": dict(sorted(entity_type_distribution.items(), key=lambda item: item[1], reverse=True)),
        "role_distribution": dict(sorted(role_distribution.items(), key=lambda item: item[1], reverse=True)),
        "top_20_entities": dict(sorted(entity_name_frequency.items(), key=lambda item: item[1], reverse=True)[:20]),
        "quantitative_metrics_distribution": dict(sorted(quantitative_metrics.items(), key=lambda item: item[1], reverse=True)),
        "potential_duplicate_entities": potential_duplicates[:20] # Show top 20 potential duplicates
    }
    
    return results

def print_report(results):
    print("--- Data Quality and Integrity Report ---")
    print(f"Total lines processed: {results['total_lines']}")
    print(f"Valid records: {results['valid_records']}")
    print(f"JSON parsing errors: {results['json_errors']}")
    print(f"Records with missing 'event_type': {results['missing_event_type']}")
    print(f"Records with empty 'involved_entities': {results['empty_entities']}")
    
    print("\n--- Event Type Distribution ---")
    for event, count in results['event_type_distribution'].items():
        print(f"- {event}: {count}")

    print("\n--- Top 20 Micro Event Type Distribution ---")
    for event, count in list(results['micro_event_type_distribution'].items())[:20]:
        print(f"- {event}: {count}")

    print("\n--- Entity Type Distribution ---")
    for entity_type, count in results['entity_type_distribution'].items():
        print(f"- {entity_type}: {count}")

    print("\n--- Top 20 Role Distribution ---")
    for role, count in list(results['role_distribution'].items())[:20]:
        print(f"- {role}: {count}")

    print("\n--- Top 20 Most Frequent Entities ---")
    for entity, count in results['top_20_entities'].items():
        print(f"- {entity}: {count}")
        
    print("\n--- Quantitative Metrics Distribution ---")
    for metric, count in results['quantitative_metrics_distribution'].items():
        print(f"- {metric}: {count}")

    print("\n--- Potential Duplicate Entities (Sample) ---")
    for e1, e2 in results['potential_duplicate_entities']:
        print(f"- '{e1}' vs '{e2}'")
    print("-------------------------------------------")


if __name__ == "__main__":
    # Create analysis directory if it doesn't exist
    if not os.path.exists('src/analysis'):
        os.makedirs('src/analysis')
        
    file_path = 'docs/output/structured_events.jsonl'
    analysis_results = analyze_data_quality(file_path)
    print_report(analysis_results)
    
    # Save results to a file
    output_path = 'src/analysis/quality_report.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=4)
    print(f"\nFull analysis report saved to {output_path}")

