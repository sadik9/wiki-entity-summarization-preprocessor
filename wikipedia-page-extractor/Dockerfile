# Build context is the repository root (see compose.yaml).
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /workspace/app

COPY lombok.config pom.xml ./
COPY wiki-storage wiki-storage
COPY wikipedia-page-extractor wikipedia-page-extractor
# The parent POM lists every module, so the reactor needs this POM even though the module is not built.
COPY wikidata-graph-builder/pom.xml wikidata-graph-builder/pom.xml

RUN mvn -B -q -pl wikipedia-page-extractor -am package -DskipTests
RUN mkdir -p wikipedia-page-extractor/target/dependency && (cd wikipedia-page-extractor/target/dependency; jar -xf ../*.jar)

FROM eclipse-temurin:21-jre
VOLUME /tmp
ARG DEPENDENCY=/workspace/app/wikipedia-page-extractor/target/dependency
COPY --from=build ${DEPENDENCY}/BOOT-INF/lib /app/lib
COPY --from=build ${DEPENDENCY}/META-INF /app/META-INF
COPY --from=build ${DEPENDENCY}/BOOT-INF/classes /app
ENTRYPOINT ["java","-cp","app:app/lib/*","com.github.msorkhpar.pageextextractor.WikipediaPageExtractorApplication"]
