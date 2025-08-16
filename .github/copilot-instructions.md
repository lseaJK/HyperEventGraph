# HyperEventGraph AI Coding Instructions

## Python Environment
（1）代码修改在当前windows项目中，我会自己同步过去
（2）代码运行、反馈在服务器ubuntu20.04，用interaction-feedback与我交互

## Architecture Overview

HyperEventGraph is an **event-centric knowledge graph system** that processes unstructured text through a multi-stage AI pipeline to build self-evolving knowledge graphs. The system uses a **dual-database architecture** (Neo4j + ChromaDB) and follows a **state-driven workflow orchestration** pattern.

### Core Data Flow
```
Raw Text → Triage → Human Review → Extraction → Clustering → Cortex Refinement → Relationship Analysis → Knowledge Storage
```

**Key Principle**: All processing is tracked through `master_state.db` with status transitions (`pending_triage` → `pending_review` → `pending_extraction` → `pending_clustering` → `pending_relationship_analysis` → `completed`).

## Essential System Components

### 1. Intelligent Agents (`src/agents/`)
- **TriageAgent**: First-stage classifier that dynamically loads event schemas from registry
- **ExtractionAgent**: Schema-driven extractor that converts text to structured events
- **CortexAgent/RefinementAgent**: Groups events into coherent "story units"
- **RelationshipAnalysisAgent**: Analyzes causal/temporal relationships between events
- **StorageAgent**: Manages dual-database persistence (Neo4j graphs + ChromaDB vectors)
- **HybridRetrieverAgent**: Provides knowledge-enhanced context for analysis

### 2. Core Orchestration (`run_*.py` scripts)
- `run_batch_triage.py`: Async batch processing with concurrency limits
- `run_extraction_workflow.py`: High-concurrency event extraction with auto-triggering
- `run_cortex_workflow.py`: Event clustering and story generation
- `run_relationship_analysis.py`: Knowledge-enhanced relationship discovery
- `run_learning_workflow.py`: Interactive schema learning for unknown events

### 3. Central State Management
- **DatabaseManager** (`src/core/database_manager.py`): All SQLite operations with schema evolution support
- **Config system** (`config.yaml`): LLM routing, database connections, workflow parameters
- **Status-driven processing**: Each workflow queries specific statuses and updates upon completion

## Development Patterns

### Agent Development
```python
# Agents use toolkit pattern for tool encapsulation
class ExtractionAgent:
    def __init__(self):
        self.toolkit = EventExtractionToolkit()
        
    async def extract_events(self, text: str, schema: dict) -> list:
        return await self.toolkit.extract_events_from_text(text, schema)
```

### Workflow Scripts
```python
# Standard workflow pattern
async def run_workflow():
    db_manager = DatabaseManager(config['database']['path'])
    records = db_manager.get_records_by_status_as_df('target_status')
    
    # Process with concurrency control
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = [worker(record, semaphore) for record in records]
    results = await tqdm_asyncio.gather(*tasks)
    
    # Update statuses and trigger next workflow if needed
```

### Database Operations
```python
# Always use DatabaseManager for state updates
db_manager.update_record_after_triage(id, 'pending_extraction', event_type, confidence, notes)
db_manager.update_story_info(event_ids, story_id, 'pending_relationship_analysis')
```

## Critical Configuration

### LLM Routing (`config.yaml`)
- Different models for different tasks (triage, extraction, relationship analysis)
- Provider abstraction (SiliconFlow, OpenAI, etc.) via unified LLMClient
- Temperature and token limits tuned per use case

### Database Setup
- **Neo4j**: Graph relationships, event networks, entity connections
- **ChromaDB**: Vector embeddings for semantic search and context retrieval
- **SQLite**: Central state tracking and workflow coordination

### Performance Considerations
- **Concurrency limits**: Respect API rate limits (typically 3-5 concurrent requests)
- **Async processing**: All workflows use asyncio with proper semaphore control
- **Resumability**: Workflows check existing outputs to avoid reprocessing

## Common Debugging Patterns

### State Inspection
```bash
# Check system status
python check_db_status.py
python check_data_integrity.py

# Debug specific workflows  
python debug_cortex_ids.py
python debug_chromadb_issue.py
```

### Database Recovery
```python
# Common recovery pattern for data issues
python restore_database.py  # Rebuilds from Neo4j
python init_database.py --data-file IC_data/filtered_data.json
```

## Schema Evolution & Learning

The system supports **dynamic schema discovery**:
- Unknown events trigger `run_learning_workflow.py`
- Human-in-the-loop classification and schema generation
- New schemas automatically loaded by TriageAgent on next run
- Supports iterative knowledge graph expansion

## Integration Points

### Frontend Integration
- **WebSocket API** (`src/api/enhanced_api.py`) for real-time workflow monitoring
- **FastAPI endpoints** for status queries and manual workflow triggers
- **React+TypeScript frontend** in `frontend/` directory

### External Dependencies
- **Neo4j** (bolt://localhost:7687): Primary graph database
- **ChromaDB**: Vector storage for semantic operations
- **LLM APIs**: Configurable providers (DeepSeek, OpenAI, etc.)
- **BGE embeddings**: Local model for text vectorization

## Error Handling

- **Database monitoring**: Automatic connection recovery and health checks
- **Graceful degradation**: Individual record failures don't crash workflows
- **Comprehensive logging**: Status updates with error context in master_state.db
- **Circuit breaker patterns**: For API and database connection failures

When contributing, always consider the **event-centric design philosophy** and maintain the **state-driven orchestration** pattern. The system is designed for **high-volume processing** with **human oversight** at key decision points.
