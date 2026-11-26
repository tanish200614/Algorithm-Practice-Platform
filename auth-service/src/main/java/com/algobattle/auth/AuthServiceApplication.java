package com.algobattle.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * GitHub login for AlgoBattle.
 *
 * <p>Runs the OAuth2 authorization-code flow against GitHub, records the user
 * and their role, and hands the browser an HS256 JWT signed with the key the
 * FastAPI backend already verifies. The Python API therefore needs no OAuth
 * code of its own: a GitHub user's token is just a token with a "roles" claim.
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class AuthServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(AuthServiceApplication.class, args);
    }
}
