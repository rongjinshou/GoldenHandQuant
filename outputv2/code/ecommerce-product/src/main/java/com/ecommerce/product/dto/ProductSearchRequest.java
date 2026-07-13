package com.ecommerce.product.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * Request DTO for product search.
 *
 * <p>The {@code onlyOnShelf} field defaults to {@code true} (design-docs/05 section 4:
 * "默认只展示 ON_SHELF 商品"), so anonymous browsing/search only ever surfaces ON_SHELF
 * products unless the caller explicitly opts in to seeing OFF_SHELF/DRAFT items.
 */
public class ProductSearchRequest {

    private String keyword;

    private Long categoryId;

    private Long brandId;

    private BigDecimal minPrice;

    private BigDecimal maxPrice;

    private List<String> tags;

    /**
     * When false, the search includes all non-DELETED products (ON_SHELF, OFF_SHELF, DRAFT).
     * When true, only ON_SHELF products are shown.
     * Defaults to true.
     */
    private boolean onlyOnShelf = true;

    private int page = 0;

    private int size = 20;

    public ProductSearchRequest() {
    }

    public String getKeyword() {
        return keyword;
    }

    public void setKeyword(String keyword) {
        this.keyword = keyword;
    }

    public Long getCategoryId() {
        return categoryId;
    }

    public void setCategoryId(Long categoryId) {
        this.categoryId = categoryId;
    }

    public Long getBrandId() {
        return brandId;
    }

    public void setBrandId(Long brandId) {
        this.brandId = brandId;
    }

    public BigDecimal getMinPrice() {
        return minPrice;
    }

    public void setMinPrice(BigDecimal minPrice) {
        this.minPrice = minPrice;
    }

    public BigDecimal getMaxPrice() {
        return maxPrice;
    }

    public void setMaxPrice(BigDecimal maxPrice) {
        this.maxPrice = maxPrice;
    }

    public List<String> getTags() {
        return tags;
    }

    public void setTags(List<String> tags) {
        this.tags = tags;
    }

    public boolean isOnlyOnShelf() {
        return onlyOnShelf;
    }

    public void setOnlyOnShelf(boolean onlyOnShelf) {
        this.onlyOnShelf = onlyOnShelf;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }
}
