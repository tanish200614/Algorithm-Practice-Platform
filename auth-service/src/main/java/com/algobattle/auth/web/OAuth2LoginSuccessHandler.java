package com.algobattle.auth.web;

import java.io.IOException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

import com.algobattle.auth.config.AppProperties;
import com.algobattle.auth.token.TokenService;
import com.algobattle.auth.user.AppUser;
import com.algobattle.auth.user.UserService;

/**
 * Last step of the GitHub login: record the user, mint a JWT, and send the
 * browser back to the frontend with it.
 *
 * <p>The token goes in the URL fragment ({@code #token=...}), which browsers
 * never send to a server or put in a Referer header, so it doesn't land in
 * access logs on the way to a frontend hosted on a different domain.
 */
@Component
public class OAuth2LoginSuccessHandler implements AuthenticationSuccessHandler {

    private final UserService users;
    private final TokenService tokens;
    private final AppProperties props;

    public OAuth2LoginSuccessHandler(UserService users, TokenService tokens, AppProperties props) {
        this.users = users;
        this.tokens = tokens;
        this.props = props;
    }

    @Override
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response,
                                        Authentication authentication) throws IOException {
        OAuth2User github = (OAuth2User) authentication.getPrincipal();
        Number id = github.getAttribute("id");
        String login = github.getAttribute("login");
        String avatar = github.getAttribute("avatar_url");

        AppUser user = users.recordLogin(id.longValue(), login, avatar);
        String token = tokens.issue(user);

        // The session only existed to carry OAuth state across the redirect;
        // from here on the JWT is the credential.
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        SecurityContextHolder.clearContext();

        response.sendRedirect(props.frontendUrl() + "/#token=" + token);
    }
}
