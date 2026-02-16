/**
 * Exhaustive Supabase Sync - Load ALL data with intelligent batching
 * Handles 1.9M+ documents with progress tracking and resume capability
 */

const { createClient } = require('@supabase/supabase-js');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  sqlitePath: '/Volumes/Crucial X10/Decide9ja/data/catalog.db',
  archivingDir: '/Volumes/Crucial X10/Decide9ja/data/archiving',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  
  // Sync settings
  batchSize: 500,  // Supabase recommended max
  maxConcurrent: 2,  // Don't overwhelm Supabase
  checkpointInterval: 5000,  // Save progress every 5000 docs
  
  // Rate limiting
  requestsPerSecond: 10,
  retryAttempts: 3,
  retryDelay: 1000
};

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'supabase-sync.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

class ExhaustiveSupabaseSync {
  constructor() {
    this.supabase = null;
    this.db = null;
    this.stats = {
      processed: 0,
      synced: 0,
      failed: 0,
      skipped: 0
    };
    this.checkpoint = null;
    this.startTime = null;
  }

  async initialize() {
    logger.info('🚀 Initializing Exhaustive Supabase Sync...');
    
    // Connect to SQLite
    this.db = new sqlite3.Database(CONFIG.sqlitePath);
    
    // Connect to Supabase
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_KEY;
    
    if (!url || !key) {
      throw new Error('SUPABASE_URL and SUPABASE_SERVICE_KEY required');
    }
    
    this.supabase = createClient(url, key);
    
    // Load checkpoint
    await this.loadCheckpoint();
    
    logger.info('✅ Sync initialized');
  }

  async loadCheckpoint() {
    try {
      const checkpointPath = path.join(CONFIG.projectDir, 'memory', 'sync_checkpoint.json');
      const data = await fs.readFile(checkpointPath, 'utf8');
      this.checkpoint = JSON.parse(data);
      logger.info(`📍 Resuming from checkpoint: ${JSON.stringify(this.checkpoint)}`);
    } catch {
      this.checkpoint = {
        lastProcessedId: null,
        lastProcessedDate: null,
        batchNumber: 0
      };
    }
  }

  async saveCheckpoint() {
    const checkpointPath = path.join(CONFIG.projectDir, 'memory', 'sync_checkpoint.json');
    await fs.writeFile(checkpointPath, JSON.stringify(this.checkpoint, null, 2));
  }

