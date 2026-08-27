import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def get_connection():
    """Get a database connection"""
    return await asyncpg.connect(os.getenv("DATABASE_URL"))

async def setup_database():
    """Create tables if they don't exist"""
    conn = await get_connection()
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id          SERIAL PRIMARY KEY,
            run_id      TEXT UNIQUE NOT NULL,
            prompt_version TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT NOW(),
            total_cases INT,
            passed      INT,
            failed      INT,
            accuracy    FLOAT,
            avg_latency FLOAT,
            avg_cost    FLOAT,
            total_cost  FLOAT,
            status      TEXT DEFAULT 'running'
        )
    """)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id              SERIAL PRIMARY KEY,
            run_id          TEXT NOT NULL,
            case_id         TEXT NOT NULL,
            prompt_version  TEXT NOT NULL,
            email_text      TEXT,
            expected_category TEXT,
            got_category    TEXT,
            summary         TEXT,
            confidence      FLOAT,
            judge_score     INT,
            passed          BOOLEAN,
            latency         FLOAT,
            cost            FLOAT,
            input_tokens    INT,
            output_tokens   INT,
            created_at      TIMESTAMP DEFAULT NOW()
        )
    """)
    
    await conn.close()
    print("Database setup complete")

async def save_eval_run(run_id: str, prompt_version: str):
    """Create a new eval run record"""
    conn = await get_connection()
    await conn.execute("""
        INSERT INTO eval_runs (run_id, prompt_version)
        VALUES ($1, $2)
        ON CONFLICT (run_id) DO NOTHING
    """, run_id, prompt_version)
    await conn.close()

async def save_eval_result(run_id: str, result: dict):
    """Save a single test case result"""
    conn = await get_connection()
    await conn.execute("""
        INSERT INTO eval_results (
            run_id, case_id, prompt_version,
            email_text, expected_category, got_category,
            summary, confidence, judge_score, passed,
            latency, cost, input_tokens, output_tokens
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11, $12, $13, $14
        )
    """,
        run_id,
        result["case_id"],
        result["prompt_version"],
        result["email_text"],
        result["expected_category"],
        result["got_category"],
        result["summary"],
        result["confidence"],
        result["judge_score"],
        result["passed"],
        result["latency"],
        result["cost"],
        result["input_tokens"],
        result["output_tokens"]
    )
    await conn.close()

async def update_run_summary(run_id: str, summary: dict):
    """Update run with final metrics"""
    conn = await get_connection()
    await conn.execute("""
        UPDATE eval_runs SET
            total_cases = $2,
            passed      = $3,
            failed      = $4,
            accuracy    = $5,
            avg_latency = $6,
            avg_cost    = $7,
            total_cost  = $8,
            status      = 'completed'
        WHERE run_id = $1
    """,
        run_id,
        summary["total_cases"],
        summary["passed"],
        summary["failed"],
        summary["accuracy"],
        summary["avg_latency"],
        summary["avg_cost"],
        summary["total_cost"]
    )
    await conn.close()

async def get_last_run(prompt_version: str) -> dict:
    """Get the most recent completed run for a prompt version"""
    conn = await get_connection()
    row = await conn.fetchrow("""
        SELECT * FROM eval_runs
        WHERE status = 'completed'
        ORDER BY created_at DESC
        LIMIT 1
    """)
    await conn.close()
    return dict(row) if row else None

async def get_run_results(run_id: str) -> list:
    """Get all test case results for a run"""
    conn = await get_connection()
    rows = await conn.fetch("""
        SELECT * FROM eval_results
        WHERE run_id = $1
        ORDER BY case_id
    """, run_id)
    await conn.close()
    return [dict(row) for row in rows]