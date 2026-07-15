package com.ecommerce.user.repository;

import com.ecommerce.user.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Spring Data JPA repository for {@link User}.
 */
@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmail(String email);

    Optional<User> findByPhone(String phone);

    /**
     * Nickname lookup for the login fallback (design-docs/04 §4: login validates
     * "用户名或邮箱" — LoginRequest's email field also accepts a nickname).
     * MUST stay a {@code findFirst…} derived query: nickname is not unique
     * (fixtures register every user as "Tester"), so a plain {@code findByNickname}
     * would blow up with NonUniqueResultException and 500 the login endpoint.
     * Deterministic tie-break: lowest id wins.
     */
    Optional<User> findFirstByNicknameOrderByIdAsc(String nickname);

    boolean existsByEmail(String email);

    boolean existsByPhone(String phone);
}
