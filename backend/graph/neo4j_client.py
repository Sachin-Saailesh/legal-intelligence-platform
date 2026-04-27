from neo4j import AsyncGraphDatabase, AsyncDriver

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class Neo4jClient:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await self._driver.verify_connectivity()
        logger.info("neo4j_connected", uri=settings.neo4j_uri)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def create_schema_constraints(self) -> None:
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Clause) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Party) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cs:Case) REQUIRE cs.citation IS UNIQUE",
        ]
        async with self._driver.session() as session:
            for q in queries:
                await session.run(q)
        logger.info("neo4j_schema_constraints_created")

    async def ingest_document_entities(
        self, doc_id: str, matter_id: str, entities_list: list[dict]
    ) -> None:
        async with self._driver.session() as session:
            # Create document node
            await session.run(
                "MERGE (d:Document {id: $doc_id}) SET d.matter_id = $matter_id",
                doc_id=doc_id,
                matter_id=matter_id,
            )

            for ent in entities_list:
                chunk_id = ent.get("chunk_id", "")
                parties = ent.get("parties", [])
                defined_terms = ent.get("defined_terms", [])
                governing_law = ent.get("governing_law")
                referenced_clauses = ent.get("referenced_clauses", [])

                # Create clause node
                await session.run(
                    "MERGE (c:Clause {id: $chunk_id}) SET c.doc_id = $doc_id, c.matter_id = $matter_id",
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    matter_id=matter_id,
                )

                # Party → Contract relationships
                for party in parties:
                    if party:
                        await session.run(
                            """
                            MERGE (p:Party {name: $name})
                            MERGE (d:Document {id: $doc_id})
                            MERGE (p)-[:SIGNATORY_TO]->(d)
                            """,
                            name=party,
                            doc_id=doc_id,
                        )

                # Governing law
                if governing_law:
                    await session.run(
                        """
                        MERGE (c:Clause {id: $chunk_id})
                        SET c.governing_law = $governing_law
                        """,
                        chunk_id=chunk_id,
                        governing_law=governing_law,
                    )

                # Clause references
                for ref in referenced_clauses:
                    if ref:
                        await session.run(
                            """
                            MERGE (c1:Clause {id: $from_id})
                            MERGE (c2:Clause {id: $to_id})
                            MERGE (c1)-[:REFERENCES]->(c2)
                            """,
                            from_id=chunk_id,
                            to_id=f"{doc_id}_{ref}",
                        )

    async def get_clause_dependencies(self, clause_id: str) -> list[dict]:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (c:Clause {id: $clause_id})-[:REFERENCES*1..3]->(dep:Clause)
                RETURN dep.id AS dep_id, dep.matter_id AS matter_id
                LIMIT 20
                """,
                clause_id=clause_id,
            )
            records = await result.data()
            return records

    async def get_parties_for_document(self, doc_id: str) -> list[str]:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (p:Party)-[:SIGNATORY_TO]->(d:Document {id: $doc_id})
                RETURN p.name AS name
                """,
                doc_id=doc_id,
            )
            records = await result.data()
            return [r["name"] for r in records]

    async def add_case_citation(
        self, case_citation: str, cited_doc_id: str
    ) -> None:
        async with self._driver.session() as session:
            await session.run(
                """
                MERGE (cs:Case {citation: $citation})
                MERGE (d:Document {id: $doc_id})
                MERGE (cs)-[:CITED_BY]->(d)
                """,
                citation=case_citation,
                doc_id=cited_doc_id,
            )
