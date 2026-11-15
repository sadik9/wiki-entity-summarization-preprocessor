# Build context is the repository root (see compose.yaml).
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /workspace/app

COPY lombok.config pom.xml ./
COPY wiki-storage wiki-storage
COPY wikidata-graph-builder wikidata-graph-builder
# The parent POM lists every module, so the reactor needs this POM even though the module is not built.
COPY wikipedia-page-extractor/pom.xml wikipedia-page-extractor/pom.xml

RUN mvn -B -q -pl wikidata-graph-builder -am package -DskipTests
RUN mkdir -p wikidata-graph-builder/target/dependency && (cd wikidata-graph-builder/target/dependency; jar -xf ../*.jar)

FROM eclipse-temurin:21-jre
VOLUME /tmp
ARG DEPENDENCY=/workspace/app/wikidata-graph-builder/target/dependency
COPY --from=build ${DEPENDENCY}/BOOT-INF/lib /app/lib
COPY --from=build ${DEPENDENCY}/META-INF /app/META-INF
COPY --from=build ${DEPENDENCY}/BOOT-INF/classes /app
ENTRYPOINT ["java","-cp","app:app/lib/*","com.github.msorkhpar.graphbuilder.WikidataGraphBuilderApplication"]
