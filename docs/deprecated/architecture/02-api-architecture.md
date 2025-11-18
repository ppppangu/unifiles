# API Architecture

This document details the FastAPI application structure and request/response flow.

## FastAPI Application Structure

```mermaid
graph TD
    %% Application Entry Point
    APP[FastAPI App Instance]
    LIFESPAN[Lifespan Manager]
    
    %% Middleware Stack (Order Matters)
    CORS[CORS Middleware]
    CLIENTIP[Client IP Middleware]
    AUTH[Auth Middleware]
    FILEVAL[File Validation Middleware]
    
    %% Router Layer
    ROUTERS[Router Collection]
    
    %% Individual Routers
    UF_ROUTER[Unifiles Router<br/>/unifiles]
    KB_ROUTER[Knowledge Bases Router<br/>/knowledge-bases]
    PROC_ROUTER[Processors Router<br/>/processors]
    MGR_ROUTER[Manager Router<br/>/manager]
    
    %% Health Check
    HEALTH[Health Check<br/>/health]
    
    %% Request Flow
    REQUEST[Incoming Request]
    RESPONSE[Response]
    
    %% Application Setup
    APP --> LIFESPAN
    LIFESPAN --> CORS
    
    %% Middleware Chain
    REQUEST --> CORS
    CORS --> CLIENTIP
    CLIENTIP --> AUTH
    AUTH --> FILEVAL
    FILEVAL --> ROUTERS
    
    %% Router Distribution
    ROUTERS --> UF_ROUTER
    ROUTERS --> KB_ROUTER
    ROUTERS --> PROC_ROUTER
    ROUTERS --> MGR_ROUTER
    ROUTERS --> HEALTH
    
    %% Response Path
    UF_ROUTER --> RESPONSE
    KB_ROUTER --> RESPONSE
    PROC_ROUTER --> RESPONSE
    MGR_ROUTER --> RESPONSE
    HEALTH --> RESPONSE
    
    %% Styling
    classDef app fill:#e3f2fd
    classDef middleware fill:#fff3e0
    classDef router fill:#e8f5e8
    classDef flow fill:#f3e5f5
    
    class APP,LIFESPAN app
    class CORS,CLIENTIP,AUTH,FILEVAL middleware
    class ROUTERS,UF_ROUTER,KB_ROUTER,PROC_ROUTER,MGR_ROUTER,HEALTH router
    class REQUEST,RESPONSE flow
```

## Request/Response Flow

```mermaid
sequenceDiagram
    participant Client
    participant CORS as CORS Middleware
    participant ClientIP as Client IP Middleware
    participant Auth as Auth Middleware
    participant FileVal as File Validation Middleware
    participant Router as API Router
    participant Service as Core Service
    participant DB as Database
    
    Client->>+CORS: HTTP Request
    Note over CORS: Add CORS headers<br/>Validate origin
    
    CORS->>+ClientIP: Request + CORS
    Note over ClientIP: Extract client IP<br/>Add to request context
    
    ClientIP->>+Auth: Request + Client Info
    Note over Auth: Validate API key<br/>Check permissions
    
    Auth->>+FileVal: Authenticated Request
    Note over FileVal: Validate file types<br/>Check file size limits
    
    FileVal->>+Router: Validated Request
    Note over Router: Route to endpoint<br/>Parse parameters
    
    Router->>+Service: Business Logic Call
    Note over Service: Process request<br/>Apply business rules
    
    Service->>+DB: Data Operation
    DB-->>-Service: Data Response
    
    Service-->>-Router: Service Response
    Router-->>-FileVal: API Response
    FileVal-->>-Auth: Response
    Auth-->>-ClientIP: Response
    ClientIP-->>-CORS: Response
    CORS-->>-Client: HTTP Response with CORS headers
```

## API Endpoint Structure

