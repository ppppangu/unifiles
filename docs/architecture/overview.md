# System Architecture Overview

This document provides a high-level view of the Unifiles system architecture using Mermaid diagrams.

## High-Level System Architecture

```mermaid
graph TD
    %% External Clients
    Client[Client Applications]
    WebUI[Web UI]
    
    %% API Gateway Layer
    API[FastAPI Gateway v1]
    CORS[CORS Middleware]
    Auth[Auth Middleware]
    FileVal[File Validation Middleware]
    ClientIP[Client IP Middleware]
    
    %% Application Layer
    Routers[API Routers]
    UF[Unifiles Router]
    KB[Knowledge Bases Router]
    PROC[Processors Router]
    MGR[Manager Router]
    
    %% Core Services Layer
    Services[Core Services]
    DocProc[Document Processor]
    EmbedSvc[Embedding Service]
    StorageSvc[Storage Service]
    
    %% Data Layer
    Database[(Database)]
    VectorDB[(Vector Store)]
    FileStorage[(File Storage)]
    ObjectStorage[(Object Storage)]
    
    %% Processing Engines
    OCR[OCR Engine]
    Pipeline[Processing Pipeline]
    
    %% External Dependencies
    EmbedAPI[Embedding API<br/>OpenAI/Local]
    
    %% Client Connections
    Client --> API
    WebUI --> API
    
    %% Middleware Stack
    API --> CORS
    CORS --> Auth
    Auth --> FileVal
    FileVal --> ClientIP
    ClientIP --> Routers
    
    %% Router Distribution
    Routers --> UF
    Routers --> KB
    Routers --> PROC
    Routers --> MGR
    
    %% Service Layer
    UF --> Services
    KB --> Services
    PROC --> Services
    MGR --> Services
    
    Services --> DocProc
    Services --> EmbedSvc
    Services --> StorageSvc
    
    %% Data Persistence
    DocProc --> Database
    EmbedSvc --> VectorDB
    StorageSvc --> FileStorage
    StorageSvc --> ObjectStorage
    
    %% Processing
    DocProc --> OCR
    DocProc --> Pipeline
    EmbedSvc --> EmbedAPI
    
    %% Styling
    classDef client fill:#e1f5fe
    classDef api fill:#f3e5f5
    classDef middleware fill:#fff3e0
    classDef service fill:#e8f5e8
    classDef data fill:#fce4ec
    classDef external fill:#fff8e1
    
    class Client,WebUI client
    class API api
    class CORS,Auth,FileVal,ClientIP middleware
    class Routers,UF,KB,PROC,MGR,Services,DocProc,EmbedSvc,StorageSvc service
    class Database,VectorDB,FileStorage,ObjectStorage data
    class OCR,Pipeline,EmbedAPI external
```

## System Components Overview

### Client Layer
- **Client Applications**: Python client library for programmatic access
- **Web UI**: Browser-based interface for document management

### API Gateway Layer
- **FastAPI Gateway v1**: RESTful API implementation
- **Middleware Stack**: CORS, Authentication, File Validation, Client IP tracking

### Application Layer
- **Unifiles Router**: File upload, management, and basic operations
- **Knowledge Bases Router**: Knowledge base creation and management
- **Processors Router**: Document processing and OCR operations
- **Manager Router**: System management and administrative functions

### Core Services Layer
- **Document Processor**: Handles file processing, OCR, and content extraction
- **Embedding Service**: Manages vector embeddings and similarity search
- **Storage Service**: Abstracts file storage across different backends

### Data Layer
- **Database**: Relational data storage (SQLAlchemy)
- **Vector Store**: Vector embeddings storage for semantic search
- **File Storage**: Local and object storage for files and assets
- **Object Storage**: Cloud-based storage integration

### Processing Layer
- **OCR Engine**: Optical Character Recognition for document text extraction
- **Processing Pipeline**: Modular document processing workflow

### External Dependencies
- **Embedding API**: OpenAI or local embedding model services