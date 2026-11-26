package com.algobattle.auth.user;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<AppUser, Long> {
    Optional<AppUser> findByGithubId(Long githubId);

    Optional<AppUser> findByLoginIgnoreCase(String login);

    long countByRole(Role role);

    List<AppUser> findAllByOrderByLastLoginAtDesc();
}
