/**
 * ChromaDB + SQLite Local RAG System
 * Free, unlimited, file-based vector search
 */

const { ChromaClient } = require('chromadb');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

// Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  chromaDir: '/Volumes/Crucial X10/Decide9ja/data/chroma',
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
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'local-rag.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

class LocalRAG {
  constructor() {
    this.chroma = null;
    this.collection = null;
    this.db = null;
  }

  async initialize() {
    logger.info('🚀 Initializing Local RAG System...');

    // Initialize ChromaDB (embedded mode - file based)
    await fs.mkdir(CONFIG.chromaDir, { recursive: true });
    this.chroma = new ChromaClient({ 
      path: 'http://localhost:8000'  // Will use embedded if chromadb is installed
    });
    
    // Get or create collection
    try {
      this.collection = await this.chroma.getCollection({ name: 'documents' });
      logger.info('✅ Collection "documents" loaded');
    } catch {
      this.collection = await this.chroma.createCollection({ 
        name: 'documents',
        metadata: { description: 'Nigerian newspaper archives' }
      });
      logger.info('✅ Collection "documents" created');
    }

    // Initialize SQLite
    await fs.mkdir(path.dirname(CONFIG.sqlitePath), { recursive: true });
    this.db = new sqlite3.Database(CONFIG.sqlitePath);
    
    await this.initializeSQLite();
    
    logger.info('✅ Local RAG Ready');
  }

