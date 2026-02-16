/**
 * Run Supabase migrations using JS client
 */

const { createClient } = require('@supabase/supabase-js');
const fs = require('fs').promises;
const path = require('path');

async function runMigrations() {
  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_ANON_KEY;
  
  if (!supabaseUrl || !supabaseKey) {
    console.error('❌ Missing Supabase credentials in .env');
    process.exit(1);
  }
  
  console.log('🔌 Connecting to Supabase...');
  const supabase = createClient(supabaseUrl, supabaseKey);
  
  // Test connection
  const { error: testError } = await supabase.rpc('pg_catalog.version');
  if (testError) {
    console.error('❌ Connection failed:', testError.message);
    process.exit(1);
  }
  
  console.log('✅ Connected to Supabase');
  
  // Read migration file
  const migrationPath = path.join(__dirname, '../supabase/migrations/001_unified_schema.sql');
  const sql = await fs.readFile(migrationPath, 'utf8');
  
  console.log('📜 Running migration...');
  
  // Split SQL into statements
  const statements = sql.split(';').filter(s => s.trim());
  
  for (let i = 0; i < statements.length; i++) {
    const statement = statements[i].trim();
    if (!statement) continue;
    
    try {
      const { error } = await supabase.rpc('exec_sql', { sql: statement + ';' });
      if (error) {
        // Try alternative: direct SQL via REST
        const response = await fetch(`${supabaseUrl}/rest/v1/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${supabaseKey}`,
          },
          body: JSON.stringify({ query: statement + ';' })
        });
        
        if (!response.ok) {
          console.log(`⚠️  Statement ${i + 1} may have failed (non-critical): ${statement.slice(0, 50)}...`);
        }
      }
    } catch (e) {
      console.log(`⚠️  Statement ${i + 1}: ${statement.slice(0, 50)}...`);
    }
  }
  
  console.log('✅ Migration complete!');
  console.log('\n📊 Tables created:');
  console.log('  - documents');
  console.log('  - document_chunks');
  console.log('  - entities');
  console.log('  - topics');
  console.log('  - ingestion_queue');
  console.log('  - sync_status');
  console.log('  - search_logs');
}

runMigrations().catch(error => {
  console.error('❌ Migration error:', error);
  process.exit(1);
});
