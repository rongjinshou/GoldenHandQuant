package com.ecommerce.product.service;

import com.ecommerce.common.audit.AuditLogService;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.product.cache.ProductDetailCacheManager;
import com.ecommerce.product.dto.ProductDetailResponse;
import com.ecommerce.product.entity.Brand;
import com.ecommerce.product.entity.Category;
import com.ecommerce.product.entity.ProductSku;
import com.ecommerce.product.entity.ProductSpu;
import com.ecommerce.product.entity.SkuStatus;
import com.ecommerce.product.query.StockSummaryDto;
import com.ecommerce.product.repository.BrandRepository;
import com.ecommerce.product.repository.CategoryRepository;
import com.ecommerce.product.repository.ProductSkuRepository;
import com.ecommerce.product.repository.ProductSpuRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("ProductDetailService")
@ExtendWith(MockitoExtension.class)
class ProductDetailServiceTest {

    @Mock
    private ProductSkuRepository skuRepository;

    @Mock
    private ProductSpuRepository spuRepository;

    @Mock
    private BrandRepository brandRepository;

    @Mock
    private CategoryRepository categoryRepository;

    @Mock
    private ObjectMapper objectMapper;

    @Mock
    private StockInfoFetcher stockInfoFetcher;

    @Mock
    private ProductDetailCacheManager productDetailCacheManager;

    @Mock
    private AuditLogService auditLogService;

    @InjectMocks
    private ProductDetailService productDetailService;

    private ProductSku sku;
    private ProductSpu spu;
    private Brand brand;
    private Category category;
    private StockSummaryDto stockSummary;

    @BeforeEach
    void setUp() {
        // Cache miss by default so existing tests exercise the full build-and-cache path;
        // individual tests may override this stub to exercise the cache-hit path instead.
        // Marked lenient because the cache-eviction test below builds its own real
        // ProductDetailCacheManager and never touches this mock.
        lenient().when(productDetailCacheManager.get(anyLong())).thenReturn(null);

        sku = new ProductSku();
        sku.setId(1L);
        sku.setSpuId(10L);
        sku.setName("Test SKU");
        sku.setPrice(new BigDecimal("99.99"));
        sku.setStatus(SkuStatus.ON_SHELF);
        sku.setSpecs("{\"color\":\"red\",\"size\":\"L\"}");

        spu = new ProductSpu();
        spu.setId(10L);
        spu.setName("Test SPU");
        spu.setBrandId(100L);
        spu.setCategoryId(200L);
        spu.setImages("[\"img1.jpg\",\"img2.jpg\"]");

        brand = new Brand();
        brand.setId(100L);
        brand.setName("Test Brand");

        category = new Category();
        category.setId(200L);
        category.setName("Test Category");

        stockSummary = new StockSummaryDto(999, 0);
    }

    @Test
    @DisplayName("getProductDetail returns SKU with stock summary from StockInfoFetcher")
    void testGetProductDetail_returnsSkuWithStockSummary() throws JsonProcessingException {
        when(skuRepository.findById(1L)).thenReturn(Optional.of(sku));
        when(spuRepository.findById(10L)).thenReturn(Optional.of(spu));
        when(stockInfoFetcher.fetch(1L)).thenReturn(stockSummary);
        when(brandRepository.findById(100L)).thenReturn(Optional.of(brand));
        when(categoryRepository.findById(200L)).thenReturn(Optional.of(category));
        when(objectMapper.readValue(eq("{\"color\":\"red\",\"size\":\"L\"}"), any(TypeReference.class)))
                .thenReturn(Map.of("color", "red", "size", "L"));
        when(objectMapper.readValue(eq("[\"img1.jpg\",\"img2.jpg\"]"), any(TypeReference.class)))
                .thenReturn(List.of("img1.jpg", "img2.jpg"));

        ProductDetailResponse result = productDetailService.getProductDetail(1L);

        assertThat(result.getSkuId()).isEqualTo(1L);
        assertThat(result.getSpuId()).isEqualTo(10L);
        assertThat(result.getName()).isEqualTo("Test SKU");
        assertThat(result.getPrice()).isEqualByComparingTo(new BigDecimal("99.99"));
        assertThat(result.getStatus()).isEqualTo("ON_SHELF");
        assertThat(result.getSpuName()).isEqualTo("Test SPU");
        assertThat(result.getBrand()).isEqualTo("Test Brand");
        assertThat(result.getCategory()).isEqualTo("Test Category");
        // Verify stock summary in product detail.
        assertThat(result.getStockSummary().getAvailableStock()).isEqualTo(999);
        assertThat(result.getStockSummary().getReservedStock()).isZero();

        // Verify StockInfoFetcher was used
        verify(stockInfoFetcher).fetch(1L);

        // Verify the freshly-built response was stored in the 10-minute cache
        verify(productDetailCacheManager).put(eq(1L), eq(result));
    }

    @Test
    @DisplayName("getProductDetail returns the cached response without touching repositories on a cache hit")
    void testGetProductDetail_cacheHit_skipsRepositories() {
        ProductDetailResponse cached = new ProductDetailResponse();
        cached.setSkuId(1L);
        cached.setName("Cached SKU");
        when(productDetailCacheManager.get(1L)).thenReturn(cached);

        ProductDetailResponse result = productDetailService.getProductDetail(1L);

        assertThat(result).isSameAs(cached);
        verify(skuRepository, never()).findById(any());
        verify(spuRepository, never()).findById(any());
        verify(stockInfoFetcher, never()).fetch(any());
        verify(productDetailCacheManager, never()).put(any(), any());
    }

