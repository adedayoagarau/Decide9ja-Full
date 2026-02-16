/**
 * Bulk Ingest Philip's Archiving Data to SQLite
 * Processes metadata.json files directly from data/archiving/
 */

const sqlite3 = require('sqlite3').verbose();
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  archivingDir: '/Volumes/Crucial X10/Decide9ja/data/archiving',
  sqlitePath: '/Volumes/Crucial X10/Decide9ja/data/catalog.db',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  batchSize: 100
};

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'bulk-ingest.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

class BulkIngestor {
  constructor() {
    this.db = null;
    this.processed = 0;
    this.failed = 0;
  }

  async initialize() {
    logger.info('🚀 Initializing Bulk Ingestor...');
    
    await fs.mkdir(path.dirname(CONFIG.sqlitePath), { recursive: true });
    this.db = new sqlite3.Database(CONFIG.sqlitePath);
    
    await this.initializeSchema();
    logger.info('✅ Ready to ingest');
  }

  initializeSchema() {
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
          processing_status TEXT DEFAULT 'completed',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(published_date);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source_type, source_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title, content, tokenize='porter');

        CREATE TRIGGER IF NOT EXISTS documents_fts_insert AFTER INSERT ON documents BEGIN
          INSERT INTO documents_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS documents_fts_delete AFTER DELETE ON documents BEGIN
          DELETE FROM documents_fts WHERE rowid = old.rowid;
        END;
      `, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  async findMetadataFiles() {
    const files = [];
    
    async function scan(dir) {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await scan(fullPath);
        } else if (entry.name === 'metadata.json') {
          files.push(fullPath);
        }
      }
    }
    
    await scan(CONFIG.archivingDir);
    return files;
  }

  extractEntities(text) {
    if (!text) return { people: [], organizations: [], locations: [] };
    
    const entities = { people: [], organizations: [], locations: [] };
    
    // Simple patterns
    const peopleMatches = text.match(/\b(Mr\.?|Mrs\.?|Dr\.?|Chief|Alhaji|Senator|Governor|President)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g);
    if (peopleMatches) {
      entities.people = [...new Set(peopleMatches)];
    }
    
    const orgMatches = text.match(/\b(INEC|APC|PDP|LP|NNPP|NLC|TUC|CBN|NNPC|EFCC|ICPC|NBA|NPA|FAAN|NHIS)\b/g);
    if (orgMatches) {
      entities.organizations = [...new Set(orgMatches)];
    }
    
    const locMatches = text.match(/\b(Lagos|Abuja|Kano|Ibadan|Kaduna|Port Harcourt|Enugu|Benin|Oyo|Nigeria)\b/g);
    if (locMatches) {
      entities.locations = [...new Set(locMatches)];
    }
    
    return entities;
  }

  extractTopics(text) {
    if (!text) return [];
    const topics = [];
    const text_lower = text.toLowerCase();
    
    const keywords = {
      election: ['election', 'vote', 'ballot', 'poll', 'campaign'],
      economy: ['economy', 'naira', 'dollar', 'budget', 'finance'],
      security: ['security', 'police', 'crime', 'terrorism', 'violence'],
      infrastructure: ['road', 'power', 'electricity', 'water'],
      health: ['health', 'hospital', 'doctor', 'disease'],
      education: ['school', 'university', 'student', 'education']
    };
    
    for (const [topic, words] of Object.entries(keywords)) {
      let score = 0;
      words.forEach(word => {
        if (text_lower.includes(word)) score++;
      });
      if (score > 0) topics.push({ topic, confidence: Math.min(score / 2, 1) });
    }
    
    return topics.slice(0, 5);
  }

  async processMetadataFile(filePath) {
    try {
      const data = JSON.parse(await fs.readFile(filePath, 'utf8'));
      
      // Support both 'articles' (Philip's scraper) and 'issues' (legacy)
      const items = data.articles || data.issues;
      if (!items || !Array.isArray(items) || items.length === 0) {
        return null;
      }

      // Build content from articles/issues
      const content = items.map(item => {
        return [
          item.title || item.headline || '',
          item.content || '',
          item.ocrText || '',
          item.snippet || ''
        ].filter(Boolean).join('\n\n');
      }).join('\n\n---\n\n');

      // Extract date from path: data/archiving/pmnews/2022/03/03/metadata.json
      const pathParts = filePath.split('/');
      const year = pathParts[pathParts.length - 4];
      const month = pathParts[pathParts.length - 3];
      const day = pathParts[pathParts.length - 2];
      const date = `${year}-${month}-${day}`;

      const doc = {
        id: `philip_${data.newspaper?.toLowerCase().replace(/\s+/g, '_')}_${date}`,
        source_type: 'newspaper',
        source_id: date,
        title: items[0]?.title || items[0]?.headline || `${data.newspaper} ${date}`,
        content: content,
        content_summary: content.slice(0, 500),
        published_date: date,
        scraped_date: data.scrapedAt || new Date().toISOString(),
        source_metadata: JSON.stringify({
          newspaper: data.newspaper,
          article_count: items.length,
          file_path: filePath
        }),
        entities: JSON.stringify(this.extractEntities(content)),
        topics: JSON.stringify(this.extractTopics(content)),
        sentiment: JSON.stringify({ label: 'neutral', score: 0 }),
        confidence: 0.7
      };

      return doc;

    } catch (error) {
      logger.warn(`Failed to process ${filePath}: ${error.message}`);
      return null;
    }
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
        doc.id, doc.source_type, doc.source_id, doc.title, doc.content,
        doc.content_summary, doc.published_date, doc.scraped_date,
        doc.source_metadata, doc.entities, doc.topics, doc.sentiment,
        doc.confidence, 'completed',
        (err) => {
          if (err) reject(err);
          else resolve();
        }
      );

      stmt.finalize();
    });
  }

  async processAll() {
    logger.info('📁 Scanning for metadata files...');
    const files = await this.findMetadataFiles();
    logger.info(`Found ${files.length} metadata files`);

    // Get already processed
    const existingIds = await new Promise((resolve, reject) => {
      this.db.all('SELECT id FROM documents', (err, rows) => {
        if (err) reject(err);
        else resolve(new Set(rows.map(r => r.id)));
      });
    });

    const newFiles = files.filter(f => {
      const parts = f.split('/');
      const date = `${parts[parts.length - 4]}_${parts[parts.length - 3]}_${parts[parts.length - 2]}`;
      const newspaper = parts[parts.length - 5];
      const id = `philip_${newspaper}_${date}`;
      return !existingIds.has(id);
    });

    logger.info(`New files to process: ${newFiles.length}`);

    for (let i = 0; i < newFiles.length; i++) {
      const file = newFiles[i];
      
      if ((i + 1) % 100 === 0 || i === 0) {
        logger.info(`[${i + 1}/${newFiles.length}] Processing... (${this.processed} success, ${this.failed} failed)`);
      }

      try {
        const doc = await this.processMetadataFile(file);
        if (doc) {
          await this.ingestDocument(doc);
          this.processed++;
        } else {
          this.failed++;
        }
      } catch (error) {
        logger.error(`Error processing ${file}:`, error.message);
        this.failed++;
      }
    }

    logger.info(`\n✅ Complete: ${this.processed} ingested, ${this.failed} failed`);
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
          fs.stat(CONFIG.sqlitePath).then(stats => {
            resolve({
              ...row,
              database_size_mb: (stats.size / 1024 / 1024).toFixed(2)
            });
          }).catch(() => resolve(row));
        }
      });
    });
  }

  close() {
    if (this.db) this.db.close();
  }
}

// Run
async function main() {
  const ingestor = new BulkIngestor();
  await ingestor.initialize();
  await ingestor.processAll();
  
  const stats = await ingestor.getStats();
  logger.info('\n📊 Final Statistics:');
  logger.info(JSON.stringify(stats, null, 2));
  
  ingestor.close();
}

main().catch(error => {
  logger.error('Fatal error:', error);
  process.exit(1);
});
