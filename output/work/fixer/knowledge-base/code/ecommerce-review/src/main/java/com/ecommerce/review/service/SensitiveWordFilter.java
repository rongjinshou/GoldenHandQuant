package com.ecommerce.review.service;

import com.ecommerce.review.entity.SensitiveWord;
import com.ecommerce.review.repository.SensitiveWordRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Filters review content for sensitive words.
 */
@Component
public class SensitiveWordFilter {

    private static final Logger log = LoggerFactory.getLogger(SensitiveWordFilter.class);

    private final SensitiveWordRepository sensitiveWordRepository;

    public SensitiveWordFilter(SensitiveWordRepository sensitiveWordRepository) {
        this.sensitiveWordRepository = sensitiveWordRepository;
    }

    /**
     * Check if the given content contains any sensitive words.
     *
     * <p>Uses substring containment (design-docs/13 §3 explicitly forbids
     * exact-equals-only matching): any occurrence of a sensitive word inside
     * the content is a hit, not just content that equals the word exactly.
     *
     * @param content the review content to check
     * @return true if the content contains a sensitive word, false otherwise
     */
    public boolean containsSensitiveWord(String content) {
        if (content == null) {
            return false;
        }

        List<SensitiveWord> words = sensitiveWordRepository.findAll();

        for (SensitiveWord sw : words) {
            if (content.contains(sw.getWord())) {
                log.warn("Sensitive word detected in content: {}", sw.getWord());
                return true;
            }
        }

        return false;
    }

    /**
     * Filter the content by replacing every occurrence of each sensitive word
     * with asterisks (substring replacement, not exact-equals replacement).
     *
     * @param content the review content to filter
     * @return the filtered content
     */
    public String filter(String content) {
        if (content == null) {
            return null;
        }

        List<SensitiveWord> words = sensitiveWordRepository.findAll();
        String result = content;

        for (SensitiveWord sw : words) {
            result = result.replace(sw.getWord(), "***");
        }

        return result;
    }
}
