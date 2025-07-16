# src/agents/toolkits/extraction_toolkit.py

import asyncio
from typing import List, Dict, Any

# 
from src.event_extraction.deepseek_extractor import DeepSeekEventExtractor
from src.event_extraction.validation import EventExtractionValidator
# from src.knowledge_graph.entity_kb import EntityKnowledgeBase # 

class EventExtractionToolkit:
    """
    
    """
    def __init__(self):
        """
        
        """
        self.extractor = DeepSeekEventExtractor()
        self.validator = EventExtractionValidator()
        # self.entity_kb = EntityKnowledgeBase() # 

    def extract_events_from_text(self, text: str, event_type: str, domain: str) -> List[Dict[str, Any]]:
        """
        

        Args:
            text: 
            event_type: 
            domain: 

        Returns:
            
            
        """
        try:
            # asyncio.run
            # AutoGenAgent
            # Agent
            raw_extraction_result = asyncio.run(
                self.extractor.extract_single_event(text=text, domain=domain, event_type=event_type)
            )

            if not raw_extraction_result or raw_extraction_result.get("metadata", {}).get("extraction_status") != "success":
                return []

            # 
            validation_result = self.validator.validate_extraction_result(
                result=raw_extraction_result,
                domain=domain,
                event_type=event_type
            )

            if not validation_result.is_valid:
                # 
                print(f"Validation failed: {validation_result.errors}")
                return []

            validated_event = raw_extraction_result

            # ---  ( ) ---
            # TODO:  (EntityKB) 
            #
            # event_data = validated_event.get("event_data", {})
            # if event_data:
            #     for field, value in event_data.items():
            #         # 
            #         if isinstance(value, str):
            #             # kb
            #             event_data[field] = self.entity_kb.normalize(value)
            #         elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            #             event_data[field] = [self.entity_kb.normalize(item) for item in value]
            #
            # validated_event["event_data"] = event_data
            # print("(")
            # ---------------------------------

            # 
            return [validated_event]

        except Exception as e:
            # 
            print(f"An error occurred during event extraction: {e}")
            return []

# 
if __name__ == '__main__':
    toolkit = EventExtractionToolkit()
    
    # 
    sample_text = "2024630"
    sample_event_type = "company_merger_and_acquisition"
    sample_domain = "financial_domain"

    print(f"
    
    extracted_events = toolkit.extract_events_from_text(
        text=sample_text,
        event_type=sample_event_type,
        domain=sample_domain
    )

    if extracted_events:
        print("\n:")
        import json
        print(json.dumps(extracted_events, indent=2, ensure_ascii=False))
    else:
        print("\n")
