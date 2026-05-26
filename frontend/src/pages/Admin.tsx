import { useEffect, useState } from "react";
import { admin, type AdminUser, type Dataset, type RbacGrant } from "@/lib/api";

const ENTITY_TYPES = [
  "PERSON", "EMAIL", "PHONE", "SSN", "CREDIT_CARD", "DOB", "LOCATION",
  "ORG", "API_KEY", "AWS_KEY", "MRN", "BANK", "IP", "USERNAME", "VIN", "*",
];

const inputCls =
  "w-full rounded-xl border border-white/8 bg-surface px-3 py-2.5 text-sm text-white placeholder-white/20 outline-none transition-all focus:border-accent/30 focus:ring-1 focus:ring-accent/10";

const btnCls =
  "rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-black/75 transition-all hover:bg-accent-hover disabled:opacity-40";

function SectionLabel({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-white/30">
      {children}
    </h3>
  );
}

export function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [grants, setGrants] = useState<RbacGrant[]>([]);
  const [tab, setTab] = useState<"users" | "datasets" | "rbac">("users");

  const [newEmail, setNewEmail] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newRole, setNewRole] = useState("viewer");

  const [dsName, setDsName] = useState("");
  const [dsDesc, setDsDesc] = useState("");

  const [keyDsId, setKeyDsId] = useState("");
  const [keyHex, setKeyHex] = useState("");

  const [rdbDsId, setRdbDsId] = useState("");
  const [rdbFile, setRdbFile] = useState<File | null>(null);
  const [rdbLoading, setRdbLoading] = useState(false);

  const [modelDsId, setModelDsId] = useState("");
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [modelLoading, setModelLoading] = useState(false);

  const [grantUserId, setGrantUserId] = useState("");
  const [grantDsId, setGrantDsId] = useState("");
  const [grantEntity, setGrantEntity] = useState("EMAIL");

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function flash(msg: string, isError = false) {
    if (isError) { setError(msg); setSuccess(null); }
    else { setSuccess(msg); setError(null); }
    setTimeout(() => { setError(null); setSuccess(null); }, 4000);
  }

  useEffect(() => {
    Promise.all([admin.listUsers(), admin.listDatasets(), admin.listGrants()])
      .then(([u, d, g]) => { setUsers(u); setDatasets(d); setGrants(g); })
      .catch((e) => flash((e as Error).message, true));
  }, []);

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const u = await admin.createUser(newEmail, newPass, newRole);
      setUsers((prev) => [...prev, u]);
      setNewEmail(""); setNewPass("");
      flash(`User ${u.email} created`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const deleteUser = async (id: string) => {
    try {
      await admin.deleteUser(id);
      setUsers((prev) => prev.filter((u) => u.id !== id));
      flash("User deleted");
    } catch (e) { flash((e as Error).message, true); }
  };

  const createDataset = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const d = await admin.createDataset(dsName, dsDesc || undefined);
      setDatasets((prev) => [...prev, d]);
      setDsName(""); setDsDesc("");
      flash(`Dataset "${d.name}" created`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const uploadKey = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { key_ref } = await admin.uploadKey(keyDsId, keyHex);
      setDatasets((prev) => prev.map((d) => d.id === keyDsId ? { ...d, has_key: true } : d));
      setKeyHex("");
      flash(`Key uploaded (ref: ${key_ref})`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const importRdb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rdbFile) return;
    setRdbLoading(true);
    try {
      const { imported_tokens } = await admin.importRdb(rdbDsId, rdbFile);
      setDatasets((prev) =>
        prev.map((d) => d.id === rdbDsId ? { ...d, rdb_imported: true } : d)
      );
      setRdbFile(null);
      flash(`Imported ${imported_tokens} tokens from dump.rdb`);
    } catch (e) { flash((e as Error).message, true); }
    finally { setRdbLoading(false); }
  };

  const uploadModel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelFile) return;
    setModelLoading(true);
    try {
      const { model_name } = await admin.uploadModel(modelDsId, modelFile);
      setDatasets((prev) =>
        prev.map((d) => d.id === modelDsId ? { ...d, model_name } : d)
      );
      setModelFile(null);
      flash(`Model registered as "${model_name}"`);
    } catch (e) { flash((e as Error).message, true); }
    finally { setModelLoading(false); }
  };

  const addGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { id } = await admin.addGrant(grantUserId, grantDsId, grantEntity);
      const user = users.find((u) => u.id === grantUserId);
      const ds = datasets.find((d) => d.id === grantDsId);
      setGrants((prev) => [...prev, {
        id, user_id: grantUserId, dataset_id: grantDsId, entity_type: grantEntity,
      }]);
      flash(`Granted ${grantEntity} on "${ds?.name}" to ${user?.email}`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const removeGrant = async (id: string) => {
    try {
      await admin.removeGrant(id);
      setGrants((prev) => prev.filter((g) => g.id !== id));
      flash("Grant removed");
    } catch (e) { flash((e as Error).message, true); }
  };

  const tabCls = (t: string) =>
    `px-5 py-3 text-sm font-medium transition-colors ${
      tab === t
        ? "text-white border-b-2 border-accent"
        : "text-white/35 hover:text-white/60"
    }`;

  return (
    <div className="min-h-screen bg-surface px-4 py-8">
      <div className="mx-auto max-w-4xl">
        {/* Page header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Admin</h1>
            <p className="mt-0.5 text-xs text-white/30">Manage users, datasets, and access grants</p>
          </div>
          <a
            href="/"
            className="rounded-lg px-3 py-1.5 text-sm text-white/35 transition-colors hover:bg-white/6 hover:text-white/60"
          >
            ← Back to chat
          </a>
        </div>

        {/* Flash messages */}
        {error && (
          <div className="mb-4 rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-300">
            {success}
          </div>
        )}

        {/* Main card */}
        <div className="rounded-2xl border border-white/8 bg-surface-raised">
          {/* Tabs */}
          <div className="flex border-b border-white/8">
            <button className={tabCls("users")} onClick={() => setTab("users")}>Users</button>
            <button className={tabCls("datasets")} onClick={() => setTab("datasets")}>Datasets &amp; Keys</button>
            <button className={tabCls("rbac")} onClick={() => setTab("rbac")}>RBAC Grants</button>
          </div>

          <div className="p-6">
            {/* ── Users ── */}
            {tab === "users" && (
              <div className="space-y-6">
                <SectionLabel>Add user</SectionLabel>
                <form onSubmit={createUser} className="grid grid-cols-4 gap-2">
                  <input className={inputCls} placeholder="Email" type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
                  <input className={inputCls} placeholder="Password" type="password" required value={newPass} onChange={(e) => setNewPass(e.target.value)} />
                  <select className={inputCls} value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                    <option value="viewer">Viewer</option>
                    <option value="analyst">Analyst</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button type="submit" className={btnCls}>Add user</button>
                </form>

                <SectionLabel>All users</SectionLabel>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/6 text-left text-xs text-white/30">
                      <th className="pb-2 font-medium">Email</th>
                      <th className="pb-2 font-medium">Role</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td className="py-3 text-white/80">{u.email}</td>
                        <td className="py-3 text-white/40">{u.role}</td>
                        <td className="py-3">
                          <span className={`text-xs font-medium ${u.is_active ? "text-emerald-400" : "text-red-400"}`}>
                            {u.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="py-3 text-right">
                          <button
                            onClick={() => deleteUser(u.id)}
                            className="text-xs text-white/20 transition-colors hover:text-red-400"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── Datasets ── */}
            {tab === "datasets" && (
              <div className="space-y-8">
                <div>
                  <SectionLabel>Create dataset</SectionLabel>
                  <form onSubmit={createDataset} className="grid grid-cols-3 gap-2">
                    <input className={inputCls} placeholder="Dataset name" required value={dsName} onChange={(e) => setDsName(e.target.value)} />
                    <input className={inputCls} placeholder="Description (optional)" value={dsDesc} onChange={(e) => setDsDesc(e.target.value)} />
                    <button type="submit" className={btnCls}>Create</button>
                  </form>
                </div>

                <div>
                  <SectionLabel>Upload AES Key</SectionLabel>
                  <form onSubmit={uploadKey} className="grid grid-cols-3 gap-2">
                    <select className={inputCls} value={keyDsId} onChange={(e) => setKeyDsId(e.target.value)} required>
                      <option value="">Select dataset…</option>
                      {datasets.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}{d.has_key ? " (has key)" : ""}</option>
                      ))}
                    </select>
                    <input className={inputCls} placeholder="AES key hex (32/48/64 chars)" required value={keyHex} onChange={(e) => setKeyHex(e.target.value)} />
                    <button type="submit" className={btnCls}>Upload key</button>
                  </form>
                  <p className="mt-1.5 text-xs text-white/20">
                    Encrypted with the server master key before storage. Never logged or sent to clients.
                  </p>
                </div>

                <div>
                  <SectionLabel>Import Token Map (dump.rdb)</SectionLabel>
                  <form onSubmit={importRdb} className="grid grid-cols-3 gap-2">
                    <select className={inputCls} value={rdbDsId} onChange={(e) => setRdbDsId(e.target.value)} required>
                      <option value="">Select dataset…</option>
                      {datasets.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}{d.rdb_imported ? " (imported)" : ""}</option>
                      ))}
                    </select>
                    <input type="file" accept=".rdb" required className={inputCls} onChange={(e) => setRdbFile(e.target.files?.[0] ?? null)} />
                    <button type="submit" disabled={rdbLoading} className={btnCls}>
                      {rdbLoading ? "Importing…" : "Import RDB"}
                    </button>
                  </form>
                  <p className="mt-1.5 text-xs text-white/20">
                    Tokens imported into Redis under ds:&#123;id&#125;:tokenmap for chat decryption.
                  </p>
                </div>

                <div>
                  <SectionLabel>Upload Chat Model (.gguf)</SectionLabel>
                  <form onSubmit={uploadModel} className="grid grid-cols-3 gap-2">
                    <select className={inputCls} value={modelDsId} onChange={(e) => setModelDsId(e.target.value)} required>
                      <option value="">Select dataset…</option>
                      {datasets.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}{d.model_name ? ` (${d.model_name})` : ""}</option>
                      ))}
                    </select>
                    <input type="file" accept=".gguf" required className={inputCls} onChange={(e) => setModelFile(e.target.files?.[0] ?? null)} />
                    <button type="submit" disabled={modelLoading} className={btnCls}>
                      {modelLoading ? "Registering…" : "Upload model"}
                    </button>
                  </form>
                  <p className="mt-1.5 text-xs text-white/20">
                    GGUF saved to disk and registered with Ollama. Large models may take several minutes.
                  </p>
                </div>

                <div>
                  <SectionLabel>All datasets</SectionLabel>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/6 text-left text-xs text-white/30">
                        <th className="pb-2 font-medium">Name</th>
                        <th className="pb-2 font-medium">Description</th>
                        <th className="pb-2 font-medium">AES Key</th>
                        <th className="pb-2 font-medium">RDB</th>
                        <th className="pb-2 font-medium">Model</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {datasets.map((d) => (
                        <tr key={d.id}>
                          <td className="py-3 text-white/80">{d.name}</td>
                          <td className="py-3 text-white/35">{d.description ?? "—"}</td>
                          <td className="py-3">
                            <span className={`text-xs font-medium ${d.has_key ? "text-emerald-400" : "text-amber-400"}`}>
                              {d.has_key ? "Configured" : "No key"}
                            </span>
                          </td>
                          <td className="py-3">
                            <span className={`text-xs ${d.rdb_imported ? "text-emerald-400" : "text-white/20"}`}>
                              {d.rdb_imported ? "Imported" : "—"}
                            </span>
                          </td>
                          <td className="py-3">
                            <span className="font-mono text-xs text-white/40">{d.model_name ?? "—"}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── RBAC ── */}
            {tab === "rbac" && (
              <div className="space-y-6">
                <SectionLabel>Add grant</SectionLabel>
                <form onSubmit={addGrant} className="grid grid-cols-4 gap-2">
                  <select className={inputCls} value={grantUserId} onChange={(e) => setGrantUserId(e.target.value)} required>
                    <option value="">Select user…</option>
                    {users.map((u) => <option key={u.id} value={u.id}>{u.email}</option>)}
                  </select>
                  <select className={inputCls} value={grantDsId} onChange={(e) => setGrantDsId(e.target.value)} required>
                    <option value="">Select dataset…</option>
                    {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select>
                  <select className={inputCls} value={grantEntity} onChange={(e) => setGrantEntity(e.target.value)}>
                    {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t === "*" ? "ALL TYPES (*)" : t}</option>)}
                  </select>
                  <button type="submit" className={btnCls}>Add grant</button>
                </form>

                <SectionLabel>Active grants</SectionLabel>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/6 text-left text-xs text-white/30">
                      <th className="pb-2 font-medium">User</th>
                      <th className="pb-2 font-medium">Dataset</th>
                      <th className="pb-2 font-medium">Entity type</th>
                      <th className="pb-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {grants.map((g) => {
                      const user = users.find((u) => u.id === g.user_id);
                      const ds = datasets.find((d) => d.id === g.dataset_id);
                      return (
                        <tr key={g.id}>
                          <td className="py-3 text-white/80">{user?.email ?? g.user_id.slice(0, 8)}</td>
                          <td className="py-3 text-white/40">{ds?.name ?? "—"}</td>
                          <td className="py-3">
                            <span className="font-mono text-xs text-accent">{g.entity_type}</span>
                          </td>
                          <td className="py-3 text-right">
                            <button
                              onClick={() => removeGrant(g.id)}
                              className="text-xs text-white/20 transition-colors hover:text-red-400"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
