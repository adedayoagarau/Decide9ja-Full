/**
 * Optimized Supabase Sync for $25/mo Pro Tier (8GB)
 * Strategy: Metadata + Summary to Supabase, Full Content stays in SQLite
 * Compression: ~5x smaller than full content sync
 */

const { createClient } = require('@supabase/supabase-js');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  sqlitePath: '/Volumes/Crucial X10/Decide9ja/data/catalog.db',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  
  // Optimized for Pro tier
  batchSize: 1000,  // Larger batches for summary-only data
  maxConcurrent: 3,
  checkpointInterval: 10000,
  
  // Compression settings
  summaryLength: 500,  // Characters
  maxEntitiesPerDoc: 10,  // Only top entities
  
  // Rate limiting
  requestsPerSecond: 15,
  retryAttempts: 3
};

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'supabase-optimized-sync.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

class OptimizedSupabaseSync {
  constructor() {
    this.supabase = null;
    this.db = null;
    this.stats = {
      processed: 0,
      synced: 0,
      failed: 0,
      bytesSent: 0
    };
    this.checkpoint = null;
  }

  async initialize() {
    logger.info('🚀 Initializing Optimized Supabase Sync (Pro Tier)');
    
    this.db = new sqlite3.Database(CONFIG.sqlitePath);
    
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_KEY;
    
    if (!url || !key) {
      throw new Error('SUPABASE_URL and SUPABASE_SERVICE_KEY required');
    }
    
    this.supabase = createClient(url, key);
    await this.loadCheckpoint();
    
    logger.info('✅ Sync initialized');
  }

  async loadCheckpoint() {
    try {
      const data = await fs.readFile(
        path.join(CONFIG.projectDir, 'memory', 'optimized_sync_checkpoint.json'), 
        'utf8'
      );
      this.checkpoint = JSON.parse(data);
      logger.info(`📍 Resuming from: ${this.checkpoint.lastProcessedId || 'start'}`);
    } catch {
      this.checkpoint = { lastProcessedId: null, lastProcessedDate: null };
    }
  }

