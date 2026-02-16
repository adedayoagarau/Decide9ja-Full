const fs = require('fs').promises;
const path = require('path');
const { createWorker } = require('tesseract.js');
const winston = require('winston');
const https = require('https');
const http = require('http');

// Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  rawDir: '/Volumes/Crucial X10/Decide9ja/data/archiving',
  processedDir: '/Volumes/Crucial X10/Decide9ja/data/processed',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  memoryDir: '/Volumes/Crucial X10/Decide9ja/memory',
  imagesDir: '/Volumes/Crucial X10/Decide9ja/data/images',
  
  // Processing settings - smaller batches for memory efficiency
  batchSize: 1, // Process 1 file at a time
  ocrLanguage: 'eng',
  minOcrConfidence: 0.6,
  maxImageSize: 50 * 1024 * 1024,
  
  // Memory management
  filesBeforeRestart: 10, // Restart worker every N files
  
  // Topic keywords
  topics: {
    politics: ['election', 'vote', 'government', 'president', 'senate', 'party', 'apc', 'pdp', 'governor', 'candidate', 'campaign', 'ballot', 'poll'],
    crime: ['police', 'court', 'judge', 'prison', 'theft', 'robbery', 'murder', 'arrest', 'crime', 'criminal', 'suspect', 'investigation', 'jail'],
    economy: ['market', 'price', 'naira', 'dollar', 'trade', 'business', 'company', 'economy', 'finance', 'bank', 'money', 'investment', 'revenue'],
    infrastructure: ['road', 'power', 'electricity', 'water', 'bridge', 'building', 'project', 'construction', 'transport', 'highway', 'dam'],
    health: ['hospital', 'doctor', 'disease', 'health', 'medical', 'covid', 'malaria', 'patient', 'nurse', 'clinic', 'medicine', 'treatment'],
    education: ['school', 'university', 'student', 'teacher', 'exam', 'education', 'graduate', 'college', 'academic', 'scholarship', 'learning'],
    sports: ['football', 'match', 'team', 'player', 'premier league', 'epl', 'super eagles', 'soccer', 'goal', 'stadium', 'coach', 'tournament'],
    entertainment: ['music', 'movie', 'actor', 'celebrity', 'nollywood', 'entertainment', 'film', 'album', 'concert', 'artist', 'comedian'],
    social: ['community', 'culture', 'religion', 'church', 'mosque', 'tradition', 'family', 'marriage', 'wedding', 'festival', 'ceremony']
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
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, 'judas-error.log'), 
      level: 'error' 
    }),
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, 'judas.log') 
    }),
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// Download image
async function downloadImage(url, outputPath) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    
    const request = client.get(url, { timeout: 30000 }, (response) => {
      if (response.statusCode === 301 || response.statusCode === 302) {
        downloadImage(response.headers.location, outputPath)
          .then(resolve)
          .catch(reject);
        return;
      }
      
      if (response.statusCode !== 200) {
        reject(new Error(`Failed: ${response.statusCode}`));
        return;
      }
      
      const fileStream = require('fs').createWriteStream(outputPath);
      response.pipe(fileStream);
      
      fileStream.on('finish', () => {
        fileStream.close();
        resolve(outputPath);
      });
      
      fileStream.on('error', reject);
    });
    
    request.on('error', reject);
    request.on('timeout', () => {
      request.destroy();
      reject(new Error('Timeout'));
    });
  });
}

// OCR with worker management
async function ocrImage(imagePath, worker) {
  try {
    const { data: { text, confidence } } = await worker.recognize(imagePath);
    const words = text.split(/\s+/).filter(w => w.length > 0).length;
    return { text, confidence, words };
  } catch (error) {
    logger.error(`OCR failed: ${error.message}`);
    return { text: '', confidence: 0, words: 0 };
  }
}

// Create new worker
async function createOcrWorker() {
  logger.info('Creating new Tesseract worker...');
  return await createWorker('eng', 1, {
    logger: m => {
      if (m.status === 'recognizing text') {
        logger.debug(`OCR: ${Math.round(m.progress * 100)}%`);
      }
    }
  });
}

