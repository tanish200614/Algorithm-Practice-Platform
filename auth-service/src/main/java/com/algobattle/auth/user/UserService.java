package com.algobattle.auth.user;

import java.time.Instant;
import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import com.algobattle.auth.config.AppProperties;

@Service
public class UserService {

    private final UserRepository users;
    private final AppProperties props;

    public UserService(UserRepository users, AppProperties props) {
        this.users = users;
        this.props = props;
    }

    /**
     * Create or refresh the user behind a successful GitHub login.
     *
     * <p>Logins listed in ADMIN_GITHUB_LOGINS are promoted on sign-in, which
     * is how the first admin exists. It only ever promotes, so to demote a
     * listed admin, also remove them from the list or their next login
     * promotes them again.
     */
    @Transactional
    public AppUser recordLogin(long githubId, String login, String avatarUrl) {
        AppUser user = users.findByGithubId(githubId).orElseGet(() -> {
            // A different account previously held this login (GitHub allows
            // renames). Free the name for the account that holds it now.
            users.findByLoginIgnoreCase(login).ifPresent(stale -> {
                stale.setLogin(stale.getLogin() + "~" + stale.getGithubId());
                users.saveAndFlush(stale);
            });
            return new AppUser(githubId, login);
        });
        user.setLogin(login);
        user.setAvatarUrl(avatarUrl);
        user.setLastLoginAt(Instant.now());
        if (props.isBootstrapAdmin(login)) {
            user.setRole(Role.ADMIN);
        }
        return users.save(user);
    }

    public List<AppUser> all() {
        return users.findAllByOrderByLastLoginAtDesc();
    }

    /**
     * Change a user's role. Refuses to demote the last admin, which would
     * leave nobody able to manage roles.
     */
    @Transactional
    public AppUser setRole(String login, Role role) {
        AppUser user = users.findByLoginIgnoreCase(login)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "No such user"));
        if (user.getRole() == Role.ADMIN && role != Role.ADMIN && users.countByRole(Role.ADMIN) <= 1) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Cannot demote the last admin");
        }
        user.setRole(role);
        return users.save(user);
    }
}
