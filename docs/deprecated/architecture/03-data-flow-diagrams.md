# Data Flow Diagrams

This document illustrates the data flow patterns within the Unifiles system.

## File Upload and Processing Pipeline

```mermaid
flowchart TD
    %% User Input
    USER[User Upload Request]
    
    %% API Layer
    API[FastAPI Endpoint]
    VALIDATE[File Validation]
    
    %% Storage Layer
    STORAGE[Storage Service]
    LOCAL[Local Storage]
    OBJECT[Object Storage]
    
    %% Processing Pipeline
    QUEUE[Processing Queue]
    OCR[OCR Engine]
    EXTRACT[Content Extraction]
    STRUCTURE[Document Structure Analysis]
    
    %% Database Operations
    DB_FILE[File Record Creation]
    DB_DOC[Document Record Creation]
    DB_LOG[Processing Log]
    
    %% Post-Processing
    EMBED[Embedding Generation]
    VECTOR[Vector Storage]
    INDEX[Search Index Update]
    
    %% User Notification
    NOTIFY[Processing Complete Notification]
    
    %% Flow
    USER --> API
    API --> VALIDATE
    VALIDATE --> STORAGE
    
    STORAGE --> LOCAL
    STORAGE --> OBJECT
    STORAGE --> DB_FILE
    
    DB_FILE --> QUEUE
    QUEUE --> OCR
    OCR --> EXTRACT
    EXTRACT --> STRUCTURE
    
    STRUCTURE --> DB_DOC
    DB_DOC --> DB_LOG
    
    STRUCTURE --> EMBED
    EMBED --> VECTOR
    VECTOR --> INDEX
    
    INDEX --> NOTIFY
    
    %% Error Handling
    VALIDATE -.-> ERROR[Error Response]
    OCR -.-> ERROR
    EXTRACT -.-> ERROR
    EMBED -.-> ERROR
    
    %% Styling
    classDef input fill:#e3f2fd
    classDef process fill:#e8f5e8
    classDef storage fill:#fff3e0
    classDef database fill:#fce4ec
    classDef error fill:#ffebee
    
    class USER,API input
    class VALIDATE,QUEUE,OCR,EXTRACT,STRUCTURE,EMBED process
    class STORAGE,LOCAL,OBJECT,VECTOR,INDEX storage
    class DB_FILE,DB_DOC,DB_LOG database
    class ERROR error
```

## Embedding Generation Workflow

```mermaid
sequenceDiagram
    participant Client
    participant API as API Gateway
    participant DocProc as Document Processor
    participant ChunkSvc as Chunking Service
    participant EmbedSvc as Embedding Service
    participant VectorDB as Vector Database
    participant Cache as Embedding Cache
    
    Client->>+API: POST /knowledge-bases/{kb_id}/documents
    API->>+DocProc: Process Document Request
    
    DocProc->>+ChunkSvc: Generate Text Chunks
    Note over ChunkSvc: Split document using<br/>hierarchical strategy
    ChunkSvc-->>-DocProc: Text Chunks[]
    
    loop For each chunk
        DocProc->>+EmbedSvc: Generate Embedding
        EmbedSvc->>+Cache: Check Cache
        
        alt Cache Hit
            Cache-->>EmbedSvc: Cached Embedding
        else Cache Miss
            EmbedSvc->>EmbedAPI: External API Call
            EmbedAPI-->>EmbedSvc: Embedding Vector
            EmbedSvc->>Cache: Store in Cache
        end
        
        EmbedSvc-->>-DocProc: Embedding Vector
        DocProc->>+VectorDB: Store Chunk + Embedding
        VectorDB-->>-DocProc: Storage Confirmation
    end
    
    DocProc-->>-API: Processing Complete
    API-->>-Client: Success Response
```

## Knowledge Base Search Flow