  initializeSQLite() {
    return new Promise((resolve, reject) => {
      this.db.exec(`
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

        CREATE TABLE IF NOT EXISTS document_entities (
          document_id TEXT,
          entity_id TEXT,
          confidence REAL,
          context TEXT,
          PRIMARY KEY (document_id, entity_id)
        );

        CREATE TABLE IF NOT EXISTS topics (
          id TEXT PRIMARY KEY,
          name TEXT UNIQUE NOT NULL,
          slug TEXT UNIQUE NOT NULL,
          keywords TEXT,
          document_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS document_topics (
          document_id TEXT,
          topic_id TEXT,
          confidence REAL,
          PRIMARY KEY (document_id, topic_id)
        );

        CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(published_date);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(processing_status);
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title, content);

        INSERT OR IGNORE INTO topics (id, name, slug, keywords) VALUES
          ('politics', 'Politics', 'politics', 'election,vote,government,party'),
          ('economy', 'Economy', 'economy', 'budget,naira,dollar,finance'),
          ('security', 'Security', 'security', 'police,crime,terrorism,violence'),
          ('infrastructure', 'Infrastructure', 'infrastructure', 'road,power,electricity,water'),
          ('health', 'Health', 'health', 'hospital,doctor,disease,medicine'),
          ('education', 'Education', 'education', 'school,university,student'),
          ('sports', 'Sports', 'sports', 'football,match,team,player'),
          ('entertainment', 'Entertainment', 'entertainment', 'music,movie,nollywood');
      `, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  async ingestDocument(doc) {
    try {
      // Add to ChromaDB (vector search)
      await this.collection.add({
        ids: [doc.id],
        documents: [doc.content.slice(0, 8000)],
        metadatas: [{
          title: doc.title,
          published_date: doc.published_date,
          source_type: doc.source_type,
          newspaper: doc.source_metadata?.newspaper,
          sentiment: doc.sentiment?.label
        }],
        embeddings: doc.embedding ? [doc.embedding] : undefined
      });

      // Add to SQLite (structured queries)
      await this.insertToSQLite(doc);

      logger.info(`✅ Ingested: ${doc.title?.slice(0, 50)}...`);
      return { success: true };

    } catch (error) {
      logger.error(`❌ Ingest failed: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  insertToSQLite(doc) {
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
        doc.scraped_date,
        JSON.stringify(doc.source_metadata || {}),
        JSON.stringify(doc.entities || {}),
        JSON.stringify(doc.topics || {}),
        JSON.stringify(doc.sentiment || {}),
        doc.confidence || 0.8,
        'completed',
        (err) => {
          if (err) reject(err);
          else resolve();
        }
      );

      stmt.finalize();
    });
  }

  async search(query, options = {}) {
    const { limit = 10, filters = {} } = options;
    
    logger.info(`🔍 Searching: "${query.slice(0, 50)}..."`);

    // ChromaDB semantic search
    const chromaResults = await this.collection.query({
      queryTexts: [query],
      nResults: limit,
      where: filters.source_type ? { source_type: filters.source_type } : undefined
    });

    // SQLite full-text search as backup
    const sqliteResults = await this.sqliteSearch(query, limit);

    // Combine and deduplicate
    const combined = this.combineResults(chromaResults, sqliteResults);

    return {
      query,
      results: combined,
      count: combined.length,
      sources: {
        semantic: chromaResults.ids?.[0]?.length || 0,
        text: sqliteResults.length
      }
    };
  }

  sqliteSearch(query, limit) {
    return new Promise((resolve, reject) => {
      const sql = `
        SELECT d.*, rank FROM documents d
        JOIN documents_fts fts ON d.id = fts.rowid
        WHERE documents_fts MATCH ?
        ORDER BY rank
        LIMIT ?
      `;

      this.db.all(sql, [query, limit], (err, rows) => {
        if (err) {
          // Fallback if FTS not ready
          this.db.all(
            `SELECT * FROM documents WHERE title LIKE ? OR content LIKE ? LIMIT ?`,
            [`%${query}%`, `%${query}%`, limit],
            (err2, rows2) => {
              if (err2) reject(err2);
              else resolve(rows2 || []);
            }
          );
        } else {
          resolve(rows || []);
        }
      });
    });
  }

  combineResults(chromaResults, sqliteResults) {
    const seen = new Set();
    const combined = [];

    // Add Chroma results first
    if (chromaResults.ids?.[0]) {
      for (let i = 0; i < chromaResults.ids[0].length; i++) {
        const id = chromaResults.ids[0][i];
        if (!seen.has(id)) {
          seen.add(id);
          combined.push({
            id,
            score: chromaResults.distances?.[0]?.[i],
            metadata: chromaResults.metadatas?.[0]?.[i],
            source: 'semantic'
          });
        }
      }
    }

    // Add SQLite results
    for (const row of sqliteResults) {
      if (!seen.has(row.id)) {
        seen.add(row.id);
        combined.push({
          id: row.id,
          document: row,
          source: 'text'
        });
      }
    }

    return combined;
  }

  async getStats() {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT COUNT(*) as count FROM documents', (err, row) => {
        if (err) reject(err);
        else resolve({
          sqlite_documents: row.count,
          storage_path: CONFIG.sqlitePath
        });
      });
    });
  }

  async processUnifiedFiles() {
    logger.info('📁 Processing unified files...');
    
    const files = await fs.readdir(CONFIG.unifiedDir);
    const jsonFiles = files.filter(f => f.endsWith('.json') && f !== 'catalog.json');
    
    logger.info(`Found ${jsonFiles.length} files to ingest`);

    let processed = 0;
    let failed = 0;

    for (const file of jsonFiles) {
      try {
        const content = await fs.readFile(path.join(CONFIG.unifiedDir, file), 'utf8');
        const doc = JSON.parse(content);
        
        const result = await this.ingestDocument(doc);
        if (result.success) processed++;
        else failed++;

      } catch (error) {
        logger.error(`Failed to process ${file}:`, error.message);
        failed++;
      }
    }

    logger.info(`✅ Complete: ${processed} ingested, ${failed} failed`);
    
    const stats = await this.getStats();
    logger.info(`📊 Total documents: ${stats.sqlite_documents}`);
  }

  close() {
    if (this.db) {
      this.db.close();
    }
  }
}

// CLI interface
async function main() {
  const rag = new LocalRAG();
  await rag.initialize();

  const command = process.argv[2];

  switch (command) {
    case 'ingest':
      await rag.processUnifiedFiles();
      break;
    
    case 'search':
      const query = process.argv[3] || 'Nigerian election';
      const results = await rag.search(query, { limit: 5 });
      console.log('\n🔍 Results:');
      console.log(JSON.stringify(results, null, 2));
      break;
    
    case 'stats':
      const stats = await rag.getStats();
      console.log('\n📊 Stats:');
      console.log(JSON.stringify(stats, null, 2));
      break;
    
    default:
      console.log('Usage:');
      console.log('  node local-rag.js ingest    - Ingest all unified files');
      console.log('  node local-rag.js search "query" - Search documents');
      console.log('  node local-rag.js stats     - Show statistics');
  }

  rag.close();
}

if (require.main === module) {
  main().catch(error => {
    logger.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { LocalRAG };
