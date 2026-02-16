const { chromium } = require('playwright');
const fs = require('fs').promises;
const path = require('path');

// Fleet Agent RHO - Egbe Omo Oduduwa Scraper
const CONFIG = {
  newspaper: { name: 'Egbe Omo Oduduwa', slug: 'Egbe%20Omo%20Oduduwa', id: 'egbe_omo_oduduwa' },
  dataDir: '/Volumes/Crucial X10/Decide9ja/data/archiving/egbe_omo_oduduwa',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  memoryDir: '/Users/adedayoagarau/.openclaw/workspace/memory',
  
  // Date range - scraping backwards
  startDate: '2002-12-02',  // Resume from here
  endDate: '1999-01-01',    // Go back to beginning of 1999
  
  // Retry and timeout settings
  maxRetries: 3,
  retryDelay: 3000,
  pageTimeout: 60000,
  headless: true,
  
  // Progress reporting interval (30 minutes in ms)
  progressInterval: 30 * 60 * 1000,
};

// Simple logger
async function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  const logEntry = { timestamp, level, message, ...data };
  const logLine = JSON.stringify(logEntry);
  
  // Console output
  const prefix = level === 'ERROR' ? '❌' : level === 'WARN' ? '⚠️' : level === 'SUCCESS' ? '✅' : 'ℹ️';
  console.log(`${prefix} [${timestamp}] ${message}`);
  
  // Write to log file
  await fs.appendFile(
    path.join(CONFIG.logsDir, 'fleet-rho.log'),
    logLine + '\n'
  );
}

// Progress tracking
async function loadProgress() {
  try {
    const progressFile = path.join(CONFIG.memoryDir, 'FLEET_rho_PROGRESS.json');
    const data = await fs.readFile(progressFile, 'utf8');
    return JSON.parse(data);
  } catch {
    return {
      newspaper: 'Egbe Omo Oduduwa',
      currentDate: CONFIG.startDate,
      endDate: CONFIG.endDate,
      totalDaysScraped: 0,
      totalArticlesFound: 0,
      totalImagesDownloaded: 0,
      errors: [],
      startedAt: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
      status: 'running'
    };
  }
}

async function saveProgress(progress) {
  progress.lastUpdated = new Date().toISOString();
  await fs.writeFile(
    path.join(CONFIG.memoryDir, 'FLEET_rho_PROGRESS.json'),
    JSON.stringify(progress, null, 2)
  );
}

// Download image
async function downloadImage(context, imageUrl, outputPath) {
  try {
    const page = await context.newPage();
    const response = await page.goto(imageUrl, { timeout: 30000 });
    if (response) {
      const buffer = await response.body();
      await fs.writeFile(outputPath, buffer);
      await page.close();
      return true;
    }
    await page.close();
    return false;
  } catch (error) {
    return false;
  }
}

// Extract full article content
async function extractArticleContent(page, articleUrl) {
  try {
    await page.goto(articleUrl, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    
    const content = await page.evaluate(() => {
      // Try multiple selectors for article content
      const selectors = [
        'article',
        '[class*="article"]',
        '[class*="content"]',
        '.prose',
        '[role="main"]',
        'main'
      ];
      
      for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el && el.textContent.trim().length > 100) {
          return {
            title: document.querySelector('h1, [class*="title"]')?.textContent?.trim() || '',
            text: el.innerText.trim(),
            html: el.innerHTML
          };
        }
      }
      
      // Fallback to body text
      return {
        title: document.querySelector('h1')?.textContent?.trim() || document.title,
        text: document.body.innerText.trim().substring(0, 10000),
        html: null
      };
    });
    
    return content;
  } catch (error) {
    return { title: '', text: '', html: null, error: error.message };
  }
}

