package com.algobattle.auth.config;

import java.nio.charset.StandardCharsets;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

/**
 * One HS256 key for minting and verifying, shared with the Python API.
 *
 * <p>The key is the UTF-8 bytes of SECRET_KEY, which is exactly what PyJWT
 * uses for a string key, so tokens verify in both directions.
 */
@Configuration
public class JwtConfig {

    @Bean
    SecretKey jwtSigningKey(AppProperties props) {
        String secret = props.jwtSecret();
        byte[] bytes = secret == null ? new byte[0] : secret.getBytes(StandardCharsets.UTF_8);
        // HS256 needs at least 256 bits; refuse to start rather than sign with
        // a weak or default key.
        if (bytes.length < 32) {
            throw new IllegalStateException(
                    "SECRET_KEY must be set (>= 32 bytes) and match the API's SECRET_KEY");
        }
        return new SecretKeySpec(bytes, "HmacSHA256");
    }

    @Bean
    JwtEncoder jwtEncoder(SecretKey key) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(key));
    }

    @Bean
    JwtDecoder jwtDecoder(SecretKey key) {
        return NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
    }
}
