package com.algobattle.auth.web;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.algobattle.auth.user.AppUser;
import com.algobattle.auth.user.Role;
import com.algobattle.auth.user.UserService;

@RestController
public class AccountController {

    private final UserService users;

    public AccountController(UserService users) {
        this.users = users;
    }

    /** Who the bearer token says you are. Works for password-login tokens too. */
    @GetMapping("/me")
    public Map<String, Object> me(@AuthenticationPrincipal Jwt jwt) {
        List<String> roles = jwt.getClaimAsStringList("roles");
        return Map.of(
                "username", jwt.getSubject(),
                "roles", roles == null ? List.of("USER") : roles,
                "provider", jwt.hasClaim("provider") ? jwt.getClaimAsString("provider") : "password");
    }

    public record UserView(String username, String login, Role role, String avatarUrl,
                           Instant createdAt, Instant lastLoginAt) {
        static UserView of(AppUser u) {
            return new UserView(u.getUsername(), u.getLogin(), u.getRole(), u.getAvatarUrl(),
                    u.getCreatedAt(), u.getLastLoginAt());
        }
    }

    public record RoleChange(@NotNull Role role) {
    }

    // The filter chain already requires ADMIN for /admin/**; @PreAuthorize
    // repeats it at the method so the rule survives a URL-mapping change.
    @PreAuthorize("hasRole('ADMIN')")
    @GetMapping("/admin/users")
    public List<UserView> listUsers() {
        return users.all().stream().map(UserView::of).toList();
    }

    @PreAuthorize("hasRole('ADMIN')")
    @PutMapping("/admin/users/{login}/role")
    public UserView setRole(@PathVariable String login, @Valid @RequestBody RoleChange change) {
        return UserView.of(users.setRole(login, change.role()));
    }
}
