package com.github.msorkhpar.wikistorage.data;

import com.github.msorkhpar.wikistorage.utils.KGTriple;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.neo4j.driver.*;
import org.springframework.stereotype.Service;

import java.util.*;


@Service
@Slf4j
@RequiredArgsConstructor
public class PersistenceService {

    private final Optional<Driver> driver;
    private final SubjectRepo subjectRepo;
    private final WikiPageRepo wikiPageRepo;

    public void createNeo4jIndexes() {
        if (driver.isPresent()) {
            try (Session session = driver.get().session()) {
                session.executeWriteWithoutResult(tx -> {
                    // Without this, every MERGE on WikiEntity is a full label scan and ingestion becomes quadratic
                    var result = tx.run("""
                            CREATE CONSTRAINT wikientity_name IF NOT EXISTS
                            FOR (n:WikiEntity) REQUIRE n.entityName IS UNIQUE
                            """).consume();
                    logger.info("Neo4j uniqueness constraint on WikiEntity.entityName ensured: {}", result.counters());
                });
            } catch (Exception e) {
                logger.error("Neo4j constraint could not be created", e);
            }
        }
    }

    // https://github.com/vikramshanbogar/Neo4j-Java
    public boolean persistTriples(List<KGTriple> triples) {
        if (driver.isPresent()) {
            List<Map<String, Object>> paramsList = triples.stream()
                    .map(triple -> Map.<String, Object>of(
                            "subject", triple.getSubjectQid(),
                            "object", triple.getObjectQid(),
                            "predicate", triple.getPropertyId()
                    ))
                    .toList();
            try (Session session = driver.get().session()) {
                session.executeWriteWithoutResult(tx -> {
                    var params = Map.<String, Object>of("props", paramsList);
                    tx.run("""
                            UNWIND $props AS triple
                            MERGE (source:WikiEntity {entityName: triple.subject})
                            MERGE (target:WikiEntity {entityName: triple.object})
                            CREATE (source)-[r:HAS_TYPE {type: triple.predicate}]->(target)
                            """, params
                    );
                });
                return true;
            } catch (Exception e) {
                logger.error("Exception during triple insertion", e);
                throw e;
            }
        }
        return false;
    }

    public void persistSubject(String subjectName, String label, String description) {
        subjectRepo.save(new Subject(subjectName, label, description));
    }

    public WikipediaPage persistWikiPage(Long id, String title, String content) {
        return wikiPageRepo.save(new WikipediaPage(id, title, content, content.length()));
    }
}