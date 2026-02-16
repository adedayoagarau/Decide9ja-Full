/**
 * Decide9ja API Server
 * Serves SQLite RAG + Syncs recent data to Supabase
 * Hybrid: Local (all data) + Cloud (recent 2 years)
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { SQLiteRAG } = require('../ezekiel/sqlite-rag');
const winston = require('winston');
const path = require('path');

// Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: path.join('/Volumes/Crucial X10/Decide9ja/logs', 'api.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Initialize RAG
const rag = new SQLiteRAG();
let ragInitialized = false;

async function initialize() {
  await rag.initialize();
  ragInitialized = true;
  logger.info('✅ API Server RAG initialized');
}

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    ragInitialized,
    timestamp: new Date().toISOString()
  });
});

// Search endpoint
app.get('/api/search', async (req, res) => {
  try {
    const { q, limit = 10, from, to, newspaper } = req.query;
    
    if (!q) {
      return res.status(400).json({ error: 'Query parameter "q" required' });
    }

    const filters = {};
    if (newspaper) filters.newspaper = newspaper;
    if (from) filters.date_from = from;
    if (to) filters.date_to = to;

    const results = await rag.search(q, { 
      limit: parseInt(limit), 
      filters 
    });

    res.json({
      query: q,
      count: results.count,
      results: results.results.map(doc => ({
        id: doc.id,
        title: doc.title,
        date: doc.published_date,
        newspaper: JSON.parse(doc.source_metadata || '{}').newspaper,
        summary: doc.content_summary?.slice(0, 200),
        sentiment: JSON.parse(doc.sentiment || '{}').label
      }))
    });

  } catch (error) {
    logger.error('Search error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get document by ID
app.get('/api/documents/:id', async (req, res) => {
  try {
    const doc = await rag.getById(req.params.id);
    if (!doc) {
      return res.status(404).json({ error: 'Document not found' });
    }

    res.json({
      id: doc.id,
      title: doc.title,
      content: doc.content,
      date: doc.published_date,
      source_metadata: JSON.parse(doc.source_metadata || '{}'),
      entities: JSON.parse(doc.entities || '{}'),
      topics: JSON.parse(doc.topics || '[]'),
      sentiment: JSON.parse(doc.sentiment || '{}')
    });

  } catch (error) {
    logger.error('Get document error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get documents by date range
app.get('/api/documents', async (req, res) => {
  try {
    const { from, to, newspaper, limit = 100 } = req.query;
    
    let results;
    if (from && to) {
      results = await rag.getByDateRange(from, to, parseInt(limit));
    } else if (newspaper) {
      results = await rag.getByNewspaper(newspaper, parseInt(limit));
    } else {
      return res.status(400).json({ 
        error: 'Provide either (from + to) dates or newspaper parameter' 
      });
    }

    res.json({
      count: results.length,
      results: results.map(doc => ({
        id: doc.id,
        title: doc.title,
        date: doc.published_date,
        newspaper: JSON.parse(doc.source_metadata || '{}').newspaper
      }))
    });

  } catch (error) {
    logger.error('List documents error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get statistics
app.get('/api/stats', async (req, res) => {
  try {
    const stats = await rag.getStats();
    res.json(stats);
  } catch (error) {
    logger.error('Stats error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Advanced query (by entity, topic, etc.)
app.post('/api/query', async (req, res) => {
  try {
    const { entities, topics, dateRange, sentiment } = req.body;
    
    // Build dynamic SQL query
    let sql = 'SELECT * FROM documents WHERE 1=1';
    const params = [];
    
    if (entities && entities.length > 0) {
      sql += ` AND EXISTS (
        SELECT 1 FROM json_each(entities) 
        WHERE json_extract(value, '$.name') IN (${entities.map(() => '?').join(',')})
      )`;
      params.push(...entities);
    }
    
    if (topics && topics.length > 0) {
      sql += ` AND EXISTS (
        SELECT 1 FROM json_each(topics) 
        WHERE json_extract(value, '$.topic') IN (${topics.map(() => '?').join(',')})
      )`;
      params.push(...topics);
    }
    
    if (dateRange) {
      sql += ' AND published_date BETWEEN ? AND ?';
      params.push(dateRange.from, dateRange.to);
    }
    
    if (sentiment) {
      sql += " AND json_extract(sentiment, '$.label') = ?";
      params.push(sentiment);
    }
    
    sql += ' ORDER BY published_date DESC LIMIT 100';
    
    const results = await new Promise((resolve, reject) => {
      rag.db.all(sql, params, (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });

    res.json({
      count: results.length,
      results: results.map(doc => ({
        id: doc.id,
        title: doc.title,
        date: doc.published_date,
        newspaper: JSON.parse(doc.source_metadata || '{}').newspaper
      }))
    });

  } catch (error) {
    logger.error('Query error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Ingest new document (for webhook/push)
app.post('/api/ingest', async (req, res) => {
  try {
    const doc = req.body;
    const result = await rag.ingestDocument(doc);
    
    res.json({
      success: result.success,
      id: doc.id
    });

  } catch (error) {
    logger.error('Ingest error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'Decide9ja RAG API',
    version: '2.0.0',
    endpoints: [
      'GET  /health',
      'GET  /api/search?q=query&limit=10',
      'GET  /api/documents/:id',
      'GET  /api/documents?from=2021-01-01&to=2021-12-31',
      'GET  /api/documents?newspaper=pmnews',
      'GET  /api/stats',
      'POST /api/query',
      'POST /api/ingest'
    ]
  });
});

// Error handler
app.use((err, req, res, next) => {
  logger.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
initialize().then(() => {
  app.listen(PORT, () => {
    logger.info(`🚀 API Server running on port ${PORT}`);
    logger.info(`📚 Document database ready`);
  });
}).catch(error => {
  logger.error('Failed to initialize:', error);
  process.exit(1);
});

module.exports = app;
