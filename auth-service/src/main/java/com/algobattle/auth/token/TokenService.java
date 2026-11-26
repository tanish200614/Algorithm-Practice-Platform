package com.algobattle.auth.token;

import java.time.Instant;

import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.stereotype.Service;

import com.algobattle.auth.config.AppProperties;
import com.algobattle.auth.user.AppUser;

/**
 * Mints the token the browser carries to both services.
 *
 * <p>Claim shape is the contract with backend/auth.py: {@code sub} is the
 * game username, {@code exp} is checked by PyJWT, and {@code roles} drives
 * role checks on both sides. Roles are baked in at issue time, so a role
 * change takes effect at the user's next login.
 */
@Service
public class TokenService {

    public static final String ISSUER = "algobattle-auth";

    private final JwtEncoder encoder;
    private final AppProperties props;

    public TokenService(JwtEncoder encoder, AppProperties props) {
        this.encoder = encoder;
        this.props = props;
    }

    public String issue(AppUser user) {
        Instant now = Instant.now();
        JwtClaimsSet.Builder claims = JwtClaimsSet.builder()
                .issuer(ISSUER)
                .subject(user.getUsername())
                .issuedAt(now)
                .expiresAt(now.plus(props.tokenTtl()))
                .claim("roles", user.getRole().grants())
                .claim("provider", "github");
        if (user.getAvatarUrl() != null) {
            claims.claim("avatar_url", user.getAvatarUrl());
        }
        JwsHeader header = JwsHeader.with(MacAlgorithm.HS256).type("JWT").build();
        return encoder.encode(JwtEncoderParameters.from(header, claims.build())).getTokenValue();
    }
}
