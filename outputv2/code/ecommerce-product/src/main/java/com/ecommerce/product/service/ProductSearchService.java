package com.ecommerce.product.service;

import com.ecommerce.common.dto.PageResponse;
import com.ecommerce.product.dto.ProductListResponse;
import com.ecommerce.product.dto.ProductSearchRequest;
import com.ecommerce.product.entity.ProductSku;
import com.ecommerce.product.entity.ProductSpu;
import com.ecommerce.product.entity.SkuStatus;
import com.ecommerce.product.entity.SpuTagRelation;
import com.ecommerce.product.repository.CategoryRepository;
import com.ecommerce.product.repository.ProductSkuRepository;
import com.ecommerce.product.repository.ProductSpuRepository;
import com.ecommerce.product.repository.SpuTagRelationRepository;
import jakarta.persistence.criteria.Predicate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Handles product search with keyword, category, brand, price range, and tag filters.
 *
 * <p>Only {@code ON_SHELF} products are returned by default (design-docs/05 section 4:
 * "默认只展示 ON_SHELF 商品"); callers may explicitly pass {@code onlyOnShelf=false} to also
 * see OFF_SHELF/DRAFT items. Category filtering includes all descendant categories. Category,
 * brand, and tag filters are all resolved to a restricted set of SPU ids and pushed into the
 * database-level {@link Specification} (never applied in-memory after the page is fetched),
 * so that both the returned page contents and the reported {@code total} consistently reflect
 * every active filter.
 */
@Service
public class ProductSearchService {

    private static final Logger log = LoggerFactory.getLogger(ProductSearchService.class);

    private final ProductSkuRepository skuRepository;
    private final ProductSpuRepository spuRepository;
    private final CategoryRepository categoryRepository;
    private final SpuTagRelationRepository spuTagRelationRepository;

    public ProductSearchService(ProductSkuRepository skuRepository,
                                ProductSpuRepository spuRepository,
                                CategoryRepository categoryRepository,
                                SpuTagRelationRepository spuTagRelationRepository) {
        this.skuRepository = skuRepository;
        this.spuRepository = spuRepository;
        this.categoryRepository = categoryRepository;
        this.spuTagRelationRepository = spuTagRelationRepository;
    }

    /**
     * Searches for products matching the given criteria.
     */
    @Transactional(readOnly = true)
    public PageResponse<ProductListResponse> search(ProductSearchRequest request) {
        log.debug("Product search: keyword={}, categoryId={}, brandId={}, tags={}, onlyOnShelf={}",
                request.getKeyword(), request.getCategoryId(), request.getBrandId(),
                request.getTags(), request.isOnlyOnShelf());

        // Resolve category/brand/tag filters to a restricted set of matching SPU ids
        // *before* querying, so the restriction is applied at the database level rather
        // than in-memory after the page is fetched (which would corrupt both the page
        // contents and the reported total for any page beyond the first).
        Set<Long> allowedSpuIds = resolveAllowedSpuIds(request);
        if (allowedSpuIds != null && allowedSpuIds.isEmpty()) {
            return PageResponse.of(request.getPage(), request.getSize(), 0L, Collections.emptyList());
        }

        Set<Long> keywordSpuIds = resolveKeywordSpuIds(request.getKeyword());

        Specification<ProductSku> spec = buildSpecification(request, allowedSpuIds, keywordSpuIds);

        PageRequest pageRequest = PageRequest.of(
                request.getPage(),
                request.getSize(),
                Sort.by(Sort.Direction.DESC, "sortOrder"));

        Page<ProductSku> page = skuRepository.findAll(spec, pageRequest);

        // Load SPU data purely for display purposes (name/image) -- every filter has
        // already been applied at the database level above, so no further in-memory
        // filtering happens here.
        List<Long> spuIds = page.getContent().stream()
                .map(ProductSku::getSpuId)
                .distinct()
                .collect(Collectors.toList());
        Map<Long, ProductSpu> spuMap = spuRepository.findAllById(spuIds).stream()
                .collect(Collectors.toMap(ProductSpu::getId, spu -> spu));

        List<ProductListResponse> items = page.getContent().stream()
                .map(sku -> toListResponse(sku, spuMap.get(sku.getSpuId())))
                .collect(Collectors.toList());

        return PageResponse.of(request.getPage(), request.getSize(), page.getTotalElements(), items);
    }

    /**
     * Resolves the set of SPU ids allowed by the category/brand/tag filters combined
     * (intersection of each active filter). Returns {@code null} when none of these
     * filters are present, meaning no restriction should be applied at all.
     */
    private Set<Long> resolveAllowedSpuIds(ProductSearchRequest request) {
        Set<Long> allowed = null;

        if (request.getCategoryId() != null) {
            Set<Long> categoryIds = resolveDescendantCategoryIds(request.getCategoryId());
            Set<Long> spuIds = spuRepository.findByCategoryIdIn(categoryIds).stream()
                    .map(ProductSpu::getId)
                    .collect(Collectors.toSet());
            allowed = spuIds;
        }

        if (request.getBrandId() != null) {
            Set<Long> spuIds = spuRepository.findByBrandId(request.getBrandId()).stream()
                    .map(ProductSpu::getId)
                    .collect(Collectors.toSet());
            allowed = intersect(allowed, spuIds);
        }

        List<String> tags = sanitizedTags(request.getTags());
        if (!tags.isEmpty()) {
            Set<Long> spuIds = spuTagRelationRepository.findByTagNameIn(tags).stream()
                    .map(SpuTagRelation::getSpuId)
                    .collect(Collectors.toSet());
            allowed = intersect(allowed, spuIds);
        }

        return allowed;
    }

