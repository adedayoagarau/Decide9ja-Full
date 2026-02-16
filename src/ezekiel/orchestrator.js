/**
 * Ezekiel - Unified Data Ingestion Orchestrator
 * Coordinates async agents for parsing, chunking, embedding, and ingesting
 */

const Queue = require('bull');
const { createClient } = require('@supabase/supabase-js');
const { OpenAI } = require('openai');
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');
const { pipeline } = require('@xenova/transformers');

// Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  supabaseUrl: process.env.SUPABASE_URL,
  supabaseKey: process.env.SUPABASE_SERVICE_KEY,
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
  openaiApiKey: process.env.OPENAI_API_KEY,
  
  // Processing settings
  batchSize: 50,
  chunkSize: 512,
  chunkOverlap: 128,
  maxRetries: 3,
  
  // Queue settings
  queues: {
    parse: { name: 'parse', concurrency: 3 },
    chunk: { name: 'chunk', concurrency: 2 },
    embed: { name: 'embed', concurrency: 4 },
    entity: { name: 'entity', concurrency: 2 },
    ingest: { name: 'ingest', concurrency: 2 }
  }
};

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join(CONFIG.projectDir, 'logs/ezekiel-error.log'), level: 'error' }),
    new winston.transports.File({ filename: path.join(CONFIG.projectDir, 'logs/ezekiel.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

// Initialize clients
let supabase, openai, embeddingModel;

async function initializeClients() {
  // Supabase
  supabase = createClient(CONFIG.supabaseUrl, CONFIG.supabaseKey);
  
  // OpenAI (for embeddings fallback)
  if (CONFIG.openaiApiKey) {
    openai = new OpenAI({ apiKey: CONFIG.openaiApiKey });
  }
  
  // Local embedding model (primary)
  logger.info('Loading embedding model...');
  embeddingModel = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
  logger.info('Embedding model loaded');
}

// ==================== QUEUE DEFINITIONS ====================

const queues = {
  parse: new Queue('parse', CONFIG.redisUrl),
  chunk: new Queue('chunk', CONFIG.redisUrl),
  embed: new Queue('embed', CONFIG.redisUrl),
  entity: new Queue('entity', CONFIG.redisUrl),
  ingest: new Queue('ingest', CONFIG.redisUrl)
};

// ==================== PARSER AGENT ====================

class ParserAgent {
  async parseJudasOutput(filePath) {
    try {
      const data = JSON.parse(await fs.readFile(filePath, 'utf8'));
      
      return {
        source_type: 'newspaper',
        source_id: this.generateSourceId(data),
        title: data.issues?.[0]?.headline || 'Untitled',
        content: this.extractFullContent(data),
        published_date: data.date,
        source_metadata: {
          newspaper: data.newspaper,
          issue_count: data.issueCount,
          file_path: filePath
        },
        raw_data: data
      };
    } catch (error) {
      logger.error(`Parse error for ${filePath}:`, error);
      throw error;
    }
  }
  
  generateSourceId(data) {
    const newspaper = (data.newspaper || 'unknown').toLowerCase().replace(/\s+/g, '_');
    const date = data.date || 'unknown';
    return `judas_${newspaper}_${date}`;
  }
  
  extractFullContent(data) {
    if (!data.issues || !Array.isArray(data.issues)) return '';
    
    return data.issues.map(issue => {
      const parts = [];
      if (issue.headline) parts.push(`HEADLINE: ${issue.headline}`);
      if (issue.snippet) parts.push(`SNIPPET: ${issue.snippet}`);
      if (issue.fullText) parts.push(`CONTENT: ${issue.fullText}`);
      else if (issue.content) parts.push(`CONTENT: ${issue.content}`);
      if (issue.ocrText) parts.push(`OCR: ${issue.ocrText}`);
      return parts.join('\n\n');
    }).join('\n\n---\n\n');
  }
}

// ==================== CHUNKER AGENT ====================

class ChunkerAgent {
  async chunkDocument(document) {
    const content = document.content;
    const chunks = [];
    
    // Simple token-based chunking (improve with proper tokenizer)
    const words = content.split(/\s+/);
    let currentChunk = [];
    let position = 0;
    
    for (let i = 0; i < words.length; i++) {
      currentChunk.push(words[i]);
      
      if (currentChunk.length >= CONFIG.chunkSize) {
        chunks.push({
          content: currentChunk.join(' '),
          position: position++,
          token_count: currentChunk.length
        });
        
        // Keep overlap
        currentChunk = currentChunk.slice(-CONFIG.chunkOverlap);
      }
    }
    
    // Add final chunk
    if (currentChunk.length > CONFIG.chunkOverlap) {
      chunks.push({
        content: currentChunk.join(' '),
        position: position,
        token_count: currentChunk.length
      });
    }
    
    return { ...document, chunks };
  }
}

// ==================== EMBEDDER AGENT ====================

class EmbedderAgent {
  async generateEmbedding(text) {
    try {
      // Use local model (fast, free)
      const output = await embeddingModel(text, { pooling: 'mean', normalize: true });
      return Array.from(output.data);
    } catch (error) {
      logger.warn(`Local embedding failed, trying OpenAI: ${error.message}`);
      
      // Fallback to OpenAI
      if (openai) {
        const response = await openai.embeddings.create({
          model: 'text-embedding-3-small',
          input: text.slice(0, 8000)  // Token limit
        });
        return response.data[0].embedding;
      }
      
      throw error;
    }
  }
  
  async embedDocument(document) {
    // Embed full document
    const documentEmbedding = await this.generateEmbedding(
      `${document.title}\n\n${document.content.slice(0, 1000)}`
    );
    
    // Embed each chunk
    const embeddedChunks = [];
    for (const chunk of document.chunks || []) {
      const embedding = await this.generateEmbedding(chunk.content);
      embeddedChunks.push({ ...chunk, embedding });
    }
    
    return {
      ...document,
      embedding: documentEmbedding,
      chunks: embeddedChunks
    };
  }
}

// ==================== ENTITY EXTRACTOR AGENT ====================

class EntityExtractorAgent {
  constructor() {
    this.patterns = {
      people: /\b(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Chief|Alhaji|Senator|Governor|President|Minister)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b/g,
      organizations: /\b([A-Z]{2,}(?:\s+[A-Z][a-zA-Z]+)*)\b/g,
      locations: /\b(Lagos|Abuja|Kano|Ibadan|Kaduna|Port Harcourt|Benin|Enugu|Oyo|Ogun|Delta|Rivers|Katsina|Borno|Anambra|Imo|Ondo|Plateau|Niger|Kogi|Sokoto|Bauchi|Osun|Cross River|Akwa Ibom|Bayelsa|Ebonyi|Ekiti|Gombe|Jigawa|Kebbi|Kwara|Nasarawa|Taraba|Yobe|Zamfara|FCT)\b/g
    };
  }
  
  extractEntities(text) {
    const entities = {
      people: [],
      organizations: [],
      locations: [],
      events: []
    };
    
    // Extract people
    let match;
    while ((match = this.patterns.people.exec(text)) !== null) {
      const name = match[2];
      if (!entities.people.find(p => p.name === name)) {
        entities.people.push({
          name,
          type: 'person',
          confidence: 0.8,
          context: text.slice(Math.max(0, match.index - 50), match.index + 100)
        });
      }
    }
    
    // Extract locations
    while ((match = this.patterns.locations.exec(text)) !== null) {
      const location = match[1];
      if (!entities.locations.find(l => l.name === location)) {
        entities.locations.push({
          name: location,
          type: 'location',
          confidence: 0.95,
          context: text.slice(Math.max(0, match.index - 50), match.index + 100)
        });
      }
    }
    
    // Extract organizations (basic)
    const orgMatches = text.match(/\b(INEC|APC|PDP|LP|NNPP|NBA|NLC|TUC|CBN|NNPC|FAAN|NHIS|NIMASA|NCC|SEC|EFCC|ICPC|NPA|NCAA|NERC|NPHCDA)\b/g);
    if (orgMatches) {
      orgMatches.forEach(org => {
        if (!entities.organizations.find(o => o.name === org)) {
          entities.organizations.push({
            name: org,
            type: 'organization',
            confidence: 0.9
          });
        }
      });
    }
    
    return entities;
  }
  
  extractTopics(text) {
    const topics = [];
    const text_lower = text.toLowerCase();
    
    const topicKeywords = {
      election: ['election', 'vote', 'ballot', 'poll', 'campaign'],
      economy: ['economy', 'naira', 'dollar', 'budget', 'finance', 'market'],
      security: ['security', 'police', 'crime', 'terrorism', 'violence'],
      infrastructure: ['road', 'power', 'electricity', 'water', 'bridge'],
      health: ['health', 'hospital', 'doctor', 'disease', 'covid'],
      education: ['school', 'university', 'student', 'education'],
      sports: ['football', 'match', 'team', 'player', 'soccer']
    };
    
    for (const [topic, keywords] of Object.entries(topicKeywords)) {
      let score = 0;
      keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
        const matches = text_lower.match(regex);
        if (matches) score += matches.length;
      });
      
      if (score > 0) {
        topics.push({
          topic,
          confidence: Math.min(score / 3, 1.0)
        });
      }
    }
    
    return topics.sort((a, b) => b.confidence - a.confidence).slice(0, 5);
  }
  
  analyzeSentiment(text) {
    const positive = ['celebrate', 'win', 'success', 'improve', 'growth', 'achieve', 'progress', 'development'];
    const negative = ['kill', 'death', 'attack', 'violence', 'crisis', 'problem', 'fail', 'corruption', 'scandal'];
    
    const text_lower = text.toLowerCase();
    let posCount = positive.filter(w => text_lower.includes(w)).length;
    let negCount = negative.filter(w => text_lower.includes(w)).length;
    
    let label = 'neutral';
    if (posCount > negCount) label = 'positive';
    if (negCount > posCount) label = 'negative';
    
    return {
      label,
      score: (posCount - negCount) / (posCount + negCount + 1),
      positive_words: posCount,
      negative_words: negCount
    };
  }
  
  async processDocument(document) {
    const entities = this.extractEntities(document.content);
    const topics = this.extractTopics(document.content);
    const sentiment = this.analyzeSentiment(document.content);
    
    return {
      ...document,
      entities,
      topics,
      sentiment,
      confidence: 0.8  // Base confidence
    };
  }
}

// ==================== INGESTOR AGENT ====================

class IngestorAgent {
  async ingestToSupabase(document) {
    try {
      // 1. Insert document
      const { data: docData, error: docError } = await supabase
        .from('documents')
        .upsert({
          source_type: document.source_type,
          source_id: document.source_id,
          title: document.title,
          content: document.content,
          content_summary: document.content.slice(0, 500),
          published_date: document.published_date,
          source_metadata: document.source_metadata,
          embedding: document.embedding,
          entities: document.entities,
          topics: document.topics,
          sentiment: document.sentiment,
          confidence: document.confidence,
          processing_status: 'completed'
        }, { onConflict: 'source_type,source_id' })
        .select()
        .single();
      
      if (docError) throw docError;
      
      const documentId = docData.id;
      
      // 2. Insert chunks
      if (document.chunks && document.chunks.length > 0) {
        const chunkRecords = document.chunks.map(chunk => ({
          document_id: documentId,
          content: chunk.content,
          embedding: chunk.embedding,
          position: chunk.position,
          token_count: chunk.token_count
        }));
        
        const { error: chunkError } = await supabase
          .from('document_chunks')
          .upsert(chunkRecords);
        
        if (chunkError) throw chunkError;
      }
      
      // 3. Insert/update entities and relationships
      await this.processEntities(documentId, document.entities);
      
      // 4. Insert topic relationships
      await this.processTopics(documentId, document.topics);
      
      logger.info(`✅ Ingested: ${document.title?.slice(0, 50)}... (${documentId})`);
      
      return { success: true, documentId };
      
    } catch (error) {
      logger.error(`Ingest error:`, error);
      throw error;
    }
  }
  
  async processEntities(documentId, entities) {
    const allEntities = [
      ...(entities.people || []).map(e => ({ ...e, type: 'person' })),
      ...(entities.organizations || []).map(e => ({ ...e, type: 'organization' })),
      ...(entities.locations || []).map(e => ({ ...e, type: 'location' })),
      ...(entities.events || []).map(e => ({ ...e, type: 'event' }))
    ];
    
    for (const entity of allEntities) {
      const slug = entity.name.toLowerCase().replace(/\s+/g, '_');
      
      // Upsert entity
      const { data: entityData, error: entityError } = await supabase
        .from('entities')
        .upsert({
          name: entity.name,
          type: entity.type,
          slug,
          metadata: entity
        }, { onConflict: 'slug' })
        .select()
        .single();
      
      if (entityError) {
        logger.warn(`Entity upsert error for ${slug}:`, entityError);
        continue;
      }
      
      // Create relationship
      await supabase
        .from('document_entities')
        .upsert({
          document_id: documentId,
          entity_id: entityData.id,
          confidence: entity.confidence || 0.8,
          context: entity.context?.slice(0, 200)
        }, { onConflict: 'document_id,entity_id' });
    }
  }
  
  async processTopics(documentId, topics) {
    for (const topic of topics) {
      // Get topic ID
      const { data: topicData } = await supabase
        .from('topics')
        .select('id')
        .eq('slug', topic.topic)
        .single();
      
      if (topicData) {
        await supabase
          .from('document_topics')
          .upsert({
            document_id: documentId,
            topic_id: topicData.id,
            confidence: topic.confidence
          }, { onConflict: 'document_id,topic_id' });
      }
    }
  }
}

// ==================== WORKER SETUP ====================

const parser = new ParserAgent();
const chunker = new ChunkerAgent();
const embedder = new EmbedderAgent();
const extractor = new EntityExtractorAgent();
const ingestor = new IngestorAgent();

// Parse worker
queues.parse.process(CONFIG.queues.parse.concurrency, async (job) => {
  logger.info(`[Parse] Processing: ${job.data.filePath}`);
  const document = await parser.parseJudasOutput(job.data.filePath);
  
  // Queue next step
  await queues.chunk.add('chunk', { document });
  
  return { success: true, documentId: document.source_id };
});

// Chunk worker
queues.chunk.process(CONFIG.queues.chunk.concurrency, async (job) => {
  logger.info(`[Chunk] Processing: ${job.data.document.source_id}`);
  const document = await chunker.chunkDocument(job.data.document);
  
  await queues.embed.add('embed', { document });
  
  return { success: true, chunks: document.chunks.length };
});

// Embed worker
queues.embed.process(CONFIG.queues.embed.concurrency, async (job) => {
  logger.info(`[Embed] Processing: ${job.data.document.source_id}`);
  const document = await embedder.embedDocument(job.data.document);
  
  await queues.entity.add('entity', { document });
  
  return { success: true, embeddingSize: document.embedding?.length };
});

// Entity worker
queues.entity.process(CONFIG.queues.entity.concurrency, async (job) => {
  logger.info(`[Entity] Processing: ${job.data.document.source_id}`);
  const document = await extractor.processDocument(job.data.document);
  
  await queues.ingest.add('ingest', { document });
  
  return { success: true, entities: Object.values(document.entities).flat().length };
});

// Ingest worker
queues.ingest.process(CONFIG.queues.ingest.concurrency, async (job) => {
  logger.info(`[Ingest] Processing: ${job.data.document.source_id}`);
  const result = await ingestor.ingestToSupabase(job.data.document);
  
  return result;
});

// ==================== MAIN ORCHESTRATOR ====================

class EzekielOrchestrator {
  constructor() {
    this.isRunning = false;
  }
  
  async start() {
    logger.info('=== EZEKIEL ORCHESTRATOR STARTING ===');
    
    await initializeClients();
    
    this.isRunning = true;

    await this.sleep(5000); // Give Bull workers time to register
    
    // Start watching for new files
    this.watchLoop();
    
    // Start backfill of existing files
    this.backfillLoop();
    
    logger.info('✅ Ezekiel is running');
  }
  
  async watchLoop() {
    const watchDir = path.join(CONFIG.projectDir, 'data/processed');
    
    while (this.isRunning) {
      try {
        // Find all JSON files in processed directory
        const files = await this.findNewFiles(watchDir);
        
        for (const file of files.slice(0, CONFIG.batchSize)) {
          // Check if already processed
          const { data: existing } = await supabase
            .from('ingestion_queue')
            .select('id')
            .eq('source_type', 'newspaper')
            .eq('source_id', this.fileToSourceId(file))
            .eq('status', 'completed')
            .single();
          
          if (!existing) {
            await queues.parse.add('parse', { filePath: file });
            
            // Add to queue tracking
            await supabase.from('ingestion_queue').upsert({
              source_type: 'newspaper',
              source_id: this.fileToSourceId(file),
              file_path: file,
              status: 'pending'
            });
          }
        }
        
        await this.sleep(30000); // Check every 30 seconds
        
      } catch (error) {
        logger.error('Watch loop error:', error);
        await this.sleep(60000);
      }
    }
  }
  
  async backfillLoop() {
    logger.info('Starting backfill of existing data...');
    
    const processedDir = path.join(CONFIG.projectDir, 'data/processed');
    
    try {
      const files = await this.findAllJsonFiles(processedDir);
      logger.info(`Found ${files.length} files for backfill`);
      
      // Get already processed
      const { data: processed } = await supabase
        .from('documents')
        .select('source_id')
        .eq('source_type', 'newspaper');
      
      const processedIds = new Set(processed?.map(d => d.source_id) || []);
      
      // Queue unprocessed files
      let queued = 0;
      for (const file of files) {
        const sourceId = this.fileToSourceId(file);
        if (!processedIds.has(sourceId)) {
          await queues.parse.add('parse', { filePath: file }, {
            priority: 5,  // Lower priority than real-time
            attempts: 3
          });
          queued++;
        }
      }
      
      logger.info(`✅ Backfill queued: ${queued} files`);
      
    } catch (error) {
      logger.error('Backfill error:', error);
    }
  }
  
  async findNewFiles(dir) {
    const files = [];
    
    async function scan(directory) {
      const entries = await fs.readdir(directory, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(directory, entry.name);
        
        if (entry.isDirectory()) {
          await scan(fullPath);
        } else if (entry.name.endsWith('.json')) {
          files.push(fullPath);
        }
      }
    }
    
    await scan(dir);
    return files.sort((a, b) => b.localeCompare(a)); // Newest first
  }
  
  async findAllJsonFiles(dir) {
    return this.findNewFiles(dir);
  }
  
  fileToSourceId(filePath) {
    const parts = filePath.split('/');
    const filename = parts[parts.length - 1];
    const date = parts.slice(-4, -1).join('_'); // year_month_day
    return `judas_pmnews_${date}_${filename.replace('.json', '')}`;
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  async stop() {
    this.isRunning = false;
    
    await queues.parse.close();
    await queues.chunk.close();
    await queues.embed.close();
    await queues.entity.close();
    await queues.ingest.close();
    
    logger.info('Ezekiel stopped');
  }
}

// ==================== START ====================

const orchestrator = new EzekielOrchestrator();

orchestrator.start().catch(error => {
  logger.error('Fatal error:', error);
  process.exit(1);
});

// Graceful shutdown
process.on('SIGTERM', () => orchestrator.stop());
process.on('SIGINT', () => orchestrator.stop());

module.exports = { EzekielOrchestrator, queues };
