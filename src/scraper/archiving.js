const { chromium } = require('playwright');
const fs = require('fs').promises;
const path = require('path');
const winston = require('winston');

// Enhanced Configuration
const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
  dataDir: '/Volumes/Crucial X10/Decide9ja/data/archiving',
  logsDir: '/Volumes/Crucial X10/Decide9ja/logs',
  memoryDir: '/Volumes/Crucial X10/Decide9ja/memory',
  
  newspapers: [
    { name: 'PM News', slug: 'PM+News', id: 'pmnews' },
    { name: 'The Guardian', slug: 'The+Guardian', id: 'guardian' },
    { name: 'Vanguard', slug: 'Vanguard', id: 'vanguard' },
    { name: 'Punch', slug: 'Punch', id: 'punch' },
    { name: 'Daily Trust', slug: 'Daily+Trust', id: 'dailytrust' },
    { name: 'ThisDay', slug: 'ThisDay', id: 'thisday' },
    { name: 'Tribune', slug: 'Tribune', id: 'tribune' },
    { name: 'Sun', slug: 'Sun', id: 'sun' },
    { name: 'Nation', slug: 'Nation', id: 'nation' },
    { name: 'Leadership', slug: 'Leadership', id: 'leadership' }
  ],
  
  startDate: '2026-02-05',
  endDate: '2020-01-01',
  
  // Enhanced retry and fallback settings
  maxRetries: 5,
  retryDelay: 5000,
  pageTimeout: 90000,
  browserTimeout: 120000,
  headless: true,
  
  // Fallback selectors in order of preference
  selectors: {
    results: [
      '[data-testid="result-item"]',
      '.result-item',
      '.archive-item',
      '.search-result',
      'article',
      '.issue-card',
      '.newspaper-item',
      '[class*="result"]',
      '[class*="item"]'
    ],
    title: [
      'h2',
      'h3',
      '.title',
      '[data-title]',
      '.headline',
      'a'
    ],
    date: [
      '.date',
      '[data-date]',
      'time',
      '[datetime]',
      '.published',
      '.timestamp'
    ],
    image: [
      'img[src*="archive"]',
      'img[src*="newspaper"]',
      'img',
      '[data-image]'
    ]
  }
};

// Enhanced Logging with detailed error capture
const logger = winston.createLogger({
  level: 'debug',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { 
    service: 'philip-scraper',
    version: '2.0.0',
    hostname: require('os').hostname()
  },
  transports: [
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, 'archiving-error.log'),
      level: 'error',
      maxsize: 52428800, // 50MB
      maxFiles: 5
    }),
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, 'archiving.log'),
      maxsize: 104857600, // 100MB
      maxFiles: 10
    }),
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ],
  exceptionHandlers: [
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, 'exceptions.log') 
    })
  ],
  rejectionHandlers: [
    new winston.transports.File({ 
      filename: path.join(CONFIG.logsDir, 'rejections.log') 
    })
  ]
});

// Detailed error logger
async function logError(context, error, metadata = {}) {
  const errorDetails = {
    context,
    message: error.message,
    stack: error.stack,
    code: error.code,
    type: error.name,
    timestamp: new Date().toISOString(),
    ...metadata
  };
  
  logger.error('Scraper Error', errorDetails);
  
  // Also write to dedicated error file for easy parsing
  const errorFile = path.join(CONFIG.logsDir, 'detailed-errors.jsonl');
  await fs.appendFile(errorFile, JSON.stringify(errorDetails) + '\n');
}

