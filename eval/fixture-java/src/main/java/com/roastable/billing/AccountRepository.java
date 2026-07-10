package com.roastable.billing;

import org.springframework.data.jpa.repository.JpaRepository;

/** Spring Data access to the accounts table. */
public interface AccountRepository extends JpaRepository<Account, String> {
}
