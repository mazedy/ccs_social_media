from neo4j import GraphDatabase
from app.core.config import settings

class Neo4jConnection:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.auth_user, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def get_session(self):
        return self.driver.session(database=settings.NEO4J_DATABASE)

db = Neo4jConnection()
