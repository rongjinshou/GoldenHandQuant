package com.ecommerce.product.repository;

import com.ecommerce.product.entity.ProductSpu;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface ProductSpuRepository extends JpaRepository<ProductSpu, Long> {

    Optional<ProductSpu> findBySpuCode(String spuCode);

    List<ProductSpu> findByCategoryIdIn(Collection<Long> categoryIds);

    List<ProductSpu> findByBrandId(Long brandId);

    List<ProductSpu> findByNameContainingIgnoreCase(String keyword);
}
