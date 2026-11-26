package com.algobattle.auth.user;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "users")
public class AppUser {

    /** Prefix the API reserves for GitHub accounts (see backend/auth.py). */
    public static final String USERNAME_PREFIX = "gh_";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** GitHub's numeric id: stable across login renames, unlike the login. */
    @Column(nullable = false, unique = true)
    private Long githubId;

    @Column(nullable = false, unique = true)
    private String login;

    private String avatarUrl;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role = Role.USER;

    @Column(nullable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant lastLoginAt;

    protected AppUser() {
    }

    public AppUser(Long githubId, String login) {
        this.githubId = githubId;
        this.login = login;
        this.createdAt = Instant.now();
        this.lastLoginAt = this.createdAt;
    }

    /** The name the game knows this player by. */
    public String getUsername() {
        return USERNAME_PREFIX + login;
    }

    public Long getId() { return id; }
    public Long getGithubId() { return githubId; }
    public String getLogin() { return login; }
    public void setLogin(String login) { this.login = login; }
    public String getAvatarUrl() { return avatarUrl; }
    public void setAvatarUrl(String avatarUrl) { this.avatarUrl = avatarUrl; }
    public Role getRole() { return role; }
    public void setRole(Role role) { this.role = role; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getLastLoginAt() { return lastLoginAt; }
    public void setLastLoginAt(Instant lastLoginAt) { this.lastLoginAt = lastLoginAt; }
}