// Extract topics
function extractTopics(text) {
  if (!text) return [];
  const text_lower = text.toLowerCase();
  const results = [];
  
  for (const [topic, keywords] of Object.entries(CONFIG.topics)) {
    let score = 0;
    for (const keyword of keywords) {
      const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
      const matches = text_lower.match(regex);
      if (matches) score += matches.length;
    }
    if (score > 0) {
      results.push({ topic, confidence: Math.min(score / 3, 1) });
    }
  }
  
  return results.sort((a, b) => b.confidence - a.confidence).slice(0, 5);
}

// Extract entities
function extractEntities(text) {
  const entities = { people: [], organizations: [], locations: [], dates: [] };
  if (!text) return entities;
  
  // People patterns
  const peoplePattern = /\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Chief|Alhaji|Otunba|Sir|Lady)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b/g;
  let match;
  while ((match = peoplePattern.exec(text)) !== null) {
    const name = match[2];
    if (!entities.people.includes(name)) entities.people.push(name);
  }
  
  // Organizations
  const orgPattern = /\b([A-Z]{3,})\b/g;
  while ((match = orgPattern.exec(text)) !== null) {
    if (match[1].length > 2 && !match[1].match(/^(PM|AM|PDF|URL|HTTP|HTTPS|WWW)$/)) {
      if (!entities.organizations.includes(match[1])) {
        entities.organizations.push(match[1]);
      }
    }
  }
  
  // Locations
  const locations = ['Lagos', 'Abuja', 'Kano', 'Ibadan', 'Kaduna', 'Port Harcourt'];
  locations.forEach(loc => {
    if (text.includes(loc) && !entities.locations.includes(loc)) {
      entities.locations.push(loc);
    }
  });
  
  return entities;
}

// Sentiment analysis
function analyzeSentiment(text) {
  if (!text) return 'neutral';
  const positive = ['celebrate', 'win', 'success', 'launch', 'improve', 'growth', 'award'];
  const negative = ['kill', 'death', 'accident', 'attack', 'violence', 'crime', 'corruption'];
  
  const text_lower = text.toLowerCase();
  let posCount = positive.filter(w => text_lower.includes(w)).length;
  let negCount = negative.filter(w => text_lower.includes(w)).length;
  
  if (posCount > negCount) return 'positive';
  if (negCount > posCount) return 'negative';
  return 'neutral';
}

// Process single file
async function processMetadataFile(metadataPath, newspaper, date, worker) {
  try {
    const data = JSON.parse(await fs.readFile(metadataPath, 'utf8'));
    
    if (!data.issues || data.issues.length === 0) {
      return { processed: 0, ocrCompleted: 0, words: 0 };
    }
    
    const processed = [];
    
    for (let i = 0; i < data.issues.length; i++) {
      const issue = data.issues[i];
      const imageFilename = `${newspaper}_${date.replace(/-/g, '')}_${i}.jpg`;
      const imagePath = path.join(CONFIG.imagesDir, imageFilename);
      
      let ocrResult = { text: '', confidence: 0, words: 0 };
      let imageDownloaded = false;
      
      if (issue.imageUrl) {
        try {
          await downloadImage(issue.imageUrl, imagePath);
          imageDownloaded = true;
          ocrResult = await ocrImage(imagePath, worker);
        } catch (error) {
          logger.warn(`Image failed: ${error.message}`);
        }
      }
      
      const fullText = [issue.title || '', ocrResult.text].join(' ').trim();
      const topics = extractTopics(fullText);
      const entities = extractEntities(fullText);
      const sentiment = analyzeSentiment(fullText);
      
      processed.push({
        url: issue.url,
        date: issue.date,
        headline: issue.title || '',
        fullText: fullText.slice(0, 3000),
        ocrText: ocrResult.text.slice(0, 2000),
        ocrConfidence: ocrResult.confidence,
        ocrWordCount: ocrResult.words,
        imageUrl: issue.imageUrl,
        imageDownloaded,
        topics: topics.slice(0, 3),
        entities: {
          people: entities.people.slice(0, 10),
          organizations: entities.organizations.slice(0, 10),
          locations: entities.locations.slice(0, 5)
        },
        sentiment,
        processedAt: new Date().toISOString()
      });
    }
    
    // Save
    const outputDir = path.join(CONFIG.processedDir, 'text', newspaper, date.slice(0, 4), date.slice(5, 7));
    await fs.mkdir(outputDir, { recursive: true });
    
    await fs.writeFile(
      path.join(outputDir, `${date.slice(8, 10)}_processed.json`),
      JSON.stringify({
        newspaper,
        date,
        issueCount: processed.length,
        ocrCompleted: processed.filter(p => p.ocrWordCount > 0).length,
        totalWordCount: processed.reduce((sum, p) => sum + p.ocrWordCount, 0),
        issues: processed
      }, null, 2)
    );
    
    return {
      processed: processed.length,
      ocrCompleted: processed.filter(p => p.ocrWordCount > 0).length,
      words: processed.reduce((sum, p) => sum + p.ocrWordCount, 0)
    };
    
  } catch (error) {
    logger.error(`Process error: ${error.message}`);
    return { processed: 0, error: error.message };
  }
}

