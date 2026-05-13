import asyncio
import csv
import time
from datetime import datetime
from neo4j import GraphDatabase
import os

# Research Configuration (Override via env if needed)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password") # Default for local
LOG_FILE = "research_pad_trajectory.csv"

async def run_collector():
    """
    Research State Collector.
    Polls Neo4j for the current PAD state of the agent and logs it to a CSV.
    This captures both chat-driven updates and idle ALMA decay.
    """
    print(f"📊 State Collector starting... logging to {LOG_FILE}")
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    
    # Initialize CSV with headers
    with open(LOG_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "valence", "arousal", "dominance", "trust", "attachment"])

    print("Listening for state changes (Polling 1Hz)... (Ctrl+C to stop)")
    
    try:
        while True:
            with driver.session() as session:
                result = session.run("MATCH (a:Agent {name: 'my friend'}) RETURN a")
                record = result.single()
                if record:
                    props = record["a"]
                    row = [
                        datetime.now().isoformat(),
                        props.get("mood", 0.0),
                        props.get("energy", 0.5),
                        props.get("dominance", 0.5),
                        props.get("trust", 0.5),
                        props.get("attachment", 0.1)
                    ]
                    
                    with open(LOG_FILE, mode='a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                    
                    # Print pulse to console
                    print(f"[{row[0][:19]}] V:{row[1]:.2f} Ar:{row[2]:.2f} D:{row[3]:.2f} T:{row[4]:.2f}", end='\r')
            
            await asyncio.sleep(1) # 1Hz sampling rate for trajectories
            
    except KeyboardInterrupt:
        print("\nStopping collector...")
    finally:
        driver.close()

if __name__ == "__main__":
    asyncio.run(run_collector())