```mermaid
flowchart TD
    %% Search Input
    QUERY[User Search Query]
    
    %% Query Processing
    PREPROCESS[Query Preprocessing]
    EMBED_QUERY[Query Embedding]
    
    %% Search Strategies
    SEMANTIC[Semantic Search]
    KEYWORD[Keyword Search]
    HYBRID[Hybrid Search]
    
    %% Vector Operations
    VECTOR_SEARCH[Vector Similarity Search]
    FILTER[Apply Filters]
    
    %% Result Processing
    RETRIEVE[Retrieve Chunks]
    RANK[Ranking & Scoring]
    RERANK[Re-ranking]
    
    %% Response Generation
    FORMAT[Format Results]
    METADATA[Add Metadata]
    RESPONSE[Search Response]
    
    %% Analytics
    LOG_SEARCH[Log Search Analytics]
    UPDATE_STATS[Update Statistics]
    
    %% Flow
    QUERY --> PREPROCESS
    PREPROCESS --> EMBED_QUERY
    
    EMBED_QUERY --> SEMANTIC
    PREPROCESS --> KEYWORD
    
    SEMANTIC --> VECTOR_SEARCH
    KEYWORD --> VECTOR_SEARCH
    SEMANTIC --> HYBRID
    KEYWORD --> HYBRID
    HYBRID --> VECTOR_SEARCH
    
    VECTOR_SEARCH --> FILTER
    FILTER --> RETRIEVE
    RETRIEVE --> RANK
    RANK --> RERANK
    
    RERANK --> FORMAT
    FORMAT --> METADATA
    METADATA --> RESPONSE
    
    %% Analytics Flow
    RESPONSE --> LOG_SEARCH
    LOG_SEARCH --> UPDATE_STATS
    
    %% Styling
    classDef input fill:#e3f2fd
    classDef process fill:#e8f5e8
    classDef search fill:#fff3e0
    classDef output fill:#f3e5f5
    classDef analytics fill:#e1f5fe
    
    class QUERY,PREPROCESS input
    class EMBED_QUERY,FILTER,RETRIEVE,RANK,RERANK,FORMAT,METADATA process
    class SEMANTIC,KEYWORD,HYBRID,VECTOR_SEARCH search
    class RESPONSE output
    class LOG_SEARCH,UPDATE_STATS analytics
```

## Database Read/Write Operations

```mermaid
flowchart LR
    %% Application Layer
    APP[Application Layer]
    
    %% Service Layer
    DOC_SVC[Document Service]
    EMBED_SVC[Embedding Service]
    STORAGE_SVC[Storage Service]
    
    %% Database Manager
    DB_MGR[Database Manager]
    
    %% Database Operations
    READ_OPS[Read Operations]
    WRITE_OPS[Write Operations]
    BATCH_OPS[Batch Operations]
    
    %% Data Stores
    POSTGRES[(PostgreSQL<br/>Metadata)]
    VECTOR[(Vector Database<br/>Embeddings)]
    FILES[(File Storage<br/>Binary Data)]
    CACHE[(Redis Cache<br/>Session Data)]
    
    %% Read Patterns
    GET_FILE[Get File Info]
    LIST_DOCS[List Documents]
    SEARCH_VEC[Vector Search]
    GET_STATS[Get Statistics]
    
    %% Write Patterns
    CREATE_FILE[Create File Record]
    UPDATE_STATUS[Update Processing Status]
    STORE_EMBED[Store Embeddings]
    LOG_EVENT[Log Events]
    
    %% Connections
    APP --> DOC_SVC
    APP --> EMBED_SVC
    APP --> STORAGE_SVC
    
    DOC_SVC --> DB_MGR
    EMBED_SVC --> DB_MGR
    STORAGE_SVC --> DB_MGR
    
    DB_MGR --> READ_OPS
    DB_MGR --> WRITE_OPS
    DB_MGR --> BATCH_OPS
    
    READ_OPS --> GET_FILE
    READ_OPS --> LIST_DOCS
    READ_OPS --> SEARCH_VEC
    READ_OPS --> GET_STATS
    
    WRITE_OPS --> CREATE_FILE
    WRITE_OPS --> UPDATE_STATUS
    WRITE_OPS --> STORE_EMBED
    WRITE_OPS --> LOG_EVENT
    
    GET_FILE --> POSTGRES
    LIST_DOCS --> POSTGRES
    SEARCH_VEC --> VECTOR
    GET_STATS --> CACHE
    
    CREATE_FILE --> POSTGRES
    UPDATE_STATUS --> POSTGRES
    STORE_EMBED --> VECTOR
    LOG_EVENT --> POSTGRES
    
    STORAGE_SVC --> FILES
    
    %% Styling
    classDef service fill:#e8f5e8
    classDef database fill:#fce4ec
    classDef operation fill:#fff3e0
    classDef pattern fill:#f3e5f5
    
    class APP,DOC_SVC,EMBED_SVC,STORAGE_SVC service
    class POSTGRES,VECTOR,FILES,CACHE database
    class DB_MGR,READ_OPS,WRITE_OPS,BATCH_OPS operation
    class GET_FILE,LIST_DOCS,SEARCH_VEC,GET_STATS,CREATE_FILE,UPDATE_STATUS,STORE_EMBED,LOG_EVENT pattern
```

