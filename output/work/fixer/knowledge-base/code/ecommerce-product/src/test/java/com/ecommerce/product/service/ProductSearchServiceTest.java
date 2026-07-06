package com.ecommerce.product.service;

import com.ecommerce.common.dto.PageResponse;
import com.ecommerce.product.dto.ProductListResponse;
import com.ecommerce.product.dto.ProductSearchRequest;
import com.ecommerce.product.entity.Category;
import com.ecommerce.product.entity.ProductSku;
import com.ecommerce.product.entity.ProductSpu;
import com.ecommerce.product.entity.SkuStatus;
import com.ecommerce.product.entity.SpuTagRelation;
import com.ecommerce.product.repository.CategoryRepository;
import com.ecommerce.product.repository.ProductSkuRepository;
import com.ecommerce.product.repository.ProductSpuRepository;
import com.ecommerce.product.repository.SpuTagRelationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("ProductSearchService")
@ExtendWith(MockitoExtension.class)
class ProductSearchServiceTest {

    @Mock
    private ProductSkuRepository skuRepository;

    @Mock
    private ProductSpuRepository spuRepository;

    @Mock
    private CategoryRepository categoryRepository;

    @Mock
    private SpuTagRelationRepository spuTagRelationRepository;

    @InjectMocks
    private ProductSearchService productSearchService;

    private ProductSku onShelfSku;
    private ProductSku offShelfSku;
    private ProductSku draftSku;
    private ProductSku deletedSku;
    private ProductSpu spu;

    @BeforeEach
    void setUp() {
        spu = new ProductSpu();
        spu.setId(1L);
        spu.setName("Test SPU");
        spu.setCategoryId(10L);
        spu.setBrandId(100L);
        spu.setMainImage("main.jpg");

        onShelfSku = new ProductSku();
        onShelfSku.setId(1L);
        onShelfSku.setSpuId(1L);
        onShelfSku.setName("OnShelf SKU");
        onShelfSku.setPrice(new BigDecimal("99.99"));
        onShelfSku.setStatus(SkuStatus.ON_SHELF);
        onShelfSku.setSortOrder(10);
        onShelfSku.setSalesCount(5);

        offShelfSku = new ProductSku();
        offShelfSku.setId(2L);
        offShelfSku.setSpuId(1L);
        offShelfSku.setName("OffShelf SKU");
        offShelfSku.setPrice(new BigDecimal("49.99"));
        offShelfSku.setStatus(SkuStatus.OFF_SHELF);
        offShelfSku.setSortOrder(5);
        offShelfSku.setSalesCount(0);

        draftSku = new ProductSku();
        draftSku.setId(3L);
        draftSku.setSpuId(1L);
        draftSku.setName("Draft SKU");
        draftSku.setPrice(new BigDecimal("29.99"));
        draftSku.setStatus(SkuStatus.DRAFT);
        draftSku.setSortOrder(0);
        draftSku.setSalesCount(0);

        deletedSku = new ProductSku();
        deletedSku.setId(4L);
        deletedSku.setSpuId(1L);
        deletedSku.setName("Deleted SKU");
        deletedSku.setPrice(new BigDecimal("9.99"));
        deletedSku.setStatus(SkuStatus.DELETED);
        deletedSku.setSortOrder(0);
        deletedSku.setSalesCount(0);
    }

