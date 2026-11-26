package com.algobattle.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.user.DefaultOAuth2User;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.server.ResponseStatusException;

import com.algobattle.auth.token.TokenService;
import com.algobattle.auth.user.AppUser;
import com.algobattle.auth.user.Role;
import com.algobattle.auth.user.UserRepository;
import com.algobattle.auth.user.UserService;
import com.algobattle.auth.web.OAuth2LoginSuccessHandler;

@SpringBootTest(properties = {
        "app.jwt-secret=" + AuthServiceTests.SECRET,
        "app.frontend-url=https://play.example.com/",
        "app.admin-logins=BossLogin",
        "spring.datasource.url=jdbc:h2:mem:authtest;DB_CLOSE_DELAY=-1",
        "spring.security.oauth2.client.registration.github.client-id=test-client",
        "spring.security.oauth2.client.registration.github.client-secret=test-secret",
})
@AutoConfigureMockMvc
class AuthServiceTests {

    static final String SECRET = "test-secret-that-is-at-least-32-bytes-long!!";

    /**
     * Minted by PyJWT with SECRET, exactly as backend/auth.py does for a
     * password login: {"sub": "ada", "exp": 4102444800}, no roles claim.
     */
    static final String PYTHON_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            + "eyJzdWIiOiJhZGEiLCJleHAiOjQxMDI0NDQ4MDB9."
            + "NRz-0eLtvqZrPF_sHZtqjpS9au-XYjm54FrFYdezgqM";

    @Autowired MockMvc mvc;
    @Autowired UserService users;
    @Autowired UserRepository repo;
    @Autowired TokenService tokens;
    @Autowired JwtDecoder decoder;
    @Autowired OAuth2LoginSuccessHandler onSuccess;

    @BeforeEach
    void clean() {
        repo.deleteAll();
    }

    String bearer(AppUser u) {
        return "Bearer " + tokens.issue(u);
    }

    @Nested
    class RoleBasedAccess {
        @Test
        void anonymousIs401() throws Exception {
            mvc.perform(get("/me")).andExpect(status().isUnauthorized());
            mvc.perform(get("/admin/users")).andExpect(status().isUnauthorized());
        }