// Scrape a single date
async function scrapeDate(browser, date, progress) {
  const url = `https://archivi.ng/search?publication=${CONFIG.newspaper.slug}&date=${date}`;
  
  let retries = 0;
  while (retries < CONFIG.maxRetries) {
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      viewport: { width: 1920, height: 1080 }
    });
    
    const page = await context.newPage();
    
    try {
      await log('INFO', `Scraping ${date}`, { url, attempt: retries + 1 });
      
      await page.goto(url, { waitUntil: 'networkidle', timeout: CONFIG.pageTimeout });
      await page.waitForTimeout(5000);
      
      // Find article links
      const articles = await page.evaluate(() => {
        const links = Array.from(document.querySelectorAll('a[href*="/read/"], a[href*="/article/"]'));
        return links.map(a => ({
          url: a.href,
          title: a.textContent?.trim() || 'Untitled'
        })).filter(a => a.title.length > 0);
      });
      
      if (articles.length === 0) {
        await log('INFO', `No articles found for ${date}`);
        await context.close();
        return { success: true, articlesFound: 0, articles: [] };
      }
      
      await log('INFO', `Found ${articles.length} articles for ${date}`);
      
      // Create date directory
      const dateDir = path.join(CONFIG.dataDir, date.replace(/-/g, '/'));
      await fs.mkdir(dateDir, { recursive: true });
      
      const processedArticles = [];
      let imagesDownloaded = 0;
      
      // Process each article
      for (let i = 0; i < articles.length; i++) {
        const article = articles[i];
        const articleId = `${date}_${String(i).padStart(3, '0')}`;
        
        try {
          // Extract full content
          const content = await extractArticleContent(page, article.url);
          
          // Save article
          const articleData = {
            id: articleId,
            date,
            title: content.title || article.title,
            url: article.url,
            content: content.text,
            html: content.html,
            scrapedAt: new Date().toISOString(),
            agentId: 'rho'
          };
          
          await fs.writeFile(
            path.join(dateDir, `article_${articleId}.json`),
            JSON.stringify(articleData, null, 2)
          );
          
          // Look for images
          const imageUrls = await page.evaluate(() => {
            return Array.from(document.querySelectorAll('img[src*="archivi.ng"], img[src*="newspaper"], img[src*="/image/"]'))
              .map(img => img.src)
              .filter(src => src && src.length > 0);
          });
          
          // Download images
          for (let j = 0; j < imageUrls.length; j++) {
            const imgUrl = imageUrls[j];
            const ext = path.extname(imgUrl) || '.jpg';
            const imgPath = path.join(dateDir, `image_${articleId}_${j}${ext}`);
            const success = await downloadImage(context, imgUrl, imgPath);
            if (success) imagesDownloaded++;
          }
          
          processedArticles.push({
            id: articleId,
            title: articleData.title,
            hasContent: content.text.length > 0,
            wordCount: content.text.split(/\s+/).length,
            hasImages: imageUrls.length > 0
          });
          
        } catch (error) {
          await log('WARN', `Failed to process article ${articleId}`, { error: error.message });
        }
      }
      
      // Save metadata for this date
      const metadata = {
        newspaper: CONFIG.newspaper.name,
        date,
        url,
        scrapedAt: new Date().toISOString(),
        agentId: 'rho',
        stats: {
          articlesFound: articles.length,
          articlesProcessed: processedArticles.length,
          imagesDownloaded,
          totalWordCount: processedArticles.reduce((sum, a) => sum + a.wordCount, 0)
        },
        articles: processedArticles
      };
      
      await fs.writeFile(
        path.join(dateDir, 'metadata.json'),
        JSON.stringify(metadata, null, 2)
      );
      
      // Save full articles summary
      await fs.writeFile(
        path.join(dateDir, 'articles_full.json'),
        JSON.stringify(processedArticles, null, 2)
      );
      
      await context.close();
      
      return {
        success: true,
        articlesFound: articles.length,
        articlesProcessed: processedArticles.length,
        imagesDownloaded
      };
      
    } catch (error) {
      await context.close();
      retries++;
      
      if (retries >= CONFIG.maxRetries) {
        await log('ERROR', `Failed to scrape ${date} after ${CONFIG.maxRetries} retries`, { error: error.message });
        return { success: false, error: error.message };
      }
      
      await log('WARN', `Retry ${retries}/${CONFIG.maxRetries} for ${date}`);
      await new Promise(r => setTimeout(r, CONFIG.retryDelay));
    }
  }
  
  return { success: false, error: 'Max retries exceeded' };
}

