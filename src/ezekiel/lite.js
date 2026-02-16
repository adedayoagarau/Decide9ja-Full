/**
 * Ezekiel Lite - Simplified ingestion without external dependencies
 * Processes Judas OCR output and prepares for Supabase
 */

const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

// Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  processedDir: '/Volumes/Crucial X10/Decide9ja/data/processed',
  outputDir: '/Volumes/Crucial X10/Decide9ja/data/unified',
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
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'ezekiel-lite.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

// Simple entity extraction
function extractEntities(text) {
  const entities = { people: [], organizations: [], locations: [] };
  if (!text) return entities;
  
  // People pattern
  const peopleMatches = text.match(/\b(Mr\.?|Mrs\.?|Dr\.?|Chief|Alhaji|Senator|Governor|President)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g);
  if (peopleMatches) {
    entities.people = [...new Set(peopleMatches.map(m => m.replace(/^(Mr\.?|Mrs\.?|Dr\.?|Chief|Alhaji|Senator|Governor|President)\s+/, '')))];
  }
  
  // Organizations
  const orgMatches = text.match(/\b(INEC|APC|PDP|LP|NNPP|NLC|TUC|CBN|NNPC|EFCC|ICPC|NBA)\b/g);
  if (orgMatches) {
    entities.organizations = [...new Set(orgMatches)];
  }
  
  // Locations
  const locMatches = text.match(/\b(Lagos|Abuja|Kano|Ibadan|Kaduna|Port Harcourt|Enugu|Benin|Jos|Ilorin)\b/g);
  if (locMatches) {
    entities.locations = [...new Set(locMatches)];
  }
  
  return entities;
}

// Extract topics
function extractTopics(text) {
  const topics = [];
  const text_lower = text.toLowerCase();
  
  const keywords = {
    election: ['election', 'vote', 'ballot', 'poll', 'campaign', 'candidate'],
    economy: ['economy', 'naira', 'dollar', 'budget', 'finance', 'market', 'trade'],
    security: ['police', 'security', 'crime', 'violence', 'terrorism', 'banditry'],
    infrastructure: ['road', 'power', 'electricity', 'water', 'bridge'],
    health: ['health', 'hospital', 'doctor', 'disease', 'covid', 'medicine'],
    education: ['school', 'university', 'student', 'education', 'academic']
  };
  
  for (const [topic, words] of Object.entries(keywords)) {
    let score = 0;
    words.forEach(word => {
      const matches = text_lower.match(new RegExp(`\\b${word}\\b`, 'g'));
      if (matches) score += matches.length;
    });
    if (score > 0) topics.push({ topic, confidence: Math.min(score / 2, 1) });
  }
  
  return topics.sort((a, b) => b.confidence - a.confidence).slice(0, 5);
}

// Sentiment analysis
function analyzeSentiment(text) {
  if (!text) return { label: 'neutral', score: 0 };
  
  const positive = ['win', 'success', 'improve', 'growth', 'achieve', 'progress', 'development', 'support'];
  const negative = ['kill', 'death', 'attack', 'crisis', 'problem', 'fail', 'corruption', 'scandal', 'accident'];
  
  const text_lower = text.toLowerCase();
  const posCount = positive.filter(w => text_lower.includes(w)).length;
  const negCount = negative.filter(w => text_lower.includes(w)).length;
  
  if (posCount > negCount) return { label: 'positive', score: posCount - negCount };
  if (negCount > posCount) return { label: 'negative', score: negCount - posCount };
  return { label: 'neutral', score: 0 };
}

// Process a single file
async function processFile(filePath) {
  try {
    const data = JSON.parse(await fs.readFile(filePath, 'utf8'));
    
    if (!data.issues || data.issues.length === 0) {
      return null;
    }
    
    // Combine all content
    const fullContent = data.issues.map(issue => {
      return [
        issue.headline || issue.title || '',
        issue.snippet || '',
        issue.content || '',
        issue.ocrText || ''
      ].filter(Boolean).join('\n\n');
    }).join('\n\n---\n\n');
    
    // Extract metadata
    const entities = extractEntities(fullContent);
    const topics = extractTopics(fullContent);
    const sentiment = analyzeSentiment(fullContent);
    
    // Create unified document
    const unifiedDoc = {
      id: `judas_${data.newspaper?.toLowerCase().replace(/\s+/g, '_')}_${data.date}`,
      source_type: 'newspaper',
      source_id: data.date,
      title: data.issues[0]?.headline || data.issues[0]?.title || `${data.newspaper} - ${data.date}`,
      content: fullContent.slice(0, 10000), // Limit size
      content_summary: fullContent.slice(0, 500),
      published_date: data.date,
      scraped_date: new Date().toISOString(),
      source_metadata: {
        newspaper: data.newspaper,
        issue_count: data.issueCount,
        original_file: filePath
      },
      entities,
      topics,
      sentiment,
      confidence: 0.8,
      processing_status: 'completed',
      created_at: new Date().toISOString()
    };
    
    return unifiedDoc;
    
  } catch (error) {
    logger.error(`Error processing ${filePath}:`, error.message);
    return null;
  }
}

