/**
 * Initialize Supabase Schema for Decide9ja
 * Creates tables needed for optimized sync
 */

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = 'https://liosugqvfvubmqaqzrro.supabase.co';
const SUPABASE_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxpb3N1Z3F2ZnZ1Ym1xYXF6cnJvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5OTQxOTAsImV4cCI6MjA4NTU3MDE5MH0.F45A5NKhJwNrFbzmh_VuMy-o88WIiQw5uoVHY2UasPA';

async function initializeSchema() {
  console.log('🚀 Initializing Supabase schema...');
  
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  
  // Test if documents table exists by trying a simple query
  const { error: testError } = await supabase
    .from('documents')
    .select('id')
    .limit(1);
  
  if (testError && testError.message.includes('does not exist')) {
    console.log('📋 Documents table not found. Creating via RPC...');
    
    // Create table using raw SQL via rpc (if available) or use the REST API workaround
    // Workaround: Create table by inserting to a non-existent table triggers auto-creation
    // in some configurations, but Supabase doesn't support this.
    
    // Alternative: Use the SQL API directly
    const sql = `
      CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        source_type TEXT,
        newspaper TEXT,
        published_date DATE,
        title TEXT,
        content_summary TEXT,
        word_count INTEGER,
        entities JSONB DEFAULT '[]',
        topics JSONB DEFAULT '[]',
        sentiment JSONB DEFAULT '{}',
        confidence_score REAL,
        has_full_content BOOLEAN DEFAULT true,
        indexed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      );
      
      CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(published_date);
      CREATE INDEX IF NOT EXISTS idx_documents_newspaper ON documents(newspaper);
    `;
    
    // Try using the pg-meta API
    try {
      const response = await fetch(`${SUPABASE_URL}/rest/v1/`, {
        method: 'POST',
        headers: {
          'apikey': SUPABASE_SERVICE_KEY,
          'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
          'Content-Type': 'application/json',
          'Prefer': 'resolution=merge-duplicates'
        },
        body: JSON.stringify({ query: sql })
      });
      
      if (!response.ok) {
        console.log('⚠️  Could not auto-create schema via API');
        console.log('📖 Please run the SQL in supabase-schema.sql manually:');
        console.log('   1. Go to https://supabase.com/dashboard/project/liosugqvfvubmqaqzrro');
        console.log('   2. Open SQL Editor');
        console.log('   3. Paste and run the contents of supabase-schema.sql');
        console.log('');
        console.log('📁 Schema file: /Volumes/Crucial X10/Decide9ja/supabase-schema.sql');
        return false;
      }
    } catch (e) {
      console.log('⚠️  Error:', e.message);
      return false;
    }
  } else if (testError) {
    console.log('⚠️  Error checking table:', testError.message);
    return false;
  } else {
    console.log('✅ Documents table exists');
    return true;
  }
}

initializeSchema().then(ok => {
  if (ok) {
    console.log('✅ Schema ready for sync');
    process.exit(0);
  } else {
    console.log('❌ Schema needs manual setup');
    process.exit(1);
  }
}).catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