// Get previous date
function getPreviousDate(dateStr) {
  const date = new Date(dateStr);
  date.setDate(date.getDate() - 1);
  return date.toISOString().split('T')[0];
}

// Progress report
async function reportProgress(progress, isFinal = false) {
  const report = {
    timestamp: new Date().toISOString(),
    agent: 'RHO',
    newspaper: 'Egbe Omo Oduduwa',
    currentDate: progress.currentDate,
    endDate: progress.endDate,
    totalDaysScraped: progress.totalDaysScraped,
    totalArticlesFound: progress.totalArticlesFound,
    totalImagesDownloaded: progress.totalImagesDownloaded,
    errorsCount: progress.errors.length,
    status: isFinal ? 'completed' : 'running'
  };
  
  await log('INFO', `Progress Report: Day ${progress.totalDaysScraped}, Date ${progress.currentDate}, Articles ${progress.totalArticlesFound}`, report);
  
  // Also save to separate progress log
  await fs.appendFile(
    path.join(CONFIG.logsDir, 'fleet-rho-progress.log'),
    JSON.stringify(report) + '\n'
  );
}

// Main function
async function main() {
  await log('INFO', '=== Fleet Agent RHO - Egbe Omo Oduduwa Scraper Starting ===');
  await log('INFO', `Target: ${CONFIG.startDate} → ${CONFIG.endDate}`);
  
  // Ensure directories exist
  await fs.mkdir(CONFIG.dataDir, { recursive: true });
  await fs.mkdir(CONFIG.logsDir, { recursive: true });
  await fs.mkdir(CONFIG.memoryDir, { recursive: true });
  
  // Load progress
  const progress = await loadProgress();
  await log('INFO', `Resuming from ${progress.currentDate}`);
  
  // Launch browser
  const browser = await chromium.launch({
    headless: CONFIG.headless,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });
  
  // Setup progress reporting interval
  const progressInterval = setInterval(() => reportProgress(progress), CONFIG.progressInterval);
  
  // Handle graceful shutdown
  let shouldStop = false;
  process.on('SIGINT', () => { shouldStop = true; });
  process.on('SIGTERM', () => { shouldStop = true; });
  
  try {
    let currentDate = progress.currentDate;
    let consecutiveErrors = 0;
    const maxConsecutiveErrors = 5;
    
    while (currentDate >= CONFIG.endDate && !shouldStop) {
      const result = await scrapeDate(browser, currentDate, progress);
      
      if (result.success) {
        progress.totalDaysScraped++;
        progress.totalArticlesFound += result.articlesFound || 0;
        progress.totalImagesDownloaded += result.imagesDownloaded || 0;
        consecutiveErrors = 0;
      } else {
        consecutiveErrors++;
        progress.errors.push({ date: currentDate, error: result.error, timestamp: new Date().toISOString() });
        
        if (consecutiveErrors >= maxConsecutiveErrors) {
          await log('ERROR', `Too many consecutive errors (${consecutiveErrors}), stopping`);
          break;
        }
      }
      
      // Update current date and save progress
      progress.currentDate = currentDate;
      await saveProgress(progress);
      
      // Move to previous date
      currentDate = getPreviousDate(currentDate);
      
      // Small delay between dates
      await new Promise(r => setTimeout(r, 2000));
    }
    
    // Final report
    clearInterval(progressInterval);
    progress.status = shouldStop ? 'stopped' : 'completed';
    await saveProgress(progress);
    await reportProgress(progress, true);
    
    await log('INFO', '=== Scraping Complete ===', {
      totalDays: progress.totalDaysScraped,
      totalArticles: progress.totalArticlesFound,
      totalImages: progress.totalImagesDownloaded
    });
    
  } catch (error) {
    clearInterval(progressInterval);
    await log('ERROR', 'Fatal error in main loop', { error: error.message, stack: error.stack });
    progress.status = 'error';
    await saveProgress(progress);
  } finally {
    await browser.close();
  }
}

// Run
main().catch(async (error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
