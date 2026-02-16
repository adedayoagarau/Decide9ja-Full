/**
 * Sync Service - Push recent data to Supabase (Hot Tier)
 * Keeps local SQLite (all data) + Supabase (recent 2 years)
 */

const { createClient } = require('@supabase/supabase-js');
const sqlite3 = require('sqlite3').verbose();
const winston = require('winston');
const path = require('path');

const CONFIG = {
  sqlitePath: '/Volumes/Crucial X10/Decide9ja/data/catalog.db',
  hotTierYears: 2,  // Sync last 2 years
  batchSize: 100,
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs'
};

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'sync.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

class SyncService {
  constructor() {
    this.db = null;
    this.supabase = null;
  }

  async initialize() {
    // Connect to SQLite
    this.db = new sqlite3.Database(CONFIG.sqlitePath);
    
    // Connect to Supabase
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_ANON_KEY;
    
    if (!supabaseUrl || !supabaseKey) {
      throw new Error('SUPABASE_URL and SUPABASE_KEY required');
    }
    
    this.supabase = createClient(supabaseUrl, supabaseKey);
    
    logger.info('✅ Sync service initialized');
  }

  async getRecentDocuments() {
    const cutoffDate = new Date();
    cutoffDate.setFullYear(cutoffDate.getFullYear() - CONFIG.hotTierYears);
    
    return new Promise((resolve, reject) => {
      this.db.all(
        `SELECT * FROM documents 
         WHERE published_date >= ?
         AND processing_status = 'completed'
         ORDER BY published_date DESC`,
        [cutoffDate.toISOString().split('T')[0]],
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        }
      );
    });
  }

  async syncToSupabase() {
    logger.info('🔄 Starting sync to Supabase...');
    
    const docs = await this.getRecentDocuments();
    logger.info(`Found ${docs.length} documents to sync (last ${CONFIG.hotTierYears} years)`);
    
    let synced = 0;
    let failed = 0;
    
    // Process in batches
    for (let i = 0; i < docs.length; i += CONFIG.batchSize) {
      const batch = docs.slice(i, i + CONFIG.batchSize);
      
      const records = batch.map(doc => ({
        id: doc.id,
        source_type: doc.source_type,
        source_id: doc.source_id,
        title: doc.title,
        content: doc.content?.slice(0, 5000), // Limit size
        content_summary: doc.content_summary,
        published_date: doc.published_date,
        source_metadata: JSON.parse(doc.source_metadata || '{}'),
        entities: JSON.parse(doc.entities || '{}'),
        topics: JSON.parse(doc.topics || '[]'),
        sentiment: JSON.parse(doc.sentiment || '{}'),
        confidence: doc.confidence,
        processing_status: 'completed'
      }));
      
      try {
        const { error } = await this.supabase
          .from('documents')
          .upsert(records, { onConflict: 'id' });
        
        if (error) {
          logger.error(`Batch sync error:`, error);
          failed += batch.length;
        } else {
          synced += batch.length;
          logger.info(`Synced batch ${Math.floor(i/CONFIG.batchSize) + 1}/${Math.ceil(docs.length/CONFIG.batchSize)}`);
        }
        
      } catch (error) {
        logger.error(`Batch error:`, error.message);
        failed += batch.length;
      }
      
      // Small delay between batches
      await new Promise(r => setTimeout(r, 100));
    }
    
    logger.info(`✅ Sync complete: ${synced} synced, ${failed} failed`);
    return { synced, failed };
  }

  async getSyncStatus() {
    // Get local count (recent)
    const localCount = await new Promise((resolve, reject) => {
      const cutoffDate = new Date();
      cutoffDate.setFullYear(cutoffDate.getFullYear() - CONFIG.hotTierYears);
      
      this.db.get(
        'SELECT COUNT(*) as count FROM documents WHERE published_date >= ?',
        [cutoffDate.toISOString().split('T')[0]],
        (err, row) => {
          if (err) reject(err);
          else resolve(row.count);
        }
      );
    });
    
    // Get Supabase count
    const { count: supabaseCount, error } = await this.supabase
      .from('documents')
      .select('*', { count: 'exact', head: true });
    
    return {
      local_recent_documents: localCount,
      supabase_documents: error ? 'Error' : supabaseCount,
      hot_tier_years: CONFIG.hotTierYears,
      last_sync: new Date().toISOString()
    };
  }

  close() {
    if (this.db) this.db.close();
  }
}

// CLI
async function main() {
  const command = process.argv[2];
  
  const sync = new SyncService();
  await sync.initialize();
  
  switch (command) {
    case 'sync':
      await sync.syncToSupabase();
      break;
    
    case 'status':
      const status = await sync.getSyncStatus();
      console.log('\n📊 Sync Status:');
      console.log(JSON.stringify(status, null, 2));
      break;
    
    default:
      console.log('Usage:');
      console.log('  node sync.js sync    - Sync recent data to Supabase');
      console.log('  node sync.js status  - Check sync status');
  }
  
  sync.close();
}

if (require.main === module) {
  main().catch(error => {
    logger.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { SyncService };
