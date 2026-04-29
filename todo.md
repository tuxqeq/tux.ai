# Production Readiness — Redis Token Map

## 1. Redis Persistence
Redis is in-memory by default. If it restarts, all token maps are lost and tokenized files become unrecoverable.

**Fix:** Enable AOF persistence in `redis.conf`:
```
appendonly yes
appendfsync everysec
```

---

## 2. Connection Pooling
A new Redis connection is created on every call. Under load this is wasteful and slow.

**Fix:** Create a shared `redis.ConnectionPool` at startup and reuse it across calls.

---

## 3. AES Key Management
The AES key used to encrypt token map values is never stored alongside the session. If the key is lost, the token map is useless.

**Fix:** Manage keys via a secrets manager:
- AWS Secrets Manager
- HashiCorp Vault
- At minimum, store a key reference (not the key itself) next to the session metadata.

---

## 4. Session ID Tracking
The session ID is the only handle to a token map. Currently it is printed to stdout and then lost — there is no index linking filenames to session IDs.

**Fix:** Write a secondary Redis key on every tokenization run:
```
filemap:{filename} -> session_id
```
This allows lookup of a token map by filename later.

---

## 5. No Default TTL
Token maps accumulate in Redis forever with no expiry or cleanup strategy.

**Fix:** Set a sensible default TTL (e.g. 30 days) or implement a scheduled cleanup job.

---

## 6. No Redis Authentication
The Redis URL has no password, leaving the token store open on the network.

**Fix:** Require auth in the Redis URL:
```
redis://:yourpassword@host:6379
```
And enforce TLS (`rediss://`) for connections over the network.

---

## 7. No Error Handling on Write
If the Redis write fails after the tokenized file has already been written, the output file exists but the recovery map is lost — with no rollback or alert.

**Fix:** Wrap the Redis write in a try/except. On failure:
1. Delete the already-written output file.
2. Raise an error so the caller knows the run failed cleanly.
