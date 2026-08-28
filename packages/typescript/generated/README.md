# @wyy/unifiles-generated@0.1.0

A TypeScript SDK client for the api.unifiles.dev API.

## Usage

First, install the SDK from npm.

```bash
npm install @wyy/unifiles-generated --save
```

Next, try it out.


```ts
import {
  Configuration,
  APIKeysApi,
} from '@wyy/unifiles-generated';
import type { CreateApiKeyRequest } from '@wyy/unifiles-generated';

async function example() {
  console.log("🚀 Testing @wyy/unifiles-generated SDK...");
  const config = new Configuration({ 
    // Configure HTTP bearer authorization: BearerAuth
    accessToken: "YOUR BEARER TOKEN",
  });
  const api = new APIKeysApi(config);

  const body = {
    // APIKeyCreate
    apiKeyCreate: ...,
    // string (optional)
    idempotencyKey: idempotencyKey_example,
  } satisfies CreateApiKeyRequest;

  try {
    const data = await api.createApiKey(body);
    console.log(data);
  } catch (error) {
    console.error(error);
  }
}

// Run the test
example().catch(console.error);
```


## Documentation

### API Endpoints

All URIs are relative to *https://api.unifiles.dev*

| Class | Method | HTTP request | Description
| ----- | ------ | ------------ | -------------
*APIKeysApi* | [**createApiKey**](docs/APIKeysApi.md#createapikey) | **POST** /v1/api-keys | Create Api Key
*APIKeysApi* | [**listApiKeys**](docs/APIKeysApi.md#listapikeys) | **GET** /v1/api-keys | List Api Keys
*APIKeysApi* | [**revokeApiKey**](docs/APIKeysApi.md#revokeapikey) | **DELETE** /v1/api-keys/{key_id} | Revoke Api Key
*DocumentsApi* | [**createDocument**](docs/DocumentsApi.md#createdocument) | **POST** /v1/knowledge-bases/{kb_id}/documents | Create Document
*DocumentsApi* | [**deleteDocument**](docs/DocumentsApi.md#deletedocument) | **DELETE** /v1/knowledge-bases/{kb_id}/documents/{document_id} | Delete Document
*DocumentsApi* | [**getDocument**](docs/DocumentsApi.md#getdocument) | **GET** /v1/knowledge-bases/{kb_id}/documents/{document_id} | Get Document
*DocumentsApi* | [**listDocuments**](docs/DocumentsApi.md#listdocuments) | **GET** /v1/knowledge-bases/{kb_id}/documents | List Documents
*ExtractionsApi* | [**createExtraction**](docs/ExtractionsApi.md#createextraction) | **POST** /v1/extractions | Create Extraction
*ExtractionsApi* | [**getExtraction**](docs/ExtractionsApi.md#getextraction) | **GET** /v1/extractions/{extraction_id} | Get Extraction
*ExtractionsApi* | [**listFileExtractions**](docs/ExtractionsApi.md#listfileextractions) | **GET** /v1/files/{file_id}/extractions | File Extractions
*FilesApi* | [**deleteFile**](docs/FilesApi.md#deletefile) | **DELETE** /v1/files/{file_id} | Delete File
*FilesApi* | [**downloadFile**](docs/FilesApi.md#downloadfile) | **GET** /v1/files/{file_id}/download | Download File
*FilesApi* | [**getFile**](docs/FilesApi.md#getfile) | **GET** /v1/files/{file_id} | Get File
*FilesApi* | [**listFiles**](docs/FilesApi.md#listfiles) | **GET** /v1/files | List Files
*FilesApi* | [**listSupportedFileTypes**](docs/FilesApi.md#listsupportedfiletypes) | **GET** /v1/files/types | Supported Types
*FilesApi* | [**uploadFile**](docs/FilesApi.md#uploadfile) | **POST** /v1/files | Upload File
*KnowledgeBasesApi* | [**createKnowledgeBase**](docs/KnowledgeBasesApi.md#createknowledgebase) | **POST** /v1/knowledge-bases | Create Knowledge Base
*KnowledgeBasesApi* | [**deleteKnowledgeBase**](docs/KnowledgeBasesApi.md#deleteknowledgebase) | **DELETE** /v1/knowledge-bases/{kb_id} | Delete Knowledge Base
*KnowledgeBasesApi* | [**getKnowledgeBase**](docs/KnowledgeBasesApi.md#getknowledgebase) | **GET** /v1/knowledge-bases/{kb_id} | Get Knowledge Base
*KnowledgeBasesApi* | [**listKnowledgeBases**](docs/KnowledgeBasesApi.md#listknowledgebases) | **GET** /v1/knowledge-bases | List Knowledge Bases
*KnowledgeBasesApi* | [**updateKnowledgeBase**](docs/KnowledgeBasesApi.md#updateknowledgebase) | **PATCH** /v1/knowledge-bases/{kb_id} | Update Knowledge Base
*SearchApi* | [**hybridSearchKnowledgeBase**](docs/SearchApi.md#hybridsearchknowledgebase) | **POST** /v1/knowledge-bases/{kb_id}/hybrid-search | Hybrid Search
*SearchApi* | [**searchKnowledgeBase**](docs/SearchApi.md#searchknowledgebase) | **POST** /v1/knowledge-bases/{kb_id}/search | Semantic Search
*SystemApi* | [**getHealth**](docs/SystemApi.md#gethealth) | **GET** /health | Health
*SystemApi* | [**getHealthDetails**](docs/SystemApi.md#gethealthdetails) | **GET** /v1/health/details | Detailed Health
*SystemApi* | [**getVersionedHealth**](docs/SystemApi.md#getversionedhealth) | **GET** /v1/health | Health
*UsageApi* | [**getUsageLimits**](docs/UsageApi.md#getusagelimits) | **GET** /v1/usage/limits | Usage Limits
*UsageApi* | [**getUsageStats**](docs/UsageApi.md#getusagestats) | **GET** /v1/usage/stats | Usage Stats
*WebhooksApi* | [**createWebhook**](docs/WebhooksApi.md#createwebhook) | **POST** /v1/webhooks | Create Webhook
*WebhooksApi* | [**deleteWebhook**](docs/WebhooksApi.md#deletewebhook) | **DELETE** /v1/webhooks/{webhook_id} | Delete Webhook
*WebhooksApi* | [**getWebhook**](docs/WebhooksApi.md#getwebhook) | **GET** /v1/webhooks/{webhook_id} | Get Webhook
*WebhooksApi* | [**listWebhooks**](docs/WebhooksApi.md#listwebhooks) | **GET** /v1/webhooks | List Webhooks
*WebhooksApi* | [**updateWebhook**](docs/WebhooksApi.md#updatewebhook) | **PATCH** /v1/webhooks/{webhook_id} | Update Webhook


### Models

- [APIKeyCreate](docs/APIKeyCreate.md)
- [APIKeyList](docs/APIKeyList.md)
- [APIKeyListResponse](docs/APIKeyListResponse.md)
- [APIKeyResource](docs/APIKeyResource.md)
- [APIKeyResponse](docs/APIKeyResponse.md)
- [ApiCallLimits](docs/ApiCallLimits.md)
- [ChunkResource](docs/ChunkResource.md)
- [ChunkingStrategy](docs/ChunkingStrategy.md)
- [DeletionResponse](docs/DeletionResponse.md)
- [DeletionResult](docs/DeletionResult.md)
- [DocumentCreate](docs/DocumentCreate.md)
- [DocumentList](docs/DocumentList.md)
- [DocumentListResponse](docs/DocumentListResponse.md)
- [DocumentResource](docs/DocumentResource.md)
- [DocumentResponse](docs/DocumentResponse.md)
- [ErrorDetail](docs/ErrorDetail.md)
- [ErrorEnvelope](docs/ErrorEnvelope.md)
- [ExtractionCreate](docs/ExtractionCreate.md)
- [ExtractionList](docs/ExtractionList.md)
- [ExtractionListResponse](docs/ExtractionListResponse.md)
- [ExtractionOptions](docs/ExtractionOptions.md)
- [ExtractionResource](docs/ExtractionResource.md)
- [ExtractionResponse](docs/ExtractionResponse.md)
- [ExtractionUsage](docs/ExtractionUsage.md)
- [FileLimits](docs/FileLimits.md)
- [FileList](docs/FileList.md)
- [FileListResponse](docs/FileListResponse.md)
- [FileResource](docs/FileResource.md)
- [FileResponse](docs/FileResponse.md)
- [HealthDetails](docs/HealthDetails.md)
- [HealthDetailsResponse](docs/HealthDetailsResponse.md)
- [HealthResponse](docs/HealthResponse.md)
- [HealthStatus](docs/HealthStatus.md)
- [HybridSearchRequest](docs/HybridSearchRequest.md)
- [KnowledgeBaseCreate](docs/KnowledgeBaseCreate.md)
- [KnowledgeBaseList](docs/KnowledgeBaseList.md)
- [KnowledgeBaseListResponse](docs/KnowledgeBaseListResponse.md)
- [KnowledgeBaseResource](docs/KnowledgeBaseResource.md)
- [KnowledgeBaseResponse](docs/KnowledgeBaseResponse.md)
- [KnowledgeBaseUpdate](docs/KnowledgeBaseUpdate.md)
- [KnowledgeBaseUsage](docs/KnowledgeBaseUsage.md)
- [SearchRequest](docs/SearchRequest.md)
- [SearchResponse](docs/SearchResponse.md)
- [SearchResults](docs/SearchResults.md)
- [StorageLimits](docs/StorageLimits.md)
- [StorageUsage](docs/StorageUsage.md)
- [SupportedFileTypes](docs/SupportedFileTypes.md)
- [SupportedFileTypesResponse](docs/SupportedFileTypesResponse.md)
- [UsageLimits](docs/UsageLimits.md)
- [UsageLimitsResponse](docs/UsageLimitsResponse.md)
- [UsageStats](docs/UsageStats.md)
- [UsageStatsResponse](docs/UsageStatsResponse.md)
- [WebhookCreate](docs/WebhookCreate.md)
- [WebhookList](docs/WebhookList.md)
- [WebhookListResponse](docs/WebhookListResponse.md)
- [WebhookResource](docs/WebhookResource.md)
- [WebhookResponse](docs/WebhookResponse.md)
- [WebhookUpdate](docs/WebhookUpdate.md)

### Authorization


Authentication schemes defined for the API:
<a id="BearerAuth"></a>
#### BearerAuth


- **Type**: HTTP Bearer Token authentication

## About

This TypeScript SDK client supports the [Fetch API](https://fetch.spec.whatwg.org/)
and is automatically generated by the
[OpenAPI Generator](https://openapi-generator.tech) project:

- API version: `1.0.0`
- Package version: `0.1.0`
- Generator version: `7.24.0`
- Build package: `org.openapitools.codegen.languages.TypeScriptFetchClientCodegen`

The generated npm module supports the following:

- Environments
  * Node.js
  * Webpack
  * Browserify
- Language levels
  * ES5 - you must have a Promises/A+ library installed
  * ES6
- Module systems
  * CommonJS
  * ES6 module system


## Development

### Building

To build the TypeScript source code, you need to have Node.js and npm installed.
After cloning the repository, navigate to the project directory and run:

```bash
npm install
npm run build
```

### Publishing

Once you've built the package, you can publish it to npm:

```bash
npm publish
```

## License

[]()
