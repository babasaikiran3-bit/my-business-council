"""Test Supabase connection."""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    from database import DatabaseManager

    print("🔍 Testing Supabase connection...")
    db_url = os.getenv('DATABASE_URL', 'NOT SET')
    if db_url == 'NOT SET':
        print("❌ DATABASE_URL not found in .env file!")
        print("\nPlease add DATABASE_URL to your .env file:")
        print("DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres")
        return

    print(f"📍 DATABASE_URL: {db_url[:50]}...")

    try:
        # Initialize database
        DatabaseManager.initialize()
        print("✅ Database manager initialized")

        # Try to connect
        session = DatabaseManager.get_session()
        print("✅ Session created")

        # Execute a simple query
        from sqlalchemy import text
        result = await session.execute(text("SELECT version();"))
        version = result.scalar()
        print(f"✅ Connected to PostgreSQL!")
        print(f"📊 Version: {version}")

        await session.close()
        await DatabaseManager.close()

        print("\n🎉 Connection successful! Ready to create tables.")

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nCommon issues:")
        print("1. Check if DATABASE_URL is correct in .env")
        print("2. Verify password doesn't contain special characters that need escaping")
        print("3. Make sure you're using the 'Pooler' connection string (port 6543)")
        print("4. Check if Supabase project is paused (go to dashboard)")
        raise

if __name__ == "__main__":
    asyncio.run(test_connection())
