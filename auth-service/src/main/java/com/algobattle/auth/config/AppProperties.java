package com.algobattle.auth.config;

import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app")
public record AppProperties(
        String jwtSecret,
        Duration tokenTtl,
        String frontendUrl,
        List<String> allowedOrigins,
        Set<String> adminLogins) {

    public AppProperties {
        frontendUrl = frontendUrl == null ? "" : frontendUrl.replaceAll("/+$", "");
        allowedOrigins = allowedOrigins == null ? List.of()
                : allowedOrigins.stream().map(String::trim).filter(s -> !s.isEmpty()).toList();
        // GitHub logins are case-insensitive.
        adminLogins = adminLogins == null ? Set.of()
                : adminLogins.stream().map(s -> s.trim().toLowerCase(Locale.ROOT))
                        .filter(s -> !s.isEmpty()).collect(Collectors.toUnmodifiableSet());
        if (tokenTtl == null) tokenTtl = Duration.ofDays(7);
    }

    public boolean isBootstrapAdmin(String login) {
        return login != null && adminLogins.contains(login.toLowerCase(Locale.ROOT));
    }
}
