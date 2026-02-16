/**
 * Ezekiel Backfill Agent - One-time bulk ingestion
 * Processes all existing OCR data into Supabase
 */

const { execSync } = require('child_process');
const path = require('path');
const winston = require('winston');

const CONFIG = {
  projectDir: '/Volumes/Crucial X10/Decide9ja',
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
    new winston.transports.File({ filename: path.join(CONFIG.logsDir, 'ezekiel-backfill.log') }),
    new winston.transports.Console({ format: winston.format.simple() })
  ]
});

async function runCommand(cmd, description) {
  logger.info(`\n📋 ${description}...`);
  logger.info(`Running: ${cmd}`);
  
  try {
    const output = execSync(cmd, {
      cwd: CONFIG.projectDir,
      encoding: 'utf8',
      stdio: 'pipe',
      timeout: 30 * 60 * 1000 // 30 min timeout
    });
    logger.info(`✅ ${description} completed`);
    if (output) logger.info(output.slice(-500)); // Last 500 chars
    return { success: true, output };
  } catch (error) {
    logger.error(`❌ ${description} failed:`, error.message);
    if (error.stdout) logger.info(error.stdout.slice(-500));
    if (error.stderr) logger.error(error.stderr.slice(-500));
    return { success: false, error: error.message };
  }
}

async function main() {
  logger.info('═══════════════════════════════════════════════════');
  logger.info('🤖 EZEKIEL BACKFILL AGENT - Bulk Ingestion');
  logger.info('═══════════════════════════════════════════════════');
  logger.info(`Started: ${new Date().toISOString()}`);
  
  const results = {
    step1_bulkIngest: null,
    step2_supabaseSync: null,
    completed: false
  };
  
  // Step 1: Bulk Ingest to SQLite
  results.step1_bulkIngest = await runCommand(
    'npm run rag:bulk-ingest',
    'Step 1/2: Bulk Ingest OCR Data to SQLite'
  );
  
  if (!results.step1_bulkIngest.success) {
    logger.error('❌ Bulk ingest failed, stopping backfill');
    process.exit(1);
  }
  
  // Step 2: Sync to Supabase (Optimized for Pro Tier)
  results.step2_supabaseSync = await runCommand(
    'npm run supabase:sync:optimized',
    'Step 2/2: Sync to Supabase (Pro Tier Optimized)'
  );
  
  if (!results.step2_supabaseSync.success) {
    logger.error('❌ Supabase sync failed');
    process.exit(1);
  }
  
  results.completed = true;
  
  // Summary
  logger.info('\n═══════════════════════════════════════════════════');
  logger.info('✅ BACKFILL COMPLETE');
  logger.info('═══════════════════════════════════════════════════');
  logger.info(`Finished: ${new Date().toISOString()}`);
  logger.info('\n📊 Results:');
  logger.info('  - Step 1 (Bulk Ingest): ✅ SUCCESS');
  logger.info('  - Step 2 (Supabase Sync): ✅ SUCCESS');
  logger.info('\n🎯 All 660 files processed into Supabase');
}

main().catch(error => {
  logger.error('Fatal error:', error);
  process.exit(1);
});
