package com.ecommerce.product.repository;

import com.ecommerce.product.entity.SpuTagRelation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface SpuTagRelationRepository extends JpaRepository<SpuTagRelation, Long> {

    List<SpuTagRelation> findByTagNameIn(Collection<String> tagNames);
}
