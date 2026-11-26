package com.algobattle.auth.config;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import com.algobattle.auth.web.OAuth2LoginSuccessHandler;

/**
 * Two filter chains:
 *
 * <ol>
 *   <li>The JSON API ({@code /me}, {@code /admin/**}): stateless, bearer JWT
 *       only, 401/403 instead of redirects. Roles come from the token's
 *       "roles" claim, and {@code /admin/**} requires ADMIN.</li>
 *   <li>Everything else: the GitHub OAuth2 login flow. It needs a short-lived
 *       session to carry the OAuth state across the redirect to GitHub; the
 *       success handler throws that session away once the JWT is issued.</li>
 * </ol>
 */
@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    @Order(1)
    SecurityFilterChain apiChain(HttpSecurity http) throws Exception {
        http.securityMatcher("/me", "/admin/**")
                .cors(Customizer.withDefaults())
                // Bearer tokens in a header aren't sent automatically by the
                // browser, so CSRF doesn't apply to this chain.
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/admin/**").hasRole("ADMIN")
                        .anyRequest().authenticated())
                .oauth2ResourceServer(rs -> rs.jwt(jwt -> jwt.jwtAuthenticationConverter(rolesFromClaim())));
        return http.build();
    }

    @Bean
    @Order(2)
    SecurityFilterChain loginChain(HttpSecurity http, OAuth2LoginSuccessHandler onSuccess,
                                   AppProperties props) throws Exception {
        AuthenticationFailureHandler onFailure = (req, res, ex) -> res.sendRedirect(
                props.frontendUrl() + "/#auth_error="
                        + URLEncoder.encode("GitHub login failed", StandardCharsets.UTF_8));

        http.cors(Customizer.withDefaults())
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health", "/error").permitAll()
                        .anyRequest().authenticated())
                .oauth2Login(login -> login.successHandler(onSuccess).failureHandler(onFailure));
        return http.build();
    }

    /** "roles": ["USER", "ADMIN"]  ->  ROLE_USER, ROLE_ADMIN. */
    static JwtAuthenticationConverter rolesFromClaim() {
        JwtGrantedAuthoritiesConverter authorities = new JwtGrantedAuthoritiesConverter();
        authorities.setAuthoritiesClaimName("roles");
        authorities.setAuthorityPrefix("ROLE_");
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(authorities);
        return converter;
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource(AppProperties props) {
        CorsConfiguration cors = new CorsConfiguration();
        cors.setAllowedOrigins(props.allowedOrigins());
        cors.setAllowedMethods(List.of("GET", "POST", "PUT", "OPTIONS"));
        cors.setAllowedHeaders(List.of("Authorization", "Content-Type"));
        cors.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", cors);
        return source;
    }
}