// Retry wrapper with exponential backoff
async function withRetry(operation, context, maxRetries = CONFIG.maxRetries) {
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      logger.debug(`Attempt ${attempt}/${maxRetries} for: ${context}`);
      return await operation();
    } catch (error) {
      lastError = error;
      
      await logError(`Retry attempt ${attempt} failed for ${context}`, error, {
        attempt,
        maxRetries,
        context
      });
      
      if (attempt < maxRetries) {
        const delay = CONFIG.retryDelay * Math.pow(2, attempt - 1); // Exponential backoff
        logger.info(`Waiting ${delay}ms before retry ${attempt + 1}...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  throw new Error(`All ${maxRetries} retries failed for ${context}: ${lastError.message}`);
}

// Enhanced page scraping with fallback selectors
async function scrapeWithFallbacks(page, url, newspaper, date) {
  const results = [];
  let lastError;
  
  for (const selector of CONFIG.selectors.results) {
    try {
      logger.debug(`Trying selector: ${selector}`);
      
      const items = await page.evaluate((sel) => {
        const results = [];
        const elements = document.querySelectorAll(sel);
        
        // Define selectors inside evaluate (can't pass complex objects)
        const titleSelectors = ['h2', 'h3', '.title', '[data-title]', '.headline', 'a'];
        const imageSelectors = ['img[src*="archive"]', 'img[src*="newspaper"]', 'img', '[data-image]'];
        const dateSelectors = ['.date', '[data-date]', 'time', '[datetime]', '.published', '.timestamp'];
        
        elements.forEach(el => {
          // Try multiple selectors for each field
          const getText = (selectors) => {
            for (const s of selectors) {
              const found = el.querySelector(s);
              if (found) return found.textContent?.trim();
            }
            return null;
          };
          
          const getAttr = (selectors, attr) => {
            for (const s of selectors) {
              const found = el.querySelector(s);
              if (found && found[attr]) return found[attr];
            }
            return null;
          };
          
          const link = el.querySelector('a');
          if (link) {
            results.push({
              url: link.href,
              title: getText(titleSelectors) || link.textContent?.trim(),
              imageUrl: getAttr(imageSelectors, 'src'),
              thumbnail: getAttr(imageSelectors, 'srcset')?.split(',')[0]?.split(' ')[0],
              date: getText(dateSelectors)
            });
          }
        });
        
        return results;
      }, selector);
      
      if (items.length > 0) {
        logger.info(`✅ Selector '${selector}' found ${items.length} items`);
        return items;
      }
    } catch (error) {
      lastError = error;
      logger.debug(`Selector '${selector}' failed: ${error.message}`);
    }
  }
  
  // If all selectors fail, try to get any links on the page
  logger.warn('All selectors failed, attempting fallback link extraction');
  
  try {
    const fallbackLinks = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('a[href*="archive"], a[href*="newspaper"]'))
        .map(a => ({
          url: a.href,
          title: a.textContent?.trim() || 'Untitled',
          imageUrl: null,
          date: null
        }));
    });
    
    if (fallbackLinks.length > 0) {
      logger.info(`✅ Fallback extraction found ${fallbackLinks.length} links`);
      return fallbackLinks;
    }
  } catch (error) {
    await logError('Fallback extraction failed', error, { url, newspaper, date });
  }
  
  throw new Error(`All scraping methods failed: ${lastError?.message || 'No results found'}`);
}

// Enhanced date scraper with retry and fallback
async function scrapeDate(browser, newspaper, date) {
  const url = `https://archivi.ng/search?publication=${newspaper.slug}&date=${date}`;
  
  return await withRetry(async () => {
    logger.info(`🔍 Scraping: ${newspaper.name} - ${date}`);
    
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      viewport: { width: 1920, height: 1080 },
      extraHTTPHeaders: {
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
      }
    });
    
    const page = await context.newPage();
    
    try {
      // Set longer timeout for slow-loading pages
      await page.goto(url, { 
        waitUntil: 'networkidle', 
        timeout: CONFIG.pageTimeout 
      });
      
      // Wait for JavaScript to render
      await page.waitForTimeout(8000);
      
      // Take screenshot for debugging if needed
      if (process.env.DEBUG_SCRAPER) {
        const screenshotPath = path.join(CONFIG.logsDir, 'screenshots', `${newspaper.id}-${date}.png`);
        await fs.mkdir(path.dirname(screenshotPath), { recursive: true });
        await page.screenshot({ path: screenshotPath, fullPage: true });
      }
      
      // Scrape with fallback selectors
      const issues = await scrapeWithFallbacks(page, url, newspaper, date);
      
      await context.close();
      
      logger.info(`✅ Found ${issues.length} issues for ${newspaper.name} on ${date}`);
      
      return {
        success: true,
        newspaper: newspaper.name,
        date,
        issues,
        url,
        timestamp: new Date().toISOString()
      };
      
    } catch (error) {
      await context.close();
      
      await logError(`Scrape failed for ${newspaper.name} - ${date}`, error, {
        url,
        newspaper: newspaper.name,
        date,
        selectorsTried: CONFIG.selectors.results
      });
      
      throw error;
    }
  }, `scrape-${newspaper.name}-${date}`);
}

// Health check function
async function healthCheck() {
  const checks = {
    timestamp: new Date().toISOString(),
    pid: process.pid,
    memory: process.memoryUsage(),
    uptime: process.uptime(),
    directories: {}
  };
  
  try {
    checks.directories.data = await fs.stat(CONFIG.dataDir).then(() => 'OK');
    checks.directories.logs = await fs.stat(CONFIG.logsDir).then(() => 'OK');
    checks.directories.memory = await fs.stat(CONFIG.memoryDir).then(() => 'OK');
  } catch (error) {
    checks.directories.error = error.message;
  }
  
  // Write health status
  await fs.writeFile(
    path.join(CONFIG.memoryDir, 'health.json'),
    JSON.stringify(checks, null, 2)
  );
  
  return checks;
}

