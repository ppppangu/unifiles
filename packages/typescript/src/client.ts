import {
  APIKeysResource,
  ExtractionsResource,
  FilesResource,
  KnowledgeBasesResource,
  UsageResource,
  WebhooksResource,
} from "./resources.js";
import { Transport, type TransportOptions } from "./transport.js";

export interface UnifilesClientOptions extends TransportOptions {}

export class UnifilesClient {
  readonly files: FilesResource;
  readonly extractions: ExtractionsResource;
  readonly knowledgeBases: KnowledgeBasesResource;
  readonly webhooks: WebhooksResource;
  readonly apiKeys: APIKeysResource;
  readonly usage: UsageResource;
  readonly baseUrl: string;

  constructor(options: UnifilesClientOptions = {}) {
    const transport = new Transport(options);
    this.baseUrl = transport.baseUrl;
    this.files = new FilesResource(transport);
    this.extractions = new ExtractionsResource(transport);
    this.knowledgeBases = new KnowledgeBasesResource(transport);
    this.webhooks = new WebhooksResource(transport);
    this.apiKeys = new APIKeysResource(transport);
    this.usage = new UsageResource(transport);
  }
}
