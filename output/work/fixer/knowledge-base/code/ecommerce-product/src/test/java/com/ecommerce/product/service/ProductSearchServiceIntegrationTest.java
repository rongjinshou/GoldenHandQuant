package com.ecommerce.product.service;

import com.ecommerce.common.dto.PageResponse;
import com.ecommerce.product.dto.ProductListResponse;
import com.ecommerce.product.dto.ProductSearchRequest;
import com.ecommerce.product.entity.Category;
import com.ecommerce.product.entity.ProductSku;
import com.ecommerce.product.entity.ProductSpu;
import com.ecommerce.product.entity.SkuStatus;
import com.ecommerce.product.entity.SpuTagRelation;
import com.ecommerce.product.repository.ProductSpuRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.context.annotation.Import;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Exercises {@link ProductSearchService} against a real (H2) database via
 * {@code @DataJpaTest}, so that database-level Specification predicates -- descendant
 * category resolution, tag filtering, keyword-vs-SPU-name matching, and pagination
 * totals -- are verified end-to-end rather than through mocked repository return values.
 *
 * <p>This specifically targets the class of bug this module had: category/brand
 * filtering applied only to the current page's in-memory content (after the DB page
 * was already fetched), which silently corrupted both {@code total} and the contents
 * of any page beyond the first.
 */
@DataJpaTest
@Import(ProductSearchService.class)
@DisplayName("ProductSearchService (integration, real database)")
class ProductSearchServiceIntegrationTest {

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private ProductSearchService productSearchService;

    @Autowired
    private ProductSpuRepository spuRepository;

    private Long parentCategoryId;

    @BeforeEach
    void setUp() {
        Category parent = new Category();
        parent.setName("Electronics");
        parent.setLevel(1);
        parent.setSortOrder(0);
        entityManager.persist(parent);
        parentCategoryId = parent.getId();

        Category child = new Category();
        child.setName("Phones");
        child.setParentId(parentCategoryId);
        child.setLevel(2);
        child.setSortOrder(0);
        entityManager.persist(child);
        Long childCategoryId = child.getId();

        // 3 SPUs directly under the parent category, 3 more under the child (descendant) category
        for (int i = 0; i < 3; i++) {
            createSkuUnderCategory("PARENT-SPU-" + i, "PARENT-SKU-" + i, parentCategoryId);
        }
        for (int i = 0; i < 3; i++) {
            createSkuUnderCategory("CHILD-SPU-" + i, "CHILD-SKU-" + i, childCategoryId);
        }
        // An SPU under an unrelated category must never show up in a parent-category search.
        createSkuUnderCategory("OTHER-SPU", "OTHER-SKU", 999_999L);

        entityManager.flush();
    }

    private void createSkuUnderCategory(String spuCode, String skuCode, Long categoryId) {
        ProductSpu spu = new ProductSpu();
        spu.setSpuCode(spuCode);
        spu.setName(spuCode);
        spu.setCategoryId(categoryId);
        spu.setStatus("ON_SHELF");
        entityManager.persist(spu);

        ProductSku sku = new ProductSku();
        sku.setSpuId(spu.getId());
        sku.setSkuCode(skuCode);
        sku.setName(skuCode);
        sku.setPrice(new BigDecimal("10.00"));
        sku.setStatus(SkuStatus.ON_SHELF);
        sku.setSortOrder(0);
        sku.setSalesCount(0);
        entityManager.persist(sku);
    }

    @Test
    @DisplayName("filtering by parent category includes descendant categories, with a correct total across pages")
    void testSearch_categoryFilterIncludesDescendants_correctTotalAcrossPages() {
        ProductSearchRequest request = new ProductSearchRequest();
        request.setCategoryId(parentCategoryId);
        request.setPage(0);
        request.setSize(4);

        PageResponse<ProductListResponse> firstPage = productSearchService.search(request);

        // 6 total: 3 directly under the parent + 3 under its child (descendant) category.
        // The unrelated "OTHER" SPU must never be counted.
        assertThat(firstPage.getTotal()).isEqualTo(6L);
        assertThat(firstPage.getItems()).hasSize(4);

        request.setPage(1);
        PageResponse<ProductListResponse> secondPage = productSearchService.search(request);
        assertThat(secondPage.getTotal()).isEqualTo(6L);
        assertThat(secondPage.getItems()).hasSize(2);
    }

    @Test
    @DisplayName("tag filter actually restricts results to SPUs associated with the tag")
    void testSearch_tagFilter_restrictsResults() {
        ProductSpu taggedSpu = spuRepository.findBySpuCode("PARENT-SPU-0").orElseThrow();
        entityManager.persist(new SpuTagRelation(taggedSpu.getId(), "clearance"));
        entityManager.flush();

        ProductSearchRequest request = new ProductSearchRequest();
        request.setTags(List.of("clearance"));

        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getTotal()).isEqualTo(1L);
        assertThat(result.getItems().get(0).getSpuId()).isEqualTo(taggedSpu.getId());
    }

    @Test
    @DisplayName("keyword matches SPU (product) name in addition to SKU name")
    void testSearch_keywordMatchesSpuName() {
        ProductSearchRequest request = new ProductSearchRequest();
        request.setKeyword("CHILD-SPU-1");

        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getTotal()).isEqualTo(1L);
        assertThat(result.getItems().get(0).getName()).isEqualTo("CHILD-SKU-1");
    }

    @Test
    @DisplayName("default search (onlyOnShelf unset) excludes OFF_SHELF items")
    void testSearch_defaultExcludesOffShelf() {
        ProductSpu offShelfSpu = new ProductSpu();
        offShelfSpu.setSpuCode("OFF-SPU");
        offShelfSpu.setName("Off Spu");
        offShelfSpu.setCategoryId(parentCategoryId);
        offShelfSpu.setStatus("OFF_SHELF");
        entityManager.persist(offShelfSpu);

        ProductSku offShelfSkuEntity = new ProductSku();
        offShelfSkuEntity.setSpuId(offShelfSpu.getId());
        offShelfSkuEntity.setSkuCode("OFF-SKU");
        offShelfSkuEntity.setName("OFF-SKU");
        offShelfSkuEntity.setPrice(new BigDecimal("10.00"));
        offShelfSkuEntity.setStatus(SkuStatus.OFF_SHELF);
        offShelfSkuEntity.setSortOrder(0);
        offShelfSkuEntity.setSalesCount(0);
        entityManager.persist(offShelfSkuEntity);
        entityManager.flush();

        ProductSearchRequest request = new ProductSearchRequest();
        request.setKeyword("OFF-SKU");

        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getTotal()).isZero();
    }
}