  async getDocumentsBatch() {
    return new Promise((resolve, reject) => {
      let sql = 'SELECT * FROM documents WHERE 1=1';
      const params = [];
      
      if (this.checkpoint.lastProcessedDate) {
        sql += ' AND published_date > ?';
        params.push(this.checkpoint.lastProcessedDate);
      }
      
      sql += ' ORDER BY published_date, id LIMIT ?';
      params.push(CONFIG.batchSize);
      
      this.db.all(sql, params, (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });
  }

  transformForSupabase(sqliteDoc) {
    return {
      id: sqliteDoc.id,
      source_type: sqliteDoc.source_type,
      source_id: sqliteDoc.source_id,
      newspaper: JSON.parse(sqliteDoc.source_metadata || '{}').newspaper,
      title: sqliteDoc.title,
      content: sqliteDoc.content?.slice(0, 10000),  // Limit size
      published_date: sqliteDoc.published_date,
      scraped_at: sqliteDoc.scraped_date,
      page_number: JSON.parse(sqliteDoc.source_metadata || '{}').page_number,
      confidence_score: sqliteDoc.confidence,
      verified: sqliteDoc.verified === 1,
      processing_status: 'completed'
    };
  }

  async syncBatch(documents) {
    const records = documents.map(d => this.transformForSupabase(d));
    
    try {
      const { data, error } = await this.supabase
        .from('documents')
        .upsert(records, { 
          onConflict: 'id',
          ignoreDuplicates: false
        });
      
      if (error) {
        // Try individual inserts if batch fails
        logger.warn(`Batch failed, trying individual: ${error.message}`);
        let individualSuccess = 0;
        
        for (const record of records) {
          try {
            const { error: singleError } = await this.supabase
              .from('documents')
              .upsert(record, { onConflict: 'id' });
            
            if (!singleError) individualSuccess++;
          } catch (e) {
            logger.warn(`Single record failed: ${e.message}`);
          }
          
          // Small delay between individual inserts
          await this.sleep(50);
        }
        
        return individualSuccess;
      }
      
      return records.length;
      
    } catch (error) {
      logger.error(`Sync error: ${error.message}`);
      return 0;
    }
  }

  async syncEntities(documents) {
    // Extract unique entities from documents
    const entityMap = new Map();
    
    for (const doc of documents) {
      try {
        const entities = JSON.parse(doc.entities || '{}');
        
        for (const person of entities.people || []) {
          const slug = person.toLowerCase().replace(/\s+/g, '_');
          if (!entityMap.has(slug)) {
            entityMap.set(slug, {
              name: person,
              normalized_name: person.toLowerCase(),
              type: 'person',
              slug: slug
            });
          }
        }
        
        for (const org of entities.organizations || []) {
          const slug = org.toLowerCase().replace(/\s+/g, '_');
          if (!entityMap.has(slug)) {
            entityMap.set(slug, {
              name: org,
              normalized_name: org.toLowerCase(),
              type: 'organization',
              slug: slug
            });
          }
        }
      } catch {}
    }
    
    if (entityMap.size === 0) return 0;
    
    const entities = Array.from(entityMap.values());
    
    try {
      const { error } = await this.supabase
        .from('entities')
        .upsert(entities, { onConflict: 'slug' });
      
      if (error) {
        logger.warn(`Entity sync warning: ${error.message}`);
        return 0;
      }
      
      return entities.length;
    } catch (error) {
      logger.error(`Entity sync error: ${error.message}`);
      return 0;
    }
  }

  async syncDocumentEntities(documents) {
    const relations = [];
    
    for (const doc of documents) {
      try {
        const entities = JSON.parse(doc.entities || '{}');
        const year = new Date(doc.published_date).getFullYear();
        
        for (const person of entities.people || []) {
          relations.push({
            document_id: doc.id,
            document_year: year,
            entity_slug: person.toLowerCase().replace(/\s+/g, '_'),
            confidence: 0.8
          });
        }
      } catch {}
    }
    
    if (relations.length === 0) return 0;
    
    // Batch insert relations
    try {
      const { error } = await this.supabase
        .from('document_entities')
        .upsert(relations, { onConflict: 'document_id,entity_id' });
      
      return error ? 0 : relations.length;
    } catch {
      return 0;
    }
  }

  async run() {
    this.startTime = Date.now();
    logger.info('🚀 Starting exhaustive sync to Supabase...');
    logger.info(`📊 Target: 1.9M+ documents`);
    logger.info(`⚙️ Batch size: ${CONFIG.batchSize}`);
    
    let hasMore = true;
    let batchNumber = this.checkpoint.batchNumber;
    
    while (hasMore) {
      // Get batch from SQLite
      const documents = await this.getDocumentsBatch();
      
      if (documents.length === 0) {
        hasMore = false;
        break;
      }
      
      batchNumber++;
      this.stats.processed += documents.length;
      
      logger.info(`[Batch ${batchNumber}] Processing ${documents.length} documents...`);
      
      // Sync documents
      const syncedCount = await this.syncBatch(documents);
      this.stats.synced += syncedCount;
      this.stats.failed += (documents.length - syncedCount);
      
      // Sync entities
      const entityCount = await this.syncEntities(documents);
      logger.info(`  ↳ Synced ${syncedCount} docs, ${entityCount} entities`);
      
      // Update checkpoint
      const lastDoc = documents[documents.length - 1];
      this.checkpoint = {
        lastProcessedId: lastDoc.id,
        lastProcessedDate: lastDoc.published_date,
        batchNumber: batchNumber
      };
      
      // Save checkpoint periodically
      if (batchNumber % 10 === 0) {
        await this.saveCheckpoint();
        
        // Progress report
        const elapsed = (Date.now() - this.startTime) / 1000;
        const rate = this.stats.processed / elapsed;
        const estimatedTotal = 1900000;  // 1.9M estimate
        const remaining = estimatedTotal - this.stats.processed;
        const eta = remaining / rate;
        
        logger.info(`\n📊 PROGRESS REPORT`);
        logger.info(`  Processed: ${this.stats.processed.toLocaleString()}`);
        logger.info(`  Synced: ${this.stats.synced.toLocaleString()}`);
        logger.info(`  Failed: ${this.stats.failed.toLocaleString()}`);
        logger.info(`  Rate: ${rate.toFixed(1)} docs/sec`);
        logger.info(`  ETA: ${(eta / 3600).toFixed(1)} hours`);
        logger.info(`  Progress: ${((this.stats.processed / estimatedTotal) * 100).toFixed(2)}%`);
      }
      
      // Rate limiting
      await this.sleep(1000 / CONFIG.requestsPerSecond);
    }
    
    // Final checkpoint
    await this.saveCheckpoint();
    
    // Final report
    const totalTime = (Date.now() - this.startTime) / 1000;
    logger.info(`\n✅ SYNC COMPLETE`);
    logger.info(`Total processed: ${this.stats.processed.toLocaleString()}`);
    logger.info(`Total synced: ${this.stats.synced.toLocaleString()}`);
    logger.info(`Total failed: ${this.stats.failed.toLocaleString()}`);
    logger.info(`Time: ${(totalTime / 60).toFixed(1)} minutes`);
    logger.info(`Average rate: ${(this.stats.processed / totalTime).toFixed(1)} docs/sec`);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  close() {
    if (this.db) this.db.close();
  }
}

// CLI
async function main() {
  const command = process.argv[2];
  
  if (command === 'status') {
    // Check Supabase status
    const sync = new ExhaustiveSupabaseSync();
    await sync.initialize();
    
    const { count, error } = await sync.supabase
      .from('documents')
      .select('*', { count: 'exact', head: true });
    
    if (error) {
      console.error('Error:', error.message);
    } else {
      console.log(`\n📊 Supabase Status:`);
      console.log(`  Documents: ${count?.toLocaleString() || 0}`);
      console.log(`  Checkpoint: ${JSON.stringify(sync.checkpoint, null, 2)}`);
    }
    
    sync.close();
    return;
  }
  
  // Full sync
  const sync = new ExhaustiveSupabaseSync();
  await sync.initialize();
  
  try {
    await sync.run();
  } catch (error) {
    logger.error('Fatal error:', error);
    await sync.saveCheckpoint();
  } finally {
    sync.close();
  }
}

if (require.main === module) {
  main().catch(error => {
    logger.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { ExhaustiveSupabaseSync };
