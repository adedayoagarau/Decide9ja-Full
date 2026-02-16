/**
 * SQLite-Only RAG System
 * Free, unlimited, file-based search with FTS5
 * No external dependencies, no Supabase limits
 */

const sqlite3 = require('sqlite3').verbose();
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

// Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  sqlitePath: '/Volumes/Crucial X10/Decide9ja/data/catalog.db',
  unifiedDir: '/Volumes/Crucial X10/Decide9ja/data/unified',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
};

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'sqlite-rag.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

class SQLiteRAG {
  constructor() {
    this.db = null;
  }

  async initialize() {
    logger.info('🚀 Initializing SQLite RAG System...');

    // Ensure directory exists
    await fs.mkdir(path.dirname(CONFIG.sqlitePath), { recursive: true });
    
    // Open database
    this.db = new sqlite3.Database(CONFIG.sqlitePath);
    
    // Initialize schema
    await this.initializeSchema();
    
    logger.info('✅ SQLite RAG Ready');
    logger.info(`📁 Database: ${CONFIG.sqlitePath}`);
  }

  initializeSchema() {
    return new Promise((resolve, reject) => {
      this.db.exec(`
        -- Main documents table
        CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY,
          source_type TEXT,
          source_id TEXT,
          title TEXT,
          content TEXT,
          content_summary TEXT,
          published_date TEXT,
          scraped_date TEXT,
          source_metadata TEXT,
          entities TEXT,
          topics TEXT,
          sentiment TEXT,
          confidence REAL,
          verified INTEGER DEFAULT 0,
          processing_status TEXT DEFAULT 'pending',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Entity registry
        CREATE TABLE IF NOT EXISTS entities (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          type TEXT NOT NULL,
          slug TEXT UNIQUE NOT NULL,
          aliases TEXT,
          metadata TEXT,
          mention_count INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Document-entity relationships
        CREATE TABLE IF NOT EXISTS document_entities (
          document_id TEXT,
          entity_id TEXT,
          confidence REAL,
          context TEXT,
          PRIMARY KEY (document_id, entity_id)
        );

        -- Topics
        CREATE TABLE IF NOT EXISTS topics (
          id TEXT PRIMARY KEY,
          name TEXT UNIQUE NOT NULL,
          slug TEXT UNIQUE NOT NULL,
          keywords TEXT,
          document_count INTEGER DEFAULT 0
        );

        -- Document-topic relationships
        CREATE TABLE IF NOT EXISTS document_topics (
          document_id TEXT,
          topic_id TEXT,
          confidence REAL,
          PRIMARY KEY (document_id, topic_id)
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(published_date);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(processing_status);
        CREATE INDEX IF NOT EXISTS idx_entities_slug ON entities(slug);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

        -- Full-text search (FTS5)
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
          title, 
          content,
          tokenize='porter'
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS documents_fts_insert AFTER INSERT ON documents BEGIN
          INSERT INTO documents_fts(rowid, title, content) 
          VALUES (new.rowid, new.title, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS documents_fts_delete AFTER DELETE ON documents BEGIN
          DELETE FROM documents_fts WHERE rowid = old.rowid;
        END;

        CREATE TRIGGER IF NOT EXISTS documents_fts_update AFTER UPDATE ON documents BEGIN
          DELETE FROM documents_fts WHERE rowid = old.rowid;
          INSERT INTO documents_fts(rowid, title, content) 
          VALUES (new.rowid, new.title, new.content);
        END;

        -- Insert default topics
        INSERT OR IGNORE INTO topics (id, name, slug, keywords) VALUES
          ('politics', 'Politics', 'politics', 'election,vote,government,party,senate,president,governor'),
          ('economy', 'Economy', 'economy', 'budget,naira,dollar,finance,market,trade,business'),
          ('security', 'Security', 'security', 'police,crime,terrorism,violence,banditry,army'),
          ('infrastructure', 'Infrastructure', 'infrastructure', 'road,power,electricity,water,bridge,construction'),
          ('health', 'Health', 'health', 'hospital,doctor,disease,covid,medicine,healthcare'),
          ('education', 'Education', 'education', 'school,university,student,education,academic,exam'),
          ('sports', 'Sports', 'sports', 'football,match,team,player,soccer,super eagles'),
          ('entertainment', 'Entertainment', 'entertainment', 'music,movie,nollywood,celebrity,actor,film');
      `, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  async ingestDocument(doc) {
    return new Promise((resolve, reject) => {
      const stmt = this.db.prepare(`
        INSERT OR REPLACE INTO documents 
        (id, source_type, source_id, title, content, content_summary, published_date, 
         scraped_date, source_metadata, entities, topics, sentiment, confidence, processing_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);

      stmt.run(
        doc.id,
        doc.source_type,
        doc.source_id,
        doc.title,
        doc.content,
        doc.content_summary,
        doc.published_date,
        doc.scraped_date || new Date().toISOString(),
        JSON.stringify(doc.source_metadata || {}),
        JSON.stringify(doc.entities || {}),
        JSON.stringify(doc.topics || {}),
        JSON.stringify(doc.sentiment || {}),
        doc.confidence || 0.8,
        'completed',
        function(err) {
          if (err) {
            reject(err);
          } else {
            resolve({ id: doc.id, changes: this.changes });
          }
        }
      );

      stmt.finalize();
    });
  }

  async search(query, options = {}) {
    const { limit = 10, filters = {} } = options;
    
    logger.info(`🔍 Searching: "${query.slice(0, 50)}..."`);

    return new Promise((resolve, reject) => {
      // Use FTS5 for full-text search
      let sql = `
        SELECT d.*, rank FROM documents d
        JOIN documents_fts fts ON d.rowid = fts.rowid
        WHERE documents_fts MATCH ?
      `;
      
      const params = [query];
      
      // Add filters
      if (filters.source_type) {
        sql += ` AND d.source_type = ?`;
        params.push(filters.source_type);
      }
      if (filters.newspaper) {
        sql += ` AND json_extract(d.source_metadata, '$.newspaper') = ?`;
        params.push(filters.newspaper);
      }
      if (filters.date_from) {
        sql += ` AND d.published_date >= ?`;
        params.push(filters.date_from);
      }
      if (filters.date_to) {
        sql += ` AND d.published_date <= ?`;
        params.push(filters.date_to);
      }
      
      sql += ` ORDER BY rank LIMIT ?`;
      params.push(limit);

      this.db.all(sql, params, (err, rows) => {
        if (err) {
          // Fallback to LIKE search if FTS fails
          this.db.all(
            `SELECT * FROM documents 
             WHERE title LIKE ? OR content LIKE ? 
             ORDER BY published_date DESC LIMIT ?`,
            [`%${query}%`, `%${query}%`, limit],
            (err2, rows2) => {
              if (err2) reject(err2);
              else resolve({
                query,
                results: rows2 || [],
                count: rows2?.length || 0,
                method: 'fallback'
              });
            }
          );
        } else {
          resolve({
            query,
            results: rows || [],
            count: rows?.length || 0,
            method: 'fts5'
          });
        }
      });
    });
  }

  async getById(id) {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT * FROM documents WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row);
      });
    });
  }

  async getStats() {
    return new Promise((resolve, reject) => {
      this.db.get(`
        SELECT 
          COUNT(*) as total_documents,
          COUNT(DISTINCT json_extract(source_metadata, '$.newspaper')) as newspapers,
          MIN(published_date) as earliest_date,
          MAX(published_date) as latest_date
        FROM documents
      `, (err, row) => {
        if (err) reject(err);
        else {
          // Get file size
          fs.stat(CONFIG.sqlitePath).then(stats => {
            resolve({
              ...row,
              database_size_mb: (stats.size / 1024 / 1024).toFixed(2),
              database_path: CONFIG.sqlitePath
            });
          }).catch(() => resolve(row));
        }
      });
    });
  }

  async getByDateRange(startDate, endDate, limit = 100) {
    return new Promise((resolve, reject) => {
      this.db.all(
        `SELECT * FROM documents 
         WHERE published_date BETWEEN ? AND ?
         ORDER BY published_date DESC
         LIMIT ?`,
        [startDate, endDate, limit],
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        }
      );
    });
  }

  async getByNewspaper(newspaper, limit = 100) {
    return new Promise((resolve, reject) => {
      this.db.all(
        `SELECT * FROM documents 
         WHERE json_extract(source_metadata, '$.newspaper') = ?
         ORDER BY published_date DESC
         LIMIT ?`,
        [newspaper, limit],
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        }
      );
    });
  }

  async processUnifiedFiles() {
    logger.info('📁 Processing unified files...');
    
    try {
      const files = await fs.readdir(CONFIG.unifiedDir);
      const jsonFiles = files.filter(f => f.endsWith('.json') && f !== 'catalog.json');
      
      logger.info(`Found ${jsonFiles.length} files to ingest`);

      let processed = 0;
      let failed = 0;

      for (let i = 0; i < jsonFiles.length; i++) {
        const file = jsonFiles[i];
        
        if ((i + 1) % 10 === 0 || i === 0) {
          logger.info(`[${i + 1}/${jsonFiles.length}] Processing...`);
        }

        try {
          const content = await fs.readFile(path.join(CONFIG.unifiedDir, file), 'utf8');
          const doc = JSON.parse(content);
          
          await this.ingestDocument(doc);
          processed++;

        } catch (error) {
          logger.error(`Failed to process ${file}:`, error.message);
          failed++;
        }
      }

      logger.info(`✅ Complete: ${processed} ingested, ${failed} failed`);
      
      const stats = await this.getStats();
      logger.info(`📊 Total documents: ${stats.total_documents}`);
      logger.info(`💾 Database size: ${stats.database_size_mb} MB`);
      
    } catch (error) {
      logger.error('Process error:', error);
    }
  }

  close() {
    if (this.db) {
      this.db.close();
    }
  }
}

// CLI interface
async function main() {
  const rag = new SQLiteRAG();
  await rag.initialize();

  const command = process.argv[2];

  switch (command) {
    case 'ingest':
      await rag.processUnifiedFiles();
      break;
    
    case 'search':
      const query = process.argv[3] || 'Nigerian election';
      const results = await rag.search(query, { limit: 5 });
      console.log('\n🔍 Search Results:');
      console.log(`Query: "${query}"`);
      console.log(`Found: ${results.count} documents`);
      console.log(`Method: ${results.method}`);
      console.log('\nResults:');
      results.results.forEach((doc, i) => {
        console.log(`\n${i + 1}. ${doc.title || 'Untitled'}`);
        console.log(`   Date: ${doc.published_date}`);
        console.log(`   Newspaper: ${JSON.parse(doc.source_metadata || '{}').newspaper || 'Unknown'}`);
        console.log(`   Content: ${doc.content_summary?.slice(0, 100)}...`);
      });
      break;
    
    case 'stats':
      const stats = await rag.getStats();
      console.log('\n📊 Database Statistics:');
      console.log(JSON.stringify(stats, null, 2));
      break;
    
    case 'by-date':
      const startDate = process.argv[3] || '2021-01-01';
      const endDate = process.argv[4] || '2021-12-31';
      const dateResults = await rag.getByDateRange(startDate, endDate);
      console.log(`\n📅 Documents from ${startDate} to ${endDate}:`);
      console.log(`Found: ${dateResults.length}`);
      dateResults.forEach(doc => {
        console.log(`- ${doc.published_date}: ${doc.title?.slice(0, 60)}...`);
      });
      break;
    
    default:
      console.log('SQLite RAG System - Usage:');
      console.log('  npm run rag:ingest              - Ingest all unified files');
      console.log('  npm run rag:search "query"      - Search documents');
      console.log('  npm run rag:stats               - Show statistics');
      console.log('  npm run rag:date 2021-01-01 2021-12-31 - Get by date range');
  }

  rag.close();
}

if (require.main === module) {
  main().catch(error => {
    logger.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { SQLiteRAG };