```mermaid
graph LR
    %% Base API
    API["/api/v1"]
    
    %% Unifiles Endpoints
    UF["/unifiles"]
    UF_UPLOAD["/upload"]
    UF_STATUS["/status/{file_id}"]
    UF_DOWNLOAD["/download/{file_id}"]
    UF_DELETE["/delete/{file_id}"]
    UF_LIST["/list"]
    
    %% Knowledge Base Endpoints
    KB["/knowledge-bases"]
    KB_CREATE["/create"]
    KB_LIST["/list"]
    KB_GET["/get/{kb_id}"]
    KB_UPDATE["/update/{kb_id}"]
    KB_DELETE["/delete/{kb_id}"]
    KB_DOCS["/docs/{kb_id}"]
    KB_SEARCH["/search/{kb_id}"]
    
    %% Processor Endpoints
    PROC["/processors"]
    PROC_OCR["/ocr"]
    PROC_STATUS["/status/{task_id}"]
    PROC_RESULT["/result/{task_id}"]
    
    %% Manager Endpoints
    MGR["/manager"]
    MGR_STATS["/stats"]
    MGR_HEALTH["/health"]
    MGR_CONFIG["/config"]
    
    %% System Endpoints
    HEALTH["/health"]
    DOCS["/docs"]
    REDOC["/redoc"]
    
    %% Connections
    API --> UF
    API --> KB
    API --> PROC
    API --> MGR
    API --> HEALTH
    API --> DOCS
    API --> REDOC
    
    UF --> UF_UPLOAD
    UF --> UF_STATUS
    UF --> UF_DOWNLOAD
    UF --> UF_DELETE
    UF --> UF_LIST
    
    KB --> KB_CREATE
    KB --> KB_LIST
    KB --> KB_GET
    KB --> KB_UPDATE
    KB --> KB_DELETE
    KB --> KB_DOCS
    KB --> KB_SEARCH
    
    PROC --> PROC_OCR
    PROC --> PROC_STATUS
    PROC --> PROC_RESULT
    
    MGR --> MGR_STATS
    MGR --> MGR_HEALTH
    MGR --> MGR_CONFIG
    
    %% Styling
    classDef base fill:#e3f2fd
    classDef group fill:#e8f5e8
    classDef endpoint fill:#fff3e0
    
    class API base
    class UF,KB,PROC,MGR,HEALTH,DOCS,REDOC group
    class UF_UPLOAD,UF_STATUS,UF_DOWNLOAD,UF_DELETE,UF_LIST,KB_CREATE,KB_LIST,KB_GET,KB_UPDATE,KB_DELETE,KB_DOCS,KB_SEARCH,PROC_OCR,PROC_STATUS,PROC_RESULT,MGR_STATS,MGR_HEALTH,MGR_CONFIG endpoint
```

## Middleware Processing Order

```mermaid
graph TD
    %% Request Processing Order
    REQUEST[Incoming Request]
    
    %% Middleware Stack (Top to Bottom)
    MW1[1. CORS Middleware<br/>- Add CORS headers<br/>- Validate origins<br/>- Handle preflight]
    MW2[2. Client IP Middleware<br/>- Extract client IP<br/>- Add to request state<br/>- Geographic tracking]
    MW3[3. Auth Middleware<br/>- Validate API keys<br/>- Check permissions<br/>- User identification]
    MW4[4. File Validation Middleware<br/>- Validate file types<br/>- Check size limits<br/>- Security scanning]
    
    %% Router Processing
    ROUTER[Router Processing<br/>- Path matching<br/>- Parameter extraction<br/>- Endpoint routing]
    
    %% Response Processing Order (Bottom to Top)
    RESPONSE[Response Generation]
    
    %% Request Flow
    REQUEST --> MW1
    MW1 --> MW2
    MW2 --> MW3
    MW3 --> MW4
    MW4 --> ROUTER
    
    %% Response Flow (Reverse Order)
    ROUTER --> RESPONSE
    
    %% Error Handling
    ERROR[Error Handling]
    MW1 -.-> ERROR
    MW2 -.-> ERROR
    MW3 -.-> ERROR
    MW4 -.-> ERROR
    ROUTER -.-> ERROR
    
    %% Styling
    classDef middleware fill:#fff3e0
    classDef process fill:#e8f5e8
    classDef error fill:#ffebee
    
    class MW1,MW2,MW3,MW4 middleware
    class REQUEST,ROUTER,RESPONSE process
    class ERROR error
```

## Response Schema Structure

```mermaid
classDiagram
    class StandardResponse {
        +bool success
        +string message
        +Any data
        +dict metadata
        +int timestamp
    }
    
    class ErrorResponse {
        +bool success = false
        +string message
        +string error_code
        +dict error_details
        +int timestamp
    }
    
    class FileUploadResponse {
        +bool success
        +string message
        +FileModel data
        +dict processing_info
    }
    
    class KnowledgeBaseResponse {
        +bool success
        +string message
        +KnowledgeBaseModel data
        +dict statistics
    }
    
    class SearchResponse {
        +bool success
        +string message
        +list~SearchResult~ data
        +dict search_metadata
    }
    
    StandardResponse <|-- ErrorResponse
    StandardResponse <|-- FileUploadResponse
    StandardResponse <|-- KnowledgeBaseResponse
    StandardResponse <|-- SearchResponse
```