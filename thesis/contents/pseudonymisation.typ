#import "helpers.typ": todo, todo-inline

= Pseudonymisation and key management <Pseudonymisation>

This chapter describes how detected values are replaced by tokens,
how the original values are protected, and who can decrypt them.

== Tokens

#todo[Format `[TYPE_id]`; id = first 12 hex characters of HMAC-SHA256 with a subkey derived from the
dataset key; deterministic within a dataset; collisions (48 bits) and the 16-hex fallback;
why the earlier unkeyed MD5 ids were unsafe (D-20); possessive endings outside the token (D-24).]

== Encryption of values

#todo[AES-CBC with a random IV for each value in the token map; one cipher-key rule for all
components; the bug with 32-byte keys and how it was found (D-22).]

== Keys

#todo[Random 32-byte dataset key; master key wraps dataset keys with AES-GCM in PostgreSQL;
key fingerprint instead of key prefix; no plaintext token map on disk; maps without expiry (D-22).]

== Decryption and access control

#todo[RBAC grants per user, dataset and entity type; streaming decryption with a buffer for tokens
split across chunks (D-21); audit log.]

== Security analysis

#todo[What an attacker learns from tokenised data (equality, frequencies @Naveed2015Inference);
what needs the key; what needs the token map; residual risk from detector misses.]