// Graceful shutdown handler
function setupGracefulShutdown(browser) {
  const shutdown = async (signal) => {
    logger.info(`Received ${signal}, shutting down gracefully...`);
    
    try {
      await browser.close();
      logger.info('Browser closed');
    } catch (error) {
      logger.error('Error closing browser:', error);
    }
    
    // Save progress
    logger.info('Progress saved. Exiting.');
    process.exit(0);
  };
  
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

// Main function with enhanced error handling
async function main() {
  logger.info('=== PHILIP ARCHIVI.NG SCRAPER v2.0 - BULLETPROOF ===');
  logger.info(`Target: ${CONFIG.newspapers.length} newspapers, ${CONFIG.startDate} → ${CONFIG.endDate}`);
  
  // Ensure directories
  await fs.mkdir(CONFIG.dataDir, { recursive: true });
  await fs.mkdir(CONFIG.logsDir, { recursive: true });
  await fs.mkdir(CONFIG.memoryDir, { recursive: true });
  await fs.mkdir(path.join(CONFIG.logsDir, 'screenshots'), { recursive: true });
  
  // Health check
  const health = await healthCheck();
  logger.info('Health check:', health);
  
  // Load progress
  let progress;
  try {
    const progressFile = path.join(CONFIG.memoryDir, 'SCRAPING_PROGRESS.json');
    const data = await fs.readFile(progressFile, 'utf8');
    progress = JSON.parse(data);
    // Ensure errors array exists (backward compatibility)
    if (!progress.errors) progress.errors = [];
    if (!progress.newspapers) progress.newspapers = {};
  } catch {
    progress = {
      currentNewspaper: 0,
      currentDate: CONFIG.startDate,
      totalIssues: 0,
      errors: [],
      newspapers: {}
    };
  }
  
  logger.info(`Resuming from: ${CONFIG.newspapers[progress.currentNewspaper]?.name || 'PM News'} - ${progress.currentDate || CONFIG.startDate}`);
  
  // Launch browser with enhanced settings
  const browser = await chromium.launch({
    headless: CONFIG.headless,
    timeout: CONFIG.browserTimeout,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--disable-gpu',
      '--window-size=1920,1080'
    ]
  });
  
  // Setup graceful shutdown
  setupGracefulShutdown(browser);
  
  try {
    // Main scraping loop
    for (let i = progress.currentNewspaper; i < CONFIG.newspapers.length; i++) {
      const newspaper = CONFIG.newspapers[i];
      logger.info(`\n📰 Processing newspaper: ${newspaper.name} (${i + 1}/${CONFIG.newspapers.length})`);
      
      let currentDate = i === progress.currentNewspaper ? progress.currentDate : CONFIG.startDate;
      let consecutiveErrors = 0;
      const maxConsecutiveErrors = 10;
      
      // Process dates backwards
      while (currentDate >= CONFIG.endDate) {
        try {
          // Periodic health check
          if (progress.totalIssues % 50 === 0) {
            await healthCheck();
          }
          
          const result = await scrapeDate(browser, newspaper, currentDate);
          
          if (result.success && result.issues.length > 0) {
            progress.totalIssues += result.issues.length;
            consecutiveErrors = 0; // Reset error counter
            
            // Save issues metadata
            const dateDir = path.join(CONFIG.dataDir, newspaper.id, currentDate.replace(/-/g, '/'));
            await fs.mkdir(dateDir, { recursive: true });
            
            await fs.writeFile(
              path.join(dateDir, 'metadata.json'),
              JSON.stringify(result, null, 2)
            );
            
            logger.info(`✅ Saved ${result.issues.length} issues to ${dateDir}`);
          } else {
            logger.warn(`⚠️ No issues found for ${newspaper.name} on ${currentDate}`);
          }
          
        } catch (error) {
          consecutiveErrors++;
          
          await logError(`Failed to scrape ${newspaper.name} - ${currentDate}`, error, {
            consecutiveErrors,
            maxConsecutiveErrors
          });
          
          progress.errors.push({
            newspaper: newspaper.name,
            date: currentDate,
            error: error.message,
            timestamp: new Date().toISOString()
          });
          
          // If too many consecutive errors, skip to next newspaper
          if (consecutiveErrors >= maxConsecutiveErrors) {
            logger.error(`❌ Too many consecutive errors (${consecutiveErrors}), skipping to next newspaper`);
            break;
          }
        }
        
        // Update progress
        progress.currentDate = currentDate;
        progress.currentNewspaper = i;
        
        await fs.writeFile(
          path.join(CONFIG.memoryDir, 'SCRAPING_PROGRESS.json'),
          JSON.stringify(progress, null, 2)
        );
        
        // Move to previous date
        const date = new Date(currentDate);
        date.setDate(date.getDate() - 1);
        currentDate = date.toISOString().split('T')[0];
        
        // Delay between dates
        await new Promise(r => setTimeout(r, 3000));
      }
      
      // Move to next newspaper
      progress.currentNewspaper = i + 1;
      progress.currentDate = CONFIG.startDate;
      await fs.writeFile(
        path.join(CONFIG.memoryDir, 'SCRAPING_PROGRESS.json'),
        JSON.stringify(progress, null, 2)
      );
    }
    
    logger.info('\n🎉 Scraping complete!');
    logger.info(`Total issues archived: ${progress.totalIssues}`);
    logger.info(`Total errors: ${progress.errors.length}`);
    
  } catch (error) {
    logger.error('💥 Fatal error in main loop:', error);
    await logError('Fatal error in main loop', error);
    throw error;
  } finally {
    await browser.close();
  }
}

// Run with enhanced error handling
if (require.main === module) {
  main().catch(async (error) => {
    await logError('Unhandled fatal error', error);
    logger.error('Process exiting with error');
    process.exit(1);
  });
}

module.exports = { main, scrapeDate, withRetry, logError };
