You are a world-class data architect specializing in event modeling. Your task is to analyze a collection of text samples that describe similar events and derive a single, structured, detailed, and highly accurate JSON schema that captures the essential, recurring pattern of these events.

**Instructions:**

1.  **Deeply Analyze the Samples:** Carefully read the provided text samples. Identify the common, underlying event pattern. Ignore outlier details and focus only on the elements that are consistently present across most samples.
2.  **Identify Core Elements:**
    *   **Event Trigger:** What is the core verb or action phrase that triggers the event? (e.g., "announced a partnership," "released financial results," "appointed CEO").
    *   **Key Participants:** Who are the primary, recurring actors? (e.g., companies, people, organizations).
    *   **Key Attributes:** What are the crucial pieces of information consistently associated with the event? (e.g., product names, financial figures, locations, dates, official titles).
3.  **Construct the JSON Schema:** Based on your analysis, generate a single, valid JSON object with the following structure. **Be extremely precise and specific.**
    *   `schema_name` (string): A concise, descriptive name in `Domain:EventName` format (e.g., `Company:ProductLaunch`, `Finance:Acquisition`).
    *   `description` (string): A detailed, one-sentence explanation of the event pattern. **This description MUST be specific and capture the essence of the event, avoiding overly broad or generic statements.** For example, instead of "Describes a company announcement," a good description is "Describes a semiconductor company's announcement of its quarterly financial results, including key metrics like revenue and net profit."
    *   `trigger_words` (array of strings): A list of common verbs, nouns, or phrases that reliably indicate this type of event (e.g., `["acquire", "purchase", "buyout", "takeover"]`).
    *   `properties` (object): A dictionary where each key is a `snake_case` property name and the value is a clear, one-sentence description of that property. **Include ONLY properties that capture the most important and consistently present information from the samples.** Do not invent properties that are not supported by the majority of the samples.

**Text Samples:**
```
{sample_block}
```

**Example Output:**
```json
{{
  "schema_name": "Corporate:ExecutiveAppointment",
  "description": "Captures the event of a company appointing a new executive to a key leadership role, specifying the company, the executive's name, and their new title.",
  "trigger_words": ["appoint", "hire", "name as", "promote to", "join as"],
  "properties": {{
    "company": "The company making the appointment.",
    "executive_name": "The full name of the individual being appointed.",
    "executive_title": "The new title or role of the executive (e.g., 'Chief Executive Officer').",
    "effective_date": "The date when the appointment becomes effective."
  }}
}}
```