    private List<String> sanitizedTags(List<String> tags) {
        if (tags == null || tags.isEmpty()) {
            return Collections.emptyList();
        }
        return tags.stream()
                .filter(tag -> tag != null && !tag.isBlank())
                .collect(Collectors.toList());
    }

    /**
     * Intersects {@code other} into {@code current}. When {@code current} is {@code null}
     * (no restriction applied yet), {@code other} becomes the new restriction.
     */
    private Set<Long> intersect(Set<Long> current, Set<Long> other) {
        if (current == null) {
            return other;
        }
        Set<Long> result = new HashSet<>(current);
        result.retainAll(other);
        return result;
    }

    /**
     * Resolves the set of SPU ids whose SPU-level name OR description ("卖点") matches
     * the keyword, so that search can match on the SKU name, the SPU name, or the SPU's
     * selling-point description -- per design-docs/05 section 4 ("keyword | 商品名称、
     * 卖点模糊匹配"). Returns an empty set when there is no keyword or nothing matches at
     * the SPU level; an empty set here only widens (never narrows) the keyword predicate,
     * so it never excludes SKU-name matches.
     */
    private Set<Long> resolveKeywordSpuIds(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return Collections.emptySet();
        }
        Set<Long> ids = spuRepository.findByNameContainingIgnoreCase(keyword).stream()
                .map(ProductSpu::getId)
                .collect(Collectors.toCollection(HashSet::new));
        spuRepository.findByDescriptionContainingIgnoreCase(keyword)
                .forEach(spu -> ids.add(spu.getId()));
        return ids;
    }

    /**
     * Resolves the category itself plus every descendant category (recursively), so that
     * filtering by a parent category also includes products filed under any sub-category
     * (design-docs/05 section 4: "categoryId | 类目过滤，包含子类目").
     */
    private Set<Long> resolveDescendantCategoryIds(Long rootCategoryId) {
        Set<Long> result = new HashSet<>();
        Deque<Long> toVisit = new ArrayDeque<>();
        toVisit.add(rootCategoryId);
        while (!toVisit.isEmpty()) {
            Long current = toVisit.poll();
            if (!result.add(current)) {
                continue;
            }
            categoryRepository.findByParentId(current).forEach(child -> toVisit.add(child.getId()));
        }
        return result;
    }

    /**
     * Builds a JPA Specification for the search criteria. Category, brand, and tag filters
     * are expressed as a {@code spuId IN (...)} predicate resolved ahead of time (see
     * {@link #resolveAllowedSpuIds}), and keyword matching is widened with an OR'd
     * {@code spuId IN (...)} predicate (see {@link #resolveKeywordSpuIds}), so that every
     * filter -- including pagination totals -- is evaluated by the database in one query.
     */
    private Specification<ProductSku> buildSpecification(ProductSearchRequest request,
                                                          Set<Long> allowedSpuIds,
                                                          Set<Long> keywordSpuIds) {
        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (request.isOnlyOnShelf()) {
                predicates.add(cb.equal(root.get("status"), SkuStatus.ON_SHELF));
            } else {
                // Explicitly opted out of the ON_SHELF-only default: show all non-DELETED products.
                predicates.add(cb.notEqual(root.get("status"), SkuStatus.DELETED));
            }

            if (request.getKeyword() != null && !request.getKeyword().isBlank()) {
                Predicate skuNameMatches = cb.like(cb.lower(root.get("name")),
                        "%" + request.getKeyword().toLowerCase() + "%");
                if (!keywordSpuIds.isEmpty()) {
                    predicates.add(cb.or(skuNameMatches, root.get("spuId").in(keywordSpuIds)));
                } else {
                    predicates.add(skuNameMatches);
                }
            }

            if (request.getMinPrice() != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("price"), request.getMinPrice()));
            }

            if (request.getMaxPrice() != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("price"), request.getMaxPrice()));
            }

            if (allowedSpuIds != null) {
                predicates.add(root.get("spuId").in(allowedSpuIds));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }

    private ProductListResponse toListResponse(ProductSku sku, ProductSpu spu) {
        ProductListResponse response = new ProductListResponse();
        response.setSkuId(sku.getId());
        response.setSpuId(sku.getSpuId());
        response.setName(sku.getName());
        response.setPrice(sku.getPrice());
        response.setStatus(sku.getStatus().name());
        response.setMainImage(spu != null ? spu.getMainImage() : sku.getImage());
        response.setSalesCount(sku.getSalesCount());
        return response;
    }
}
