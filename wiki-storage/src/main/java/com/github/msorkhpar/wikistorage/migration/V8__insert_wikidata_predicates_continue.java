package com.github.msorkhpar.wikistorage.migration;

import lombok.extern.slf4j.Slf4j;
import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

@Component
@Slf4j
public class V8__insert_wikidata_predicates_continue extends BaseJavaMigration {
    @Value("${app.storage.wikidata-predicates-path-con:classpath:wikidata_predicates_continue.tsv}")
    private String filePath;
    @Autowired
    private ResourceLoader resourceLoader;

    private void persistRow(JdbcTemplate jdbcTemplate, String[] row) {
        jdbcTemplate.update("insert into predicates (property_id, property_label, description) values(?,?,?)",
                row[0], row[1], row[2]);
    }

    public void migrate(Context context) throws IOException {
        final JdbcTemplate jdbcTemplate = new JdbcTemplate(
                new SingleConnectionDataSource(context.getConnection(), true));
        Resource resource = resourceLoader.getResource(filePath);

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {
            String line = reader.readLine();
            String[] headers = line.split("\t");
            String[] row;
            while ((line = reader.readLine()) != null) {
                // limit -1 keeps trailing empty columns (e.g. a property without a description); the default
                // split drops them, and the row then has too few columns
                persistRow(jdbcTemplate, line.split("\t", -1));
            }
        }
    }
}