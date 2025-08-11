#!/usr/bin/env python3
"""
Run database migrations for Suna
"""
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
import glob

# Load environment variables
load_dotenv('backend/.env')

async def run_migrations():
    # Get Supabase credentials
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not service_key:
        print("❌ Missing Supabase credentials in .env file")
        return False
    
    print(f"🔗 Connecting to Supabase at {url}")
    
    # Create Supabase client
    supabase: Client = create_client(url, service_key)
    
    # Get all migration files
    migration_files = sorted(glob.glob('backend/supabase/migrations/*.sql'))
    
    print(f"📚 Found {len(migration_files)} migration files")
    
    # Track results
    successful = 0
    failed = 0
    skipped = 0
    
    for migration_file in migration_files:
        filename = os.path.basename(migration_file)
        print(f"\n📄 Processing: {filename}")
        
        try:
            with open(migration_file, 'r') as f:
                sql = f.read()
            
            # Skip if it's just comments or empty
            if not sql.strip() or sql.strip().startswith('--'):
                print(f"   ⏭️  Skipped (empty or comments only)")
                skipped += 1
                continue
            
            # Execute the migration
            # Note: Supabase Python client doesn't have direct SQL execution
            # We'll use the service role key to run via REST API
            print(f"   ⚠️  Note: Manual execution needed via Supabase dashboard")
            print(f"   📝 Migration contains {len(sql)} characters")
            skipped += 1
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            failed += 1
    
    print(f"\n📊 Migration Summary:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Failed: {failed}")
    
    print("\n💡 To run migrations:")
    print("   1. Go to your Supabase dashboard")
    print("   2. Navigate to SQL Editor")
    print("   3. Run each migration file in order")
    print("   4. Or use: supabase db push (requires Docker)")
    
    return True

if __name__ == "__main__":
    asyncio.run(run_migrations())