// Main loop
async function main() {
  logger.info('=== EZEKIEL LITE - Starting... ===');
  
  // Ensure output directory
  await fs.mkdir(CONFIG.outputDir, { recursive: true });
  
  // Find all processed files
  const files = [];
  
  async function scanDir(dir) {
    try {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await scanDir(fullPath);
        } else if (entry.name.endsWith('_processed.json')) {
          files.push(fullPath);
        }
      }
    } catch (error) {
      logger.warn(`Cannot read directory ${dir}:`, error.message);
    }
  }
  
  await scanDir(CONFIG.processedDir);
  logger.info(`Found ${files.length} files to process`);
  
  // Process files
  let processed = 0;
  let failed = 0;
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    logger.info(`[${i + 1}/${files.length}] Processing: ${path.basename(file)}`);
    
    const doc = await processFile(file);
    
    if (doc) {
      // Save unified document
      const outputPath = path.join(CONFIG.outputDir, `${doc.id}.json`);
      await fs.writeFile(outputPath, JSON.stringify(doc, null, 2));
      processed++;
    } else {
      failed++;
    }
    
    // Progress log every 50 files
    if ((i + 1) % 50 === 0) {
      logger.info(`📊 Progress: ${i + 1}/${files.length} (${processed} success, ${failed} failed)`);
    }
  }
  
  logger.info(`\n✅ Complete: ${processed} files processed, ${failed} failed`);
  logger.info(`📁 Output: ${CONFIG.outputDir}`);
  
  // Generate catalog
  await generateCatalog();
}

// Generate catalog summary
async function generateCatalog() {
  logger.info('Generating catalog...');
  
  const files = await fs.readdir(CONFIG.outputDir);
  const documents = [];
  
  for (const file of files.filter(f => f.endsWith('.json'))) {
    try {
      const data = JSON.parse(await fs.readFile(path.join(CONFIG.outputDir, file), 'utf8'));
      documents.push(data);
    } catch {}
  }
  
  const catalog = {
    generated_at: new Date().toISOString(),
    total_documents: documents.length,
    by_newspaper: {},
    by_topic: {},
    by_sentiment: { positive: 0, negative: 0, neutral: 0 },
    top_entities: {
      people: {},
      organizations: {},
      locations: {}
    }
  };
  
  for (const doc of documents) {
    // By newspaper
    const newspaper = doc.source_metadata?.newspaper || 'unknown';
    catalog.by_newspaper[newspaper] = (catalog.by_newspaper[newspaper] || 0) + 1;
    
    // By sentiment
    if (doc.sentiment?.label) {
      catalog.by_sentiment[doc.sentiment.label]++;
    }
    
    // By topic
    for (const topic of doc.topics || []) {
      catalog.by_topic[topic.topic] = (catalog.by_topic[topic.topic] || 0) + 1;
    }
    
    // Entities
    for (const person of doc.entities?.people || []) {
      catalog.top_entities.people[person] = (catalog.top_entities.people[person] || 0) + 1;
    }
    for (const org of doc.entities?.organizations || []) {
      catalog.top_entities.organizations[org] = (catalog.top_entities.organizations[org] || 0) + 1;
    }
    for (const loc of doc.entities?.locations || []) {
      catalog.top_entities.locations[loc] = (catalog.top_entities.locations[loc] || 0) + 1;
    }
  }
  
  // Sort top entities
  catalog.top_entities.people = Object.entries(catalog.top_entities.people)
    .sort((a, b) => b[1] - a[1]).slice(0, 30);
  catalog.top_entities.organizations = Object.entries(catalog.top_entities.organizations)
    .sort((a, b) => b[1] - a[1]).slice(0, 20);
  catalog.top_entities.locations = Object.entries(catalog.top_entities.locations)
    .sort((a, b) => b[1] - a[1]).slice(0, 15);
  
  await fs.writeFile(
    path.join(CONFIG.outputDir, 'catalog.json'),
    JSON.stringify(catalog, null, 2)
  );
  
  logger.info(`📚 Catalog: ${catalog.total_documents} documents`);
  logger.info(`📰 By newspaper:`, catalog.by_newspaper);
  logger.info(`😊 Sentiment:`, catalog.by_sentiment);
  logger.info(`🏷️ Top topics:`, Object.entries(catalog.by_topic).slice(0, 5));
}

main().catch(error => {
  logger.error('Fatal error:', error);
  process.exit(1);
});