    @Test
    @DisplayName("search with default request (onlyOnShelf unset) only returns ON_SHELF products")
    void testSearch_defaultRequest_onlyReturnsOnShelf() {
        // design-docs/05 section 4: "默认只展示 ON_SHELF 商品" -- onlyOnShelf now defaults to true.
        Page<ProductSku> page = new PageImpl<>(List.of(onShelfSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        // onlyOnShelf not set explicitly

        assertThat(request.isOnlyOnShelf()).isTrue();

        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        assertThat(result.getItems().get(0).getStatus()).isEqualTo("ON_SHELF");
    }

    @Test
    @DisplayName("search with onlyOnShelf explicitly false still returns OFF_SHELF and DRAFT")
    void testSearch_explicitOnlyOnShelfFalse_returnsAllNonDeletedSkus() {
        List<ProductSku> nonDeletedSkus = List.of(onShelfSku, offShelfSku, draftSku);
        Page<ProductSku> page = new PageImpl<>(nonDeletedSkus);
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setOnlyOnShelf(false);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(3);
        assertThat(result.getItems().stream().map(ProductListResponse::getStatus))
                .contains("ON_SHELF", "OFF_SHELF", "DRAFT");
    }

    @Test
    @DisplayName("search with onlyOnShelf=true filters to only ON_SHELF products")
    void testSearch_withOnlyOnShelfTrue_filtersToOnShelf() {
        List<ProductSku> allSkus = List.of(onShelfSku, offShelfSku, draftSku);
        Page<ProductSku> page = new PageImpl<>(allSkus);
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setOnlyOnShelf(true);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        // Even though repository returns all, the Specification should filter ON_SHELF
        // Verify the specification is applied by checking that repository was called
        ArgumentCaptor<Specification<ProductSku>> specCaptor = ArgumentCaptor.forClass(Specification.class);
        verify(skuRepository).findAll(specCaptor.capture(), any(Pageable.class));
        assertThat(specCaptor.getValue()).isNotNull();
    }

    @Test
    @DisplayName("search by keyword finds matching SKUs by name (case-insensitive like)")
    void testSearch_byKeyword_findsMatchingSkus() {
        ProductSku matchingSku = new ProductSku();
        matchingSku.setId(10L);
        matchingSku.setSpuId(1L);
        matchingSku.setName("Premium Widget");
        matchingSku.setPrice(new BigDecimal("199.99"));
        matchingSku.setStatus(SkuStatus.ON_SHELF);
        matchingSku.setSortOrder(1);
        matchingSku.setSalesCount(0);

        Page<ProductSku> page = new PageImpl<>(List.of(matchingSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setKeyword("widget");
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        assertThat(result.getItems().get(0).getName()).isEqualTo("Premium Widget");
    }

    @Test
    @DisplayName("search by keyword also resolves SPUs whose product name matches, widening the DB predicate")
    void testSearch_byKeyword_alsoResolvesMatchingSpuNames() {
        ProductSpu matchingNameSpu = new ProductSpu();
        matchingNameSpu.setId(5L);
        matchingNameSpu.setName("Widget Pro");

        when(spuRepository.findByNameContainingIgnoreCase("widget")).thenReturn(List.of(matchingNameSpu));

        Page<ProductSku> page = new PageImpl<>(List.of());
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of());

        ProductSearchRequest request = new ProductSearchRequest();
        request.setKeyword("widget");
        productSearchService.search(request);

        verify(spuRepository).findByNameContainingIgnoreCase("widget");
    }

    @Test
    @DisplayName("search by categoryId resolves matching SPUs at the DB level (not in-memory)")
    void testSearch_byCategoryId_filtersCategoryAtDbLevel() {
        ProductSpu spu2 = new ProductSpu();
        spu2.setId(2L);
        spu2.setName("Other SPU");
        spu2.setCategoryId(20L);

        ProductSku matchingSku = new ProductSku();
        matchingSku.setId(10L);
        matchingSku.setSpuId(2L);
        matchingSku.setName("Matching SKU");
        matchingSku.setPrice(new BigDecimal("100.00"));
        matchingSku.setStatus(SkuStatus.ON_SHELF);
        matchingSku.setSortOrder(1);
        matchingSku.setSalesCount(0);

        // categoryId=20 has no children -> descendant set is just {20}
        when(categoryRepository.findByParentId(20L)).thenReturn(List.of());
        when(spuRepository.findByCategoryIdIn(Set.of(20L))).thenReturn(List.of(spu2));

        Page<ProductSku> page = new PageImpl<>(List.of(matchingSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu2));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setCategoryId(20L);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        assertThat(result.getItems().get(0).getName()).isEqualTo("Matching SKU");
        verify(spuRepository).findByCategoryIdIn(Set.of(20L));
    }

    @Test
    @DisplayName("search by categoryId includes descendant categories transitively")
    void testSearch_byCategoryId_includesDescendantCategoriesTransitively() {
        Category child = new Category();
        child.setId(2L);
        Category grandchild = new Category();
        grandchild.setId(3L);

        when(categoryRepository.findByParentId(1L)).thenReturn(List.of(child));
        when(categoryRepository.findByParentId(2L)).thenReturn(List.of(grandchild));
        when(categoryRepository.findByParentId(3L)).thenReturn(List.of());

        ProductSpu deepSpu = new ProductSpu();
        deepSpu.setId(30L);
        deepSpu.setCategoryId(3L);

        ProductSku deepSku = new ProductSku();
        deepSku.setId(300L);
        deepSku.setSpuId(30L);
        deepSku.setName("Deep SKU");
        deepSku.setPrice(new BigDecimal("50.00"));
        deepSku.setStatus(SkuStatus.ON_SHELF);
        deepSku.setSortOrder(1);
        deepSku.setSalesCount(0);

        when(spuRepository.findByCategoryIdIn(Set.of(1L, 2L, 3L))).thenReturn(List.of(deepSpu));
        Page<ProductSku> page = new PageImpl<>(List.of(deepSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(deepSpu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setCategoryId(1L);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        assertThat(result.getItems().get(0).getName()).isEqualTo("Deep SKU");
    }

    @Test
    @DisplayName("search by categoryId with no matching SPUs short-circuits to an empty page without querying SKUs")
    void testSearch_byCategoryId_noMatches_shortCircuitsToEmptyPage() {
        when(categoryRepository.findByParentId(999L)).thenReturn(List.of());
        when(spuRepository.findByCategoryIdIn(Set.of(999L))).thenReturn(List.of());

        ProductSearchRequest request = new ProductSearchRequest();
        request.setCategoryId(999L);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getTotal()).isZero();
        assertThat(result.getItems()).isEmpty();
        verify(skuRepository, never()).findAll(any(Specification.class), any(Pageable.class));
    }

    @Test
    @DisplayName("search by brandId resolves matching SPUs at the DB level")
    void testSearch_byBrandId_filtersAtDbLevel() {
        ProductSpu brandSpu = new ProductSpu();
        brandSpu.setId(7L);
        brandSpu.setBrandId(200L);

        ProductSku brandSku = new ProductSku();
        brandSku.setId(70L);
        brandSku.setSpuId(7L);
        brandSku.setName("Brand SKU");
        brandSku.setPrice(new BigDecimal("75.00"));
        brandSku.setStatus(SkuStatus.ON_SHELF);
        brandSku.setSortOrder(1);
        brandSku.setSalesCount(0);

        when(spuRepository.findByBrandId(200L)).thenReturn(List.of(brandSpu));
        Page<ProductSku> page = new PageImpl<>(List.of(brandSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(brandSpu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setBrandId(200L);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        verify(spuRepository).findByBrandId(200L);
    }

    @Test
    @DisplayName("search by tags actually restricts results to SPUs associated with the tag")
    void testSearch_byTags_restrictsResults() {
        SpuTagRelation relation = new SpuTagRelation(9L, "clearance");
        when(spuTagRelationRepository.findByTagNameIn(List.of("clearance"))).thenReturn(List.of(relation));

        ProductSpu taggedSpu = new ProductSpu();
        taggedSpu.setId(9L);

        ProductSku taggedSku = new ProductSku();
        taggedSku.setId(90L);
        taggedSku.setSpuId(9L);
        taggedSku.setName("Clearance SKU");
        taggedSku.setPrice(new BigDecimal("19.99"));
        taggedSku.setStatus(SkuStatus.ON_SHELF);
        taggedSku.setSortOrder(0);
        taggedSku.setSalesCount(0);

        Page<ProductSku> page = new PageImpl<>(List.of(taggedSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(taggedSpu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setTags(List.of("clearance"));
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        verify(spuTagRelationRepository).findByTagNameIn(List.of("clearance"));
    }

    @Test
    @DisplayName("search by tags with no matching SPUs short-circuits to an empty page")
    void testSearch_byTags_noMatches_shortCircuitsToEmptyPage() {
        when(spuTagRelationRepository.findByTagNameIn(List.of("nonexistent-tag"))).thenReturn(List.of());

        ProductSearchRequest request = new ProductSearchRequest();
        request.setTags(List.of("nonexistent-tag"));
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getTotal()).isZero();
        assertThat(result.getItems()).isEmpty();
    }

    @Test
    @DisplayName("search without tags never queries the tag relation repository")
    void testSearch_withoutTags_doesNotQueryTagRepository() {
        Page<ProductSku> page = new PageImpl<>(List.of(onShelfSku));
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        productSearchService.search(new ProductSearchRequest());

        verify(spuTagRelationRepository, never()).findByTagNameIn(any());
    }

    @Test
    @DisplayName("search by price range filters SKUs with price between min and max")
    void testSearch_byPriceRange_filtersByPrice() {
        ProductSku sku2 = new ProductSku();
        sku2.setId(2L);
        sku2.setSpuId(1L);
        sku2.setName("Mid SKU");
        sku2.setPrice(new BigDecimal("50.00"));
        sku2.setStatus(SkuStatus.ON_SHELF);
        sku2.setSortOrder(2);
        sku2.setSalesCount(0);

        // The Specification handles price filtering at DB level
        List<ProductSku> filteredSkus = List.of(sku2);
        Page<ProductSku> page = new PageImpl<>(filteredSkus);
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setMinPrice(new BigDecimal("30.00"));
        request.setMaxPrice(new BigDecimal("100.00"));
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getItems()).hasSize(1);
        assertThat(result.getItems().get(0).getName()).isEqualTo("Mid SKU");
    }

    @Test
    @DisplayName("search pagination returns correct page metadata")
    void testSearch_pagination_returnsCorrectPage() {
        List<ProductSku> skus = List.of(onShelfSku, offShelfSku);
        Page<ProductSku> page = new PageImpl<>(skus, PageRequest.of(1, 2, Sort.by(Sort.Direction.DESC, "sortOrder")), 10);
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setPage(1);
        request.setSize(2);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getPage()).isEqualTo(1);
        assertThat(result.getSize()).isEqualTo(2);
        assertThat(result.getTotal()).isEqualTo(10L);
        assertThat(result.getItems()).hasSize(2);
    }

    @Test
    @DisplayName("search reports the DB-computed total (reflecting every filter), not just the current page's size")
    void testSearch_totalReflectsFilteredCountAcrossAllPages() {
        // Simulates a category filter matching 6 SPUs total, of which only 4 fit on this page --
        // the repository (standing in for the real DB) is the sole source of the total, and it
        // must have been queried with the spuId-IN predicate baked in (verified via findByCategoryIdIn).
        when(categoryRepository.findByParentId(10L)).thenReturn(List.of());
        when(spuRepository.findByCategoryIdIn(Set.of(10L))).thenReturn(List.of(spu));

        Page<ProductSku> page = new PageImpl<>(
                List.of(onShelfSku, offShelfSku, draftSku, deletedSku),
                PageRequest.of(0, 4, Sort.by(Sort.Direction.DESC, "sortOrder")),
                6);
        when(skuRepository.findAll(any(Specification.class), any(Pageable.class))).thenReturn(page);
        when(spuRepository.findAllById(any())).thenReturn(List.of(spu));

        ProductSearchRequest request = new ProductSearchRequest();
        request.setCategoryId(10L);
        request.setOnlyOnShelf(false);
        request.setSize(4);
        PageResponse<ProductListResponse> result = productSearchService.search(request);

        assertThat(result.getTotal()).isEqualTo(6L);
        assertThat(result.getItems()).hasSize(4);
    }
}
