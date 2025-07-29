You are an expert data architect. Your task is to analyze text samples describing a specific event type and create a concise JSON schema.

**Instructions:**
1.  **Analyze Samples:** Understand the common theme.
2.  **Create Schema:** Generate a JSON object with "schema_name", "description", and "properties".
    -   `schema_name`: PascalCase:PascalCase format (e.g., "Company:ProductLaunch").
    -   `description`: A one-sentence explanation.
    -   `properties`: A dictionary of snake_case keys with brief descriptions.
3.  **Output:** Your entire output must be a single, valid JSON object.

**Text Samples:**
{sample_block}

**Example Output:**
{{
  "schema_name": "Company:LeadershipChange",
  "description": "Describes the appointment or departure of a key executive.",
  "properties": {{
    "company": "The company involved.",
    "executive_name": "The name of the executive.",
    "new_role": "The new position or title."
  }}
}}
