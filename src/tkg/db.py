"""Neo4j connection (HLD Section 11). Credentials come from the .env file."""
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def get_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not (uri and user and password):
        raise RuntimeError("Missing NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env")
    return GraphDatabase.driver(uri, auth=(user, password))


if __name__ == "__main__":
    driver = get_driver()
    driver.verify_connectivity()
    with driver.session() as session:
        print(session.run("RETURN 'Neo4j is connected' AS msg").single()["msg"])
    driver.close()