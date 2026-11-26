package com.algobattle.auth.user;

import java.util.List;

public enum Role {
    USER,
    ADMIN;

    /** Roles are hierarchical: an admin is also a user. */
    public List<String> grants() {
        return this == ADMIN ? List.of("USER", "ADMIN") : List.of("USER");
    }
}