  async saveCheckpoint() {
    await fs.writeFile(
      path.join(CONFIG.projectDir, 'memory', 'optimized_sync_checkpoint.json'),
      JSON.stringify(this.checkpoint, null, 2)
    );
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

  compressEntities(entitiesJson) {
    try {
      const entities = JSON.parse(entitiesJson || '{}');
      
      // Only keep top entities per category
      const compressed = {
        people: (entities.people || []).slice(0, 5),
        organizations: (entities.organizations || []).slice(0, 3),
        locations: (entities.locations || []).slice(0, 2)
      };
      
      // Remove empty arrays
      Object.keys(compressed).forEach(key => {
        if (compressed[key].length === 0) delete compressed[key];
      });
      
      return compressed;
    } catch {
      return {};
    }
  }

  transformForSupabase(sqliteDoc) {
    const metadata = JSON.parse(sqliteDoc.source_metadata || '{}');
    
    // Calculate size savings
    const fullContentSize = (sqliteDoc.content || '').length;
    const summary = (sqliteDoc.content_summary || sqliteDoc.content || '').slice(0, CONFIG.summaryLength);
    const compressionRatio = fullContentSize > 0 ? (fullContentSize / summary.length).toFixed(1) : 1;
    
    this.stats.bytesSent += summary.length;
    
    return {
      id: sqliteDoc.id,
      source_type: sqliteDoc.source_type,
      newspaper: metadata.newspaper || 'Unknown',
      published_date: sqliteDoc.published_date,
      
      // Compressed content
      title: sqliteDoc.title?.slice(0, 300),
      content_summary: summary,
      word_count: sqliteDoc.content?.split(/\s+/).length || 0,
      
      // Compressed entities
      entities: this.compressEntities(sqliteDoc.entities),
      topics: JSON.parse(sqliteDoc.topics || '[]').slice(0, 3),
      sentiment: JSON.parse(sqliteDoc.sentiment || '{}'),
      
      // Quality signals
      confidence_score: sqliteDoc.confidence,
      has_full_content: true,  // Available in local SQLite
      
      // Tracking
      indexed_at: new Date().toISOString()
    };
  }

  async syncBatch(documents) {
    const records = documents.map(d => this.transformForSupabase(d));
    
    try {
      const { error } = await this.supabase
        .from('documents')
        .upsert(records, { onConflict: 'id' });
      
      if (error) {
        logger.warn(`Batch error: ${error.message}. Trying individual...`);
        
        // Individual fallback
        let success = 0;
        for (const record of records) {
          try {
            const { error: singleError } = await this.supabase
              .from('documents')
              .upsert(record, { onConflict: 'id' });
            if (!singleError) success++;
          } catch (e) {}
          await this.sleep(30);
        }
        return success;
      }
      
      return records.length;
      
    } catch (error) {
      logger.error(`Sync error: ${error.message}`);
      return 0;
    }
  }

  async syncEntities(documents) {
    // Build entity frequency map
    const entityFreq = new Map();
    
    for (const doc of documents) {
      try {
        const entities = JSON.parse(doc.entities || '{}');
        
        for (const person of entities.people || []) {
          const slug = person.toLowerCase().replace(/\s+/g, '_').slice(0, 200);
          entityFreq.set(slug, (entityFreq.get(slug) || 0) + 1);
        }
        
        for (const org of entities.organizations || []) {
          const slug = org.toLowerCase().replace(/\s+/g, '_').slice(0, 200);
          entityFreq.set(slug, (entityFreq.get(slug) || 0) + 1);
        }
      } catch {}
    }
    
    // Only sync entities mentioned 3+ times (reduce noise)
    const significantEntities = Array.from(entityFreq.entries())
      .filter(([_, count]) => count >= 3)
      .map(([slug, count]) => ({
        slug,
        name: slug.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        normalized_name: slug.replace(/_/g, ' '),
        type: 'person',  // Simplified
        mention_count: count
      }));
    
    if (significantEntities.length === 0) return 0;
    
    try {
      const { error } = await this.supabase
        .from('entities')
        .upsert(significantEntities, { onConflict: 'slug' });
      
      return error ? 0 : significantEntities.length;
    } catch {
      return 0;
    }
  }

  async run() {
    const startTime = Date.now();
    logger.info('🚀 Starting OPTIMIZED sync to Supabase (Pro Tier)');
    logger.info('📦 Strategy: Summary-only, Full content in local SQLite');
    logger.info(`🎯 Target: Fit 1.9M docs in 8GB (~4.2KB avg per doc)`);
    
    let hasMore = true;
    let batchNumber = 0;
    
    while (hasMore) {
      const documents = await this.getDocumentsBatch();
      
      if (documents.length === 0) {
        hasMore = false;
        break;
      }
      
      batchNumber++;
      this.stats.processed += documents.length;
      
      logger.info(`[Batch ${batchNumber}] Processing ${documents.length} docs...`);
      
      // Sync documents
      const syncedCount = await this.syncBatch(documents);
      this.stats.synced += syncedCount;
      this.stats.failed += (documents.length - syncedCount);
      
      // Sync significant entities
      const entityCount = await this.syncEntities(documents);
      
      // Calculate compression
      const avgSize = this.stats.bytesSent / this.stats.processed;
      
      logger.info(`  ↳ Synced: ${syncedCount} docs, ${entityCount} entities`);
      logger.info(`  📊 Avg doc size: ${avgSize.toFixed(0)} bytes (${(avgSize/1024).toFixed(2)} KB)`);
      
      // Update checkpoint
      const lastDoc = documents[documents.length - 1];
      this.checkpoint = {
        lastProcessedId: lastDoc.id,
        lastProcessedDate: lastDoc.published_date
      };
      
      // Progress report
      if (batchNumber % 10 === 0) {
        await this.saveCheckpoint();
        
        const elapsed = (Date.now() - startTime) / 1000;
        const rate = this.stats.processed / elapsed;
        const estimatedTotal = 1900000;
        const remaining = estimatedTotal - this.stats.synced;
        const eta = remaining / rate;
        const projectedSize = (this.stats.bytesSent / this.stats.synced) * estimatedTotal;
        
        logger.info(`\n📊 PROGRESS REPORT`);
        logger.info(`  Processed: ${this.stats.processed.toLocaleString()}`);
        logger.info(`  Synced: ${this.stats.synced.toLocaleString()}`);
        logger.info(`  Failed: ${this.stats.failed.toLocaleString()}`);
        logger.info(`  Rate: ${rate.toFixed(1)} docs/sec`);
        logger.info(`  ETA: ${(eta / 3600).toFixed(1)} hours`);
        logger.info(`  Progress: ${((this.stats.synced / estimatedTotal) * 100).toFixed(2)}%`);
        logger.info(`  Projected Supabase Size: ${(projectedSize / 1024 / 1024 / 1024).toFixed(2)} GB / 8 GB`);
        
        // Warning if projected exceeds limit
        if (projectedSize > 7.5 * 1024 * 1024 * 1024) {
          logger.warn(`⚠️  WARNING: Projected size exceeds 8GB limit!`);
          logger.warn(`   Consider further compression or upgrade to Team tier.`);
        }
      }
      
      await this.sleep(1000 / CONFIG.requestsPerSecond);
    }
    
    await this.saveCheckpoint();
    
    const totalTime = (Date.now() - startTime) / 1000;
    const finalSize = (this.stats.bytesSent / this.stats.synced) * 1900000;
    
    logger.info(`\n✅ OPTIMIZED SYNC COMPLETE`);
    logger.info(`Total processed: ${this.stats.processed.toLocaleString()}`);
    logger.info(`Total synced: ${this.stats.synced.toLocaleString()}`);
    logger.info(`Total failed: ${this.stats.failed.toLocaleString()}`);
    logger.info(`Time: ${(totalTime / 60).toFixed(1)} minutes`);
    logger.info(`Average rate: ${(this.stats.processed / totalTime).toFixed(1)} docs/sec`);
    logger.info(`Data sent: ${(this.stats.bytesSent / 1024 / 1024).toFixed(2)} MB`);
    logger.info(`Projected 1.9M size: ${(finalSize / 1024 / 1024 / 1024).toFixed(2)} GB`);
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
  const sync = new OptimizedSupabaseSync();
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

module.exports = { OptimizedSupabaseSync };
