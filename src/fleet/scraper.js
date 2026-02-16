const { chromium } = require('playwright');
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');
const https = require('https');
const http = require('http');

// Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  dataDir: '/Volumes/Crucial X10/Decide9ja/data/archiving',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  memoryDir: '/Volumes/Crucial X10/Decide9ja/memory',
  
  // Fleet settings
  agentId: process.env.AGENT_ID || 'alpha',
  startYear: parseInt(process.env.START_YEAR) || 2026,
  endYear: parseInt(process.env.END_YEAR) || 1900,
  newspapers: (process.env.NEWSPAPERS || 'PM News').split(','),
  
  // Scraping settings
  maxConcurrent: 2,
  requestDelay: 1000,
  pageTimeout: 90000,
  retries: 5,
  retryDelay: 3000
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
      filename: path.join(CONFIG.logsDir, `fleet-${CONFIG.agentId}-error.log`), 
      level: 'error' 
    }),
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, `fleet-${CONFIG.agentId}.log`) 
    }),
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// Generate date range (BACKWARD - newest to oldest)
function* dateRangeBackward(startYear, endYear) {
  for (let year = startYear; year >= endYear; year--) {
    for (let month = 12; month >= 1; month--) {
      for (let day = 31; day >= 1; day--) {
        const date = new Date(year, month - 1, day);
        if (date.getMonth() !== month - 1) continue;
        yield {
          year: String(year),
          month: String(month).padStart(2, '0'),
          day: String(day).padStart(2, '0'),
          iso: `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
        };
      }
    }
  }
}

// Ensure directory exists
async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

// Download image with retry
async function downloadImage(url, outputPath, retries = 3) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    
    const attempt = (remainingRetries) => {
      const file = require('fs').createWriteStream(outputPath);
      
      client.get(url, { timeout: 30000 }, (response) => {
        if (response.statusCode === 200) {
          response.pipe(file);
          file.on('finish', () => {
            file.close();
            resolve({ success: true, size: file.bytesWritten });
          });
        } else if (response.statusCode === 302 || response.statusCode === 301) {
          // Follow redirect
          downloadImage(response.headers.location, outputPath, remainingRetries)
            .then(resolve)
            .catch(reject);
        } else {
          file.close();
          if (remainingRetries > 0) {
            setTimeout(() => attempt(remainingRetries - 1), 2000);
          } else {
            reject(new Error(`HTTP ${response.statusCode}`));
          }
        }
      }).on('error', (err) => {
        file.close();
        if (remainingRetries > 0) {
          setTimeout(() => attempt(remainingRetries - 1), 2000);
        } else {
          reject(err);
        }
      });
    };
    
    attempt(retries);
  });
}

// Load progress
async function loadProgress() {
  try {
    const file = path.join(CONFIG.memoryDir, `FLEET_${CONFIG.agentId}_PROGRESS.json`);
    const data = await fs.readFile(file, 'utf8');
    return JSON.parse(data);
  } catch {
    return {
      agentId: CONFIG.agentId,
      currentDate: null,
      processedDates: 0,
      totalImages: 0,
      totalArticles: 0,
      failedDates: [],
      lastRun: null
    };
  }
}

// Save progress
async function saveProgress(progress) {
  const file = path.join(CONFIG.memoryDir, `FLEET_${CONFIG.agentId}_PROGRESS.json`);
  progress.lastRun = new Date().toISOString();
  await fs.writeFile(file, JSON.stringify(progress, null, 2));
}

// Extract full content from an article page
async function extractArticleContent(page, articleUrl) {
  try {
    await page.goto(articleUrl, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1500);
    
    const content = await page.evaluate(() => {
      // Try multiple content selectors
      const selectors = [
        'article',
        '[data-testid="article-content"]',
        '.article-content',
        '.content',
        '.entry-content',
        'main',
        '.story',
        '.news-content',
        '[role="main"]'
      ];
      
      let articleText = '';
      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el) {
          articleText = el.innerText.trim();
          if (articleText.length > 100) break;
        }
      }
      
      // Fallback: get all paragraphs
      if (!articleText) {
        const paragraphs = document.querySelectorAll('p');
        articleText = Array.from(paragraphs).map(p => p.innerText).join('\n\n');
      }
      
      // Extract metadata
      const title = document.querySelector('h1, h2, .headline, [data-testid="headline"]')?.innerText?.trim() || '';
      const author = document.querySelector('[data-testid="author"], .author, .byline')?.innerText?.trim() || '';
      const publishDate = document.querySelector('time, [datetime], .date, .publish-date')?.getAttribute('datetime') || 
                         document.querySelector('time, [datetime], .date, .publish-date')?.innerText?.trim() || '';
      
      // Extract all images
      const images = Array.from(document.querySelectorAll('img')).map(img => ({
        url: img.src,
        alt: img.alt || '',
        caption: img.closest('figure')?.querySelector('figcaption')?.innerText || ''
      })).filter(img => img.url && !img.url.includes('data:'));
      
      return { title, author, publishDate, articleText, images };
    });
    
    return content;
  } catch (error) {
    logger.warn(`Failed to extract content from ${articleUrl}: ${error.message}`);
    return null;
  }
}

// Scrape a single date
async function scrapeDate(page, newspaper, dateObj, progress) {
  const { year, month, day, iso } = dateObj;
  const url = `https://archivi.ng/search?publication=${encodeURIComponent(newspaper)}&date=${iso}`;
  
  logger.info(`[${CONFIG.agentId}] Scraping: ${newspaper} ${iso}`);
  
  try {
    // Navigate to search page
    await page.goto(url, { 
      waitUntil: 'networkidle',
      timeout: CONFIG.pageTimeout 
    });
    
    await page.waitForTimeout(2000);
    
    // Extract search results with full content
    const searchResults = await page.evaluate(() => {
      const results = [];
      
      // Find all result cards
      const cards = document.querySelectorAll('[data-testid="result-card"], .result-item, .search-result, .issue-card, article');
      
      cards.forEach((card, idx) => {
        const img = card.querySelector('img');
        const link = card.querySelector('a');
        const title = card.querySelector('h3, h4, .title, h2')?.textContent?.trim() || '';
        const snippet = card.querySelector('p, .snippet, .excerpt, .description')?.textContent?.trim() || '';
        const date = card.querySelector('time, .date, [datetime]')?.textContent?.trim() || '';
        
        results.push({
          id: idx,
          title,
          snippet,
          date,
          imageUrl: img?.src || '',
          pageUrl: link?.href || '',
          alt: img?.alt || ''
        });
      });
      
      // Fallback: find any images in search results
      if (results.length === 0) {
        const allImages = document.querySelectorAll('img[src*="s3.af-south-1.amazonaws.com"], img[src*="resiz.ed"], img[src*="archivi"]');
        allImages.forEach((img, idx) => {
          const link = img.closest('a');
          results.push({
            id: idx,
            title: img.alt || '',
            snippet: '',
            date: '',
            imageUrl: img.src,
            pageUrl: link?.href || '',
            alt: img.alt || ''
          });
        });
      }
      
      return results;
    });
    
    if (searchResults.length === 0) {
      logger.info(`[${CONFIG.agentId}] No results found for ${iso}`);
      return { success: true, articles: 0, images: 0 };
    }
    
    // Create output directory
    const newspaperSlug = newspaper.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    const outputDir = path.join(CONFIG.dataDir, newspaperSlug, year, month, day);
    await ensureDir(outputDir);
    await ensureDir(path.join(outputDir, 'images'));
    
    // Process each result
    const articles = [];
    let downloadedImages = 0;
    
    for (let i = 0; i < searchResults.length; i++) {
      const result = searchResults[i];
      const articleId = `${iso}_${String(i).padStart(3, '0')}`;
      
      // Download image if available
      let localImagePath = null;
      if (result.imageUrl) {
        const ext = path.extname(new URL(result.imageUrl).pathname) || '.jpg';
        const imageFileName = `image_${articleId}${ext}`;
        localImagePath = path.join('images', imageFileName);
        
        try {
          await downloadImage(result.imageUrl, path.join(outputDir, localImagePath));
          downloadedImages++;
        } catch (err) {
          logger.warn(`Failed to download image for ${articleId}: ${err.message}`);
          localImagePath = null;
        }
      }
      
      // Extract full content if page URL exists
      let fullContent = null;
      if (result.pageUrl) {
        fullContent = await extractArticleContent(page, result.pageUrl);
        await page.waitForTimeout(500);
      }
      
      // Build article object
      const article = {
        id: articleId,
        newspaper,
        date: iso,
        searchDate: result.date,
        title: fullContent?.title || result.title,
        author: fullContent?.author || '',
        publishDate: fullContent?.publishDate || result.date,
        snippet: result.snippet,
        content: fullContent?.articleText || '',
        wordCount: fullContent?.articleText ? fullContent.articleText.split(/\s+/).length : 0,
        images: {
          searchResult: {
            url: result.imageUrl,
            alt: result.alt,
            localPath: localImagePath
          },
          article: fullContent?.images || []
        },
        sourceUrl: result.pageUrl,
        searchUrl: url,
        scrapedAt: new Date().toISOString(),
        agentId: CONFIG.agentId
      };
      
      articles.push(article);
      
      // Save individual article
      await fs.writeFile(
        path.join(outputDir, `article_${articleId}.json`),
        JSON.stringify(article, null, 2)
      );
    }
    
    // Save structured metadata
    const metadata = {
      newspaper,
      date: iso,
      url,
      scrapedAt: new Date().toISOString(),
      agentId: CONFIG.agentId,
      stats: {
        articlesFound: searchResults.length,
        articlesProcessed: articles.length,
        imagesDownloaded: downloadedImages,
        totalWordCount: articles.reduce((sum, a) => sum + (a.wordCount || 0), 0)
      },
      articles: articles.map(a => ({
        id: a.id,
        title: a.title,
        hasContent: a.content.length > 0,
        wordCount: a.wordCount,
        hasImages: !!(a.images.searchResult.localPath || a.images.article.length > 0)
      }))
    };
    
    await fs.writeFile(
      path.join(outputDir, 'metadata.json'),
      JSON.stringify(metadata, null, 2)
    );
    
    // Save full content archive
    await fs.writeFile(
      path.join(outputDir, 'articles_full.json'),
      JSON.stringify({ articles }, null, 2)
    );
    
    logger.info(`[${CONFIG.agentId}] ✓ Saved ${articles.length} articles, ${downloadedImages} images for ${iso}`);
    
    return { 
      success: true, 
      articles: articles.length, 
      images: downloadedImages,
      wordCount: metadata.stats.totalWordCount
    };
    
  } catch (error) {
    logger.error(`[${CONFIG.agentId}] ✗ Failed ${iso}:`, error.message);
    return { success: false, error: error.message };
  }
}

// Main scraping loop
async function main() {
  logger.info(`=== ARCHIVI.NG FLEET AGENT [${CONFIG.agentId}] STARTING ===`);
  logger.info(`Range: ${CONFIG.startYear} → ${CONFIG.endYear}`);
  logger.info(`Newspapers: ${CONFIG.newspapers.join(', ')}`);
  
  const progress = await loadProgress();
  logger.info(`Resuming: ${progress.processedDates} dates processed, ${progress.totalArticles} articles, ${progress.totalImages} images`);
  
  // Launch browser
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--disable-dev-shm-usage', '--disable-gpu', '--no-sandbox']
  });
  
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  let consecutiveErrors = 0;
  const maxConsecutiveErrors = 10;
  
  try {
    for (const newspaper of CONFIG.newspapers) {
      logger.info(`[${CONFIG.agentId}] Starting newspaper: ${newspaper}`);
      
      for (const dateObj of dateRangeBackward(CONFIG.startYear, CONFIG.endYear)) {
        // Skip if already processed
        if (progress.currentDate && dateObj.iso > progress.currentDate) {
          continue;
        }
        
        // Scrape this date with retry
        let result = null;
        let attempts = 0;
        
        while (attempts < CONFIG.retries && !result) {
          try {
            result = await scrapeDate(page, newspaper, dateObj, progress);
          } catch (err) {
            attempts++;
            logger.warn(`Attempt ${attempts} failed for ${dateObj.iso}: ${err.message}`);
            await page.waitForTimeout(CONFIG.retryDelay * attempts);
          }
        }
        
        if (result && result.success) {
          progress.processedDates++;
          progress.totalArticles += result.articles || 0;
          progress.totalImages += result.images || 0;
          consecutiveErrors = 0;
        } else {
          progress.failedDates.push({
            newspaper,
            date: dateObj.iso,
            error: result?.error || 'Unknown error'
          });
          consecutiveErrors++;
          
          if (consecutiveErrors >= maxConsecutiveErrors) {
            logger.error(`[${CONFIG.agentId}] Too many errors, pausing newspaper ${newspaper}...`);
            break;
          }
        }
        
        progress.currentDate = dateObj.iso;
        await saveProgress(progress);
        
        // Delay between requests
        await page.waitForTimeout(CONFIG.requestDelay);
      }
    }
    
  } catch (error) {
    logger.error(`[${CONFIG.agentId}] Fatal error:`, error);
  } finally {
    await browser.close();
  }
  
  logger.info(`[${CONFIG.agentId}] === COMPLETE ===`);
  logger.info(`Dates processed: ${progress.processedDates}`);
  logger.info(`Total articles: ${progress.totalArticles}`);
  logger.info(`Total images: ${progress.totalImages}`);
  logger.info(`Failed: ${progress.failedDates.length}`);
}

// Run
if (require.main === module) {
  main().catch(error => {
    logger.error('Unhandled error:', error);
    process.exit(1);
  });
}

module.exports = { main, scrapeDate };
