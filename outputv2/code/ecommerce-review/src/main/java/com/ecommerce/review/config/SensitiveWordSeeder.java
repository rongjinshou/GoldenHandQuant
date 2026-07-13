package com.ecommerce.review.config;

import com.ecommerce.review.entity.SensitiveWord;
import com.ecommerce.review.repository.SensitiveWordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * Seeds a default sensitive-word list on startup if the table is empty.
 *
 * <p>design-docs/13 §3 makes sensitive-word filtering a mandatory step of
 * review submission, but defines only the matching algorithm (substring, not
 * exact-equals — see {@code SensitiveWordFilter}), not the word list itself or
 * any management API to populate it. Without this seed, the table stays
 * permanently empty and the (correctly implemented) filter can never actually
 * reject anything.
 */
@Configuration
public class SensitiveWordSeeder {

    private static final Logger log = LoggerFactory.getLogger(SensitiveWordSeeder.class);

    private static final List<String> DEFAULT_WORDS = List.of(
            "垃圾产品", "假货", "骗子", "傻逼", "妈的");

    @Bean
    public ApplicationRunner sensitiveWordSeedRunner(SensitiveWordRepository sensitiveWordRepository) {
        return args -> {
            if (sensitiveWordRepository.count() > 0) {
                return;
            }
            for (String word : DEFAULT_WORDS) {
                SensitiveWord entity = new SensitiveWord();
                entity.setWord(word);
                entity.setCategory("DEFAULT");
                sensitiveWordRepository.save(entity);
            }
            log.info("Seeded {} default sensitive words", DEFAULT_WORDS.size());
        };
    }
}
