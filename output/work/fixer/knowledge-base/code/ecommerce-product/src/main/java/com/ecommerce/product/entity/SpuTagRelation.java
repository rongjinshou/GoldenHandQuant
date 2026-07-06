package com.ecommerce.product.entity;

import com.ecommerce.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

/**
 * Associates a {@link ProductSpu} with a tag name for search/filtering purposes
 * (design-docs/05 section 4: "tags | 标签过滤"). Tag names are stored directly
 * (rather than a foreign key to {@link ProductTag}) since {@code ProductSearchRequest#getTags()}
 * is a list of tag names, not tag ids — consistent with the rest of this module's
 * id-based (not JPA-relationship-based) cross-entity references.
 */
@Entity
@Table(name = "product_spu_tag")
public class SpuTagRelation extends BaseEntity {

    @Column(name = "spu_id", nullable = false)
    private Long spuId;

    @Column(name = "tag_name", nullable = false, length = 64)
    private String tagName;

    public SpuTagRelation() {
    }

    public SpuTagRelation(Long spuId, String tagName) {
        this.spuId = spuId;
        this.tagName = tagName;
    }

    public Long getSpuId() {
        return spuId;
    }

    public void setSpuId(Long spuId) {
        this.spuId = spuId;
    }

    public String getTagName() {
        return tagName;
    }

    public void setTagName(String tagName) {
        this.tagName = tagName;
    }
}