        @Test
        void usersCanSeeThemselvesButNotAdmin() throws Exception {
            AppUser u = users.recordLogin(1, "octocat", null);
            mvc.perform(get("/me").header("Authorization", bearer(u)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.username").value("gh_octocat"))
                    .andExpect(jsonPath("$.roles[0]").value("USER"));
            mvc.perform(get("/admin/users").header("Authorization", bearer(u)))
                    .andExpect(status().isForbidden());
        }

        @Test
        void adminsCanListAndChangeRoles() throws Exception {
            AppUser admin = users.recordLogin(1, "bosslogin", null);
            users.recordLogin(2, "octocat", null);
            mvc.perform(get("/admin/users").header("Authorization", bearer(admin)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(2));
            mvc.perform(put("/admin/users/octocat/role").header("Authorization", bearer(admin))
                            .contentType(MediaType.APPLICATION_JSON).content("{\"role\":\"ADMIN\"}"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.role").value("ADMIN"));
        }

        @Test
        void badRoleIs400() throws Exception {
            AppUser admin = users.recordLogin(1, "bosslogin", null);
            mvc.perform(put("/admin/users/bosslogin/role").header("Authorization", bearer(admin))
                            .contentType(MediaType.APPLICATION_JSON).content("{\"role\":\"GOD\"}"))
                    .andExpect(status().isBadRequest());
        }

        @Test
        void tokenFromTheWrongKeyIs401() throws Exception {
            // Same token with the last signature character changed.
            String token = tokens.issue(users.recordLogin(1, "bosslogin", null));
            char last = token.charAt(token.length() - 1);
            String tampered = token.substring(0, token.length() - 1) + (last == 'A' ? 'B' : 'A');
            mvc.perform(get("/admin/users").header("Authorization", "Bearer " + tampered))
                    .andExpect(status().isUnauthorized());
        }
    }

    @Nested
    class InteropWithThePythonApi {
        @Test
        void passwordLoginTokensAreAcceptedAsPlainUsers() throws Exception {
            mvc.perform(get("/me").header("Authorization", "Bearer " + PYTHON_TOKEN))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.username").value("ada"))
                    .andExpect(jsonPath("$.provider").value("password"));
            mvc.perform(get("/admin/users").header("Authorization", "Bearer " + PYTHON_TOKEN))
                    .andExpect(status().isForbidden());
        }

        @Test
        void issuedTokensCarryTheClaimsTheApiReads() {
            AppUser u = users.recordLogin(7, "bosslogin", "https://avatars.example/7");
            Jwt jwt = decoder.decode(tokens.issue(u));
            assertThat(jwt.getHeaders()).containsEntry("alg", "HS256");
            assertThat(jwt.getSubject()).isEqualTo("gh_bosslogin");
            assertThat(jwt.getClaimAsStringList("roles")).containsExactly("USER", "ADMIN");
            assertThat(jwt.getExpiresAt()).isAfter(jwt.getIssuedAt());
        }
    }

    @Nested
    class GithubLogin {
        @Test
        void loginStartsTheGithubAuthorizationFlow() throws Exception {
            mvc.perform(get("/oauth2/authorization/github"))
                    .andExpect(status().is3xxRedirection())
                    .andExpect(header().string("Location",
                            org.hamcrest.Matchers.startsWith("https://github.com/login/oauth/authorize")))
                    .andExpect(header().string("Location",
                            org.hamcrest.Matchers.containsString("redirect_uri=http://localhost/login/oauth2/code/github")));
        }

        @Test
        void successRedirectsToTheFrontendWithAToken() throws Exception {
            var principal = new DefaultOAuth2User(AuthorityUtils.createAuthorityList("OAUTH2_USER"),
                    Map.of("id", 583231, "login", "octocat", "avatar_url", "https://a/1"), "login");
            var auth = new OAuth2AuthenticationToken(principal, principal.getAuthorities(), "github");
            var req = new MockHttpServletRequest();
            req.getSession(true);
            var res = new MockHttpServletResponse();

            onSuccess.onAuthenticationSuccess(req, res, auth);

            String location = res.getRedirectedUrl();
            assertThat(location).startsWith("https://play.example.com/#token=");
            Jwt jwt = decoder.decode(location.substring(location.indexOf("=") + 1));
            assertThat(jwt.getSubject()).isEqualTo("gh_octocat");
            assertThat(jwt.getClaimAsStringList("roles")).isEqualTo(List.of("USER"));
            assertThat(req.getSession(false)).as("OAuth session is discarded").isNull();
        }
    }

    @Nested
    class Users {
        @Test
        void bootstrapAdminsArePromotedCaseInsensitively() {
            assertThat(users.recordLogin(1, "BOSSLOGIN", null).getRole()).isEqualTo(Role.ADMIN);
            assertThat(users.recordLogin(2, "someone", null).getRole()).isEqualTo(Role.USER);
        }

        @Test
        void repeatLoginsUpdateRatherThanDuplicate() {
            users.recordLogin(1, "octocat", null);
            users.recordLogin(1, "octocat-renamed", null);
            assertThat(repo.count()).isEqualTo(1);
            assertThat(repo.findByGithubId(1L).orElseThrow().getLogin()).isEqualTo("octocat-renamed");
        }

        @Test
        void aRenamedLoginFreesTheNameForItsNewOwner() {
            users.recordLogin(1, "octocat", null);
            users.recordLogin(2, "octocat", null);
            assertThat(repo.findByGithubId(2L).orElseThrow().getLogin()).isEqualTo("octocat");
            assertThat(repo.findByGithubId(1L).orElseThrow().getLogin()).isEqualTo("octocat~1");
        }

        @Test
        void theLastAdminCannotBeDemoted() {
            users.recordLogin(1, "bosslogin", null);
            try {
                users.setRole("bosslogin", Role.USER);
                throw new AssertionError("expected a conflict");
            } catch (ResponseStatusException e) {
                assertThat(e.getStatusCode().value()).isEqualTo(409);
            }
        }
    }
}