// Load progress
async function loadProgress() {
  try {
    const file = path.join(CONFIG.memoryDir, 'JUDAS_PROGRESS.json');
    const data = await fs.readFile(file, 'utf8');
    return JSON.parse(data);
  } catch {
    return {
      currentNewspaper: 'pmnews',
      processedCount: 0,
      ocrCompleted: 0,
      lastRun: null
    };
  }
}

// Save progress
async function saveProgress(progress) {
  const file = path.join(CONFIG.memoryDir, 'JUDAS_PROGRESS.json');
  progress.lastRun = new Date().toISOString();
  await fs.writeFile(file, JSON.stringify(progress, null, 2));
}

// Get metadata files
async function getMetadataFiles(newspaper) {
  const files = [];
  const rawDir = path.join(CONFIG.rawDir, newspaper);
  
  try {
    const years = await fs.readdir(rawDir);
    for (const year of years) {
      const yearPath = path.join(rawDir, year);
      const months = await fs.readdir(yearPath);
      for (const month of months) {
        const monthPath = path.join(yearPath, month);
        const days = await fs.readdir(monthPath);
        for (const day of days) {
          const metadataPath = path.join(monthPath, day, 'metadata.json');
          try {
            await fs.access(metadataPath);
            files.push({
              path: metadataPath,
              newspaper,
              date: `${year}-${month}-${day}`
            });
          } catch {}
        }
      }
    }
  } catch (error) {
    logger.error(`Error reading directory: ${error.message}`);
  }
  
  return files.sort();
}

// Main
async function main() {
  logger.info('=== JUDAS OCR - MEMORY EFFICIENT MODE ===');
  
  await fs.mkdir(CONFIG.processedDir, { recursive: true });
  await fs.mkdir(CONFIG.imagesDir, { recursive: true });
  await fs.mkdir(CONFIG.memoryDir, { recursive: true });
  
  const progress = await loadProgress();
  logger.info(`Resuming: ${progress.currentNewspaper}, processed: ${progress.processedCount}, OCR: ${progress.ocrCompleted || 0}`);
  
  const metadataFiles = await getMetadataFiles(progress.currentNewspaper);
  const startIndex = progress.processedCount || 0;
  const remainingFiles = metadataFiles.slice(startIndex);
  
  logger.info(`Found ${metadataFiles.length} total files, ${remainingFiles.length} remaining`);
  
  let worker = await createOcrWorker();
  let processed = startIndex;
  let ocrCompleted = progress.ocrCompleted || 0;
  let totalWords = 0;
  let filesSinceRestart = 0;
  
  for (let i = 0; i < remainingFiles.length; i++) {
    const file = remainingFiles[i];
    
    logger.info(`[${i + 1}/${remainingFiles.length}] Processing: ${file.date}`);
    
    const result = await processMetadataFile(file.path, file.newspaper, file.date, worker);
    
    if (!result.error) {
      processed++;
      ocrCompleted += result.ocrCompleted;
      totalWords += result.words;
    }
    
    // Update progress
    progress.processedCount = processed;
    progress.ocrCompleted = ocrCompleted;
    await saveProgress(progress);
    
    // Restart worker periodically to free memory
    filesSinceRestart++;
    if (filesSinceRestart >= CONFIG.filesBeforeRestart) {
      logger.info('Restarting worker to free memory...');
      await worker.terminate();
      worker = await createOcrWorker();
      filesSinceRestart = 0;
      
      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }
    }
    
    // Small delay
    await new Promise(r => setTimeout(r, 500));
  }
  
  await worker.terminate();
  
  logger.info(`\n✅ Complete: ${processed} files, ${ocrCompleted} OCR'd, ${totalWords} words`);
}

if (require.main === module) {
  main().catch(error => {
    logger.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { main };