    @Test
    @DisplayName("getProductDetail throws ResourceNotFoundException when SKU not found")
    void testGetProductDetail_throwsWhenSkuNotFound() {
        when(skuRepository.findById(999L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> productDetailService.getProductDetail(999L))
                .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    @DisplayName("getProductDetail throws ResourceNotFoundException when SPU not found")
    void testGetProductDetail_throwsWhenSpuNotFound() {
        when(skuRepository.findById(1L)).thenReturn(Optional.of(sku));
        when(spuRepository.findById(10L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> productDetailService.getProductDetail(1L))
                .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    @DisplayName("getProductDetail handles null brand and category gracefully")
    void testGetProductDetail_handlesNullBrandAndCategory() throws JsonProcessingException {
        spu.setBrandId(null);
        spu.setCategoryId(null);

        when(skuRepository.findById(1L)).thenReturn(Optional.of(sku));
        when(spuRepository.findById(10L)).thenReturn(Optional.of(spu));
        when(stockInfoFetcher.fetch(1L)).thenReturn(stockSummary);
        when(objectMapper.readValue(eq("{\"color\":\"red\",\"size\":\"L\"}"), any(TypeReference.class)))
                .thenReturn(Map.of("color", "red", "size", "L"));
        when(objectMapper.readValue(eq("[\"img1.jpg\",\"img2.jpg\"]"), any(TypeReference.class)))
                .thenReturn(List.of("img1.jpg", "img2.jpg"));

        ProductDetailResponse result = productDetailService.getProductDetail(1L);

        assertThat(result.getBrand()).isNull();
        assertThat(result.getCategory()).isNull();
    }

    @Test
    @DisplayName("getProductDetail handles empty specs and images gracefully")
    void testGetProductDetail_handlesEmptySpecsAndImages() {
        sku.setSpecs(null);
        spu.setImages(null);

        when(skuRepository.findById(1L)).thenReturn(Optional.of(sku));
        when(spuRepository.findById(10L)).thenReturn(Optional.of(spu));
        when(stockInfoFetcher.fetch(1L)).thenReturn(stockSummary);
        when(brandRepository.findById(100L)).thenReturn(Optional.of(brand));
        when(categoryRepository.findById(200L)).thenReturn(Optional.of(category));

        ProductDetailResponse result = productDetailService.getProductDetail(1L);

        assertThat(result.getSpecs()).isEmpty();
        assertThat(result.getImages()).isEmpty();
    }

    @Test
    @DisplayName("product detail cache evicts the stale entry when the SKU goes off-shelf via SkuService")
    void testProductDetailCache_evictsOnOffShelf() throws JsonProcessingException {
        // Wire a *real* cache manager (backed by a real Caffeine cache) shared between a
        // real ProductDetailService and a real SkuService, so this test proves actual
        // cache-hit / cache-eviction behavior end-to-end rather than mocked interactions.
        ProductDetailCacheManager realCacheManager =
                new ProductDetailCacheManager(Caffeine.newBuilder().build());

        ProductDetailService realProductDetailService = new ProductDetailService(
                skuRepository, spuRepository, brandRepository, categoryRepository,
                objectMapper, stockInfoFetcher, realCacheManager);
        SkuService realSkuService = new SkuService(
                skuRepository, spuRepository, objectMapper, auditLogService, realCacheManager);

        when(skuRepository.findById(1L)).thenReturn(Optional.of(sku));
        when(spuRepository.findById(10L)).thenReturn(Optional.of(spu));
        when(stockInfoFetcher.fetch(1L)).thenReturn(stockSummary);
        when(brandRepository.findById(100L)).thenReturn(Optional.of(brand));
        when(categoryRepository.findById(200L)).thenReturn(Optional.of(category));
        when(objectMapper.readValue(eq("{\"color\":\"red\",\"size\":\"L\"}"), any(TypeReference.class)))
                .thenReturn(Map.of("color", "red", "size", "L"));
        when(objectMapper.readValue(eq("[\"img1.jpg\",\"img2.jpg\"]"), any(TypeReference.class)))
                .thenReturn(List.of("img1.jpg", "img2.jpg"));

        ProductDetailResponse before = realProductDetailService.getProductDetail(1L);
        assertThat(before.getStatus()).isEqualTo("ON_SHELF");

        // Second call is served from the cache: no additional repository round-trip.
        realProductDetailService.getProductDetail(1L);
        verify(skuRepository, times(1)).findById(1L);

        // SkuService.offShelf mutates the same underlying ProductSku instance and must
        // evict the cache entry for this skuId. (offShelf itself performs one findById
        // via SkuService.findSku, bringing the running total to 2 before the next
        // getProductDetail call.)
        realSkuService.offShelf(1L, "admin-1");
        verify(skuRepository, times(2)).findById(1L);

        ProductDetailResponse after = realProductDetailService.getProductDetail(1L);
        assertThat(after.getStatus()).isEqualTo("OFF_SHELF");
        verify(skuRepository, times(3)).findById(1L);
    }
}