## Storage Service Interactions

```mermaid
stateDiagram-v2
    [*] --> FileReceived
    
    FileReceived --> ValidatingFile : File upload initiated
    ValidatingFile --> StorageDecision : Validation complete
    
    StorageDecision --> LocalStorage : Small files or dev environment
    StorageDecision --> ObjectStorage : Large files or production
    
    LocalStorage --> FileStored : Store in local filesystem
    ObjectStorage --> FileStored : Store in cloud storage
    
    FileStored --> DatabaseRecord : Create file metadata record
    DatabaseRecord --> ProcessingQueue : Add to processing queue
    
    ProcessingQueue --> OCRProcessing : Extract text content
    OCRProcessing --> ContentExtracted : OCR complete
    
    ContentExtracted --> ChunkGeneration : Split into chunks
    ChunkGeneration --> EmbeddingGeneration : Generate embeddings
    
    EmbeddingGeneration --> VectorStorage : Store in vector database
    VectorStorage --> IndexUpdate : Update search index
    
    IndexUpdate --> ProcessingComplete : File ready for search
    ProcessingComplete --> [*]
    
    ValidatingFile --> ValidationFailed : File validation error
    OCRProcessing --> ProcessingFailed : OCR error
    EmbeddingGeneration --> ProcessingFailed : Embedding error
    
    ValidationFailed --> [*]
    ProcessingFailed --> [*]
```

## Component Data Flow

```mermaid
graph TD
    %% Input Documents
    PDF[PDF Document]
    DOCX[Word Document]
    TXT[Text File]
    IMG[Image File]
    
    %% Processing Layer
    UPLOAD[Upload Handler]
    VALIDATE[File Validator]
    
    %% Content Extraction
    OCR_PDF[PDF OCR Engine]
    OCR_IMG[Image OCR Engine]
    DOCX_PARSER[DOCX Parser]
    TXT_READER[Text Reader]
    
    %% Content Processing
    MARKDOWN[Markdown Generator]
    CHUNKER[Text Chunker]
    
    %% Knowledge Base Integration
    KB_PROCESSOR[KB Document Processor]
    EMBEDDER[Embedding Generator]
    
    %% Storage
    FILE_DB[(File Database)]
    DOC_DB[(Document Database)]
    VECTOR_DB[(Vector Database)]
    ASSET_STORAGE[(Asset Storage)]
    
    %% Search and Retrieval
    SEARCH_ENGINE[Search Engine]
    RESULT_FORMATTER[Result Formatter]
    
    %% Flow Connections
    PDF --> UPLOAD
    DOCX --> UPLOAD
    TXT --> UPLOAD
    IMG --> UPLOAD
    
    UPLOAD --> VALIDATE
    
    VALIDATE --> OCR_PDF
    VALIDATE --> OCR_IMG
    VALIDATE --> DOCX_PARSER
    VALIDATE --> TXT_READER
    
    OCR_PDF --> MARKDOWN
    OCR_IMG --> MARKDOWN
    DOCX_PARSER --> MARKDOWN
    TXT_READER --> MARKDOWN
    
    MARKDOWN --> CHUNKER
    CHUNKER --> KB_PROCESSOR
    
    KB_PROCESSOR --> EMBEDDER
    KB_PROCESSOR --> DOC_DB
    
    EMBEDDER --> VECTOR_DB
    
    VALIDATE --> FILE_DB
    MARKDOWN --> ASSET_STORAGE
    
    VECTOR_DB --> SEARCH_ENGINE
    DOC_DB --> SEARCH_ENGINE
    SEARCH_ENGINE --> RESULT_FORMATTER
    
    %% Styling
    classDef input fill:#e3f2fd
    classDef process fill:#e8f5e8
    classDef storage fill:#fce4ec
    classDef output fill:#f3e5f5
    
    class PDF,DOCX,TXT,IMG input
    class UPLOAD,VALIDATE,OCR_PDF,OCR_IMG,DOCX_PARSER,TXT_READER,MARKDOWN,CHUNKER,KB_PROCESSOR,EMBEDDER,SEARCH_ENGINE process
    class FILE_DB,DOC_DB,VECTOR_DB,ASSET_STORAGE storage
    class RESULT_FORMATTER output
```