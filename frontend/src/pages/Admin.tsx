import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { admin, type AdminUser, type Dataset, type RbacGrant } from "@/lib/api";
import { Redaction } from "@/components/Redaction";
import { Toast, type ToastMessage } from "@/components/Toast";
import { Wordmark } from "@/components/Wordmark";
import { useSlidingMarker } from "@/hooks/useMotion";

const ENTITY_TYPES = [
  "PERSON", "EMAIL", "PHONE", "SSN", "CREDIT_CARD", "DOB", "LOCATION",
  "ORG", "API_KEY", "AWS_KEY", "MRN", "BANK", "IP", "USERNAME", "VIN", "DL", "PII", "*",
];

type Tab = "users" | "datasets" | "access";

const TABS: { key: Tab; label: string }[] = [
  { key: "users", label: "Users" },
  { key: "datasets", label: "Datasets" },
  { key: "access", label: "Access" },
];

// ── small building blocks ──────────────────────────────────────────────────────

function Section({
  title,
  hint,
  children,
}: Readonly<{ title: string; hint?: React.ReactNode; children: React.ReactNode }>) {
  return (
    <section className="border-t border-rule py-8 first:border-t-0 first:pt-7">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {hint && <p className="mt-1 max-w-[70ch] text-sm text-ink-2">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, htmlFor, children }: Readonly<{ label: string; htmlFor: string; children: React.ReactNode }>) {
  return (
    <div className="min-w-0">
      <label htmlFor={htmlFor} className="field-label">
        {label}
      </label>
      {children}
    </div>
  );
}

function FilePick({
  id,
  accept,
  file,
  onPick,
}: Readonly<{ id: string; accept: string; file: File | null; onPick: (f: File | null) => void }>) {
  return (
    <label
      htmlFor={id}
      className="field flex cursor-pointer items-center gap-2 focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgb(29_32_38/0.1)]"
    >
      <input
        id={id}
        type="file"
        accept={accept}
        required
        className="sr-only"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
      <span className="shrink-0 rounded border border-rule-strong px-1.5 text-xs font-medium text-ink">
        Choose
      </span>
      <span className={`truncate ${file ? "text-ink" : "text-ink-3"}`}>{file ? file.name : `No ${accept} file`}</span>
    </label>
  );
}

function Status({ ok, yes, no, warn = false }: Readonly<{ ok: boolean; yes: string; no: string; warn?: boolean }>) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${ok ? "text-ink" : warn ? "text-alert" : "text-ink-3"}`}>
      <span
        aria-hidden
        className={`h-2 w-2 rounded-[1px] ${ok ? "bg-ink" : warn ? "border border-alert" : "border border-rule-strong"}`}
      />
      {ok ? yes : no}
    </span>
  );
}

const th = "pb-2 pr-4 text-left text-xs font-medium text-ink-2";
const td = "py-3 pr-4 align-middle";

// ── page ──────────────────────────────────────────────────────────────────────

export function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [grants, setGrants] = useState<RbacGrant[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState<Tab>("users");

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

  const [toast, setToast] = useState<ToastMessage | null>(null);
  const toastId = useRef(0);
  // rows created or changed in this visit get a short highlight
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [leaving, setLeaving] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState<string | null>(null);

  function flash(text: string, isError = false) {
    toastId.current += 1;
    setToast({ id: toastId.current, text, tone: isError ? "error" : "ok" });
  }
  const markFresh = (id: string) => {
    setFresh((p) => new Set(p).add(id));
    window.setTimeout(() => setFresh((p) => { const n = new Set(p); n.delete(id); return n; }), 1700);
  };
  const fadeOut = (id: string, then: () => void) => {
    setLeaving((p) => new Set(p).add(id));
    window.setTimeout(() => {
      then();
      setLeaving((p) => { const n = new Set(p); n.delete(id); return n; });
    }, 220);
  };

  useEffect(() => {
    Promise.all([admin.listUsers(), admin.listDatasets(), admin.listGrants()])
      .then(([u, d, g]) => { setUsers(u); setDatasets(d); setGrants(g); })
      .catch((e) => flash((e as Error).message, true))
      .finally(() => setLoaded(true));
  }, []);

  // a delete asks once more; the question goes away after 3 s
  useEffect(() => {
    if (!confirming) return;
    const t = window.setTimeout(() => setConfirming(null), 3000);
    return () => clearTimeout(t);
  }, [confirming]);

  const { containerRef: tabsRef, markerStyle } = useSlidingMarker<HTMLDivElement>(tab, "x", [
    loaded,
    users.length,
    datasets.length,
    grants.length,
  ]);

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const u = await admin.createUser(newEmail, newPass, newRole);
      setUsers((prev) => [...prev, u]);
      markFresh(u.id);
      setNewEmail(""); setNewPass("");
      flash(`Added ${u.email}`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const deleteUser = async (id: string) => {
    if (confirming !== id) { setConfirming(id); return; }
    setConfirming(null);
    try {
      await admin.deleteUser(id);
      fadeOut(id, () => setUsers((prev) => prev.filter((u) => u.id !== id)));
      flash("User deleted");
    } catch (e) { flash((e as Error).message, true); }
  };

  const createDataset = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const d = await admin.createDataset(dsName, dsDesc || undefined);
      setDatasets((prev) => [...prev, d]);
      markFresh(d.id);
      setDsName(""); setDsDesc("");
      flash(`Created dataset ${d.name}`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const uploadKey = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { key_ref } = await admin.uploadKey(keyDsId, keyHex);
      setDatasets((prev) => prev.map((d) => d.id === keyDsId ? { ...d, has_key: true } : d));
      markFresh(keyDsId);
      setKeyHex("");
      flash(`Key uploaded. Reference: ${key_ref}`);
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
      markFresh(rdbDsId);
      setRdbFile(null);
      flash(`Imported ${imported_tokens.toLocaleString()} tokens`);
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
      markFresh(modelDsId);
      setModelFile(null);
      flash(`Model registered as ${model_name}`);
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
      markFresh(id);
      flash(`${user?.email} can now see ${grantEntity === "*" ? "all values" : grantEntity} in ${ds?.name}`);
    } catch (e) { flash((e as Error).message, true); }
  };

  const removeGrant = async (id: string) => {
    try {
      await admin.removeGrant(id);
      fadeOut(id, () => setGrants((prev) => prev.filter((g) => g.id !== id)));
      flash("Access removed");
    } catch (e) { flash((e as Error).message, true); }
  };

  const rowCls = (id: string) =>
    `border-t border-rule transition-opacity duration-200 ${fresh.has(id) ? "row-new" : ""} ${
      leaving.has(id) ? "opacity-0" : ""
    }`;

  const datasetOptions = (suffix: (d: Dataset) => string) =>
    datasets.map((d) => (
      <option key={d.id} value={d.id}>{d.name}{suffix(d)}</option>
    ));

  return (
    <div className="min-h-dvh bg-paper">
      <header className="border-b border-rule bg-paper">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-baseline gap-3">
            <Wordmark />
            <span className="text-sm text-ink-2">Admin</span>
          </div>
          <Link to="/" className="btn-quiet">Back to chat</Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6">
        <h1 className="text-2xl font-semibold tracking-[-0.015em]">Users, datasets and access</h1>
        <p className="mt-1 max-w-[64ch] text-base text-ink-2">
          A user sees a value in an answer only when a rule below allows it for that dataset. Admins
          see every value.
        </p>

        <div ref={tabsRef} role="tablist" aria-label="Admin sections" className="relative mt-8 flex gap-1 border-b border-rule">
          {TABS.map((t) => (
            <button
              key={t.key}
              data-key={t.key}
              role="tab"
              id={`tab-${t.key}`}
              aria-selected={tab === t.key}
              aria-controls={`panel-${t.key}`}
              onClick={() => setTab(t.key)}
              className={`relative px-3 pb-3 pt-1 text-sm font-semibold transition-colors duration-150 ${
                tab === t.key ? "text-ink" : "text-ink-2 hover:text-ink"
              }`}
            >
              {t.label}
              <span className="ml-1.5 font-normal text-ink-3">
                {loaded ? (t.key === "users" ? users.length : t.key === "datasets" ? datasets.length : grants.length) : ""}
              </span>
            </button>
          ))}
          <span
            aria-hidden
            style={markerStyle}
            className="absolute -bottom-px left-0 h-[3px] bg-ink transition-[transform,width] duration-300 ease-out"
          />
        </div>

        <div
          key={tab}
          role="tabpanel"
          id={`panel-${tab}`}
          aria-labelledby={`tab-${tab}`}
          className="fade-in rounded-b-lg border border-t-0 border-rule bg-sheet px-5 sm:px-7"
        >
          {/* ── Users ── */}
          {tab === "users" && (
            <>
              <Section title="Add a user" hint="The user signs in with this email and password.">
                <form onSubmit={createUser} className="grid gap-3 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.8fr)_10.5rem] sm:items-end">
                  <Field label="Email" htmlFor="nu-email">
                    <input id="nu-email" className="field" type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
                  </Field>
                  <Field label="Password" htmlFor="nu-pass">
                    <input id="nu-pass" className="field" type="password" required value={newPass} onChange={(e) => setNewPass(e.target.value)} />
                  </Field>
                  <Field label="Role" htmlFor="nu-role">
                    <select id="nu-role" className="field" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                      <option value="viewer">Viewer</option>
                      <option value="analyst">Analyst</option>
                      <option value="admin">Admin</option>
                    </select>
                  </Field>
                  <button type="submit" className="btn-ink">Add user</button>
                </form>
              </Section>

              <Section title="All users">
                <Table empty={loaded && users.length === 0 ? "No users yet." : null}>
                  <thead>
                    <tr>
                      <th className={th}>Email</th>
                      <th className={th}>Role</th>
                      <th className={th}>Status</th>
                      <th className={th}><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className={rowCls(u.id)}>
                        <td className={`${td} text-ink`}>{u.email}</td>
                        <td className={`${td} capitalize text-ink-2`}>{u.role}</td>
                        <td className={td}><Status ok={u.is_active} yes="Active" no="Inactive" /></td>
                        <td className={`${td} pr-0 text-right`}>
                          <button
                            onClick={() => deleteUser(u.id)}
                            className={`btn-quiet text-xs transition-[background-color,color,width] ${
                              confirming === u.id ? "bg-alert-soft text-alert hover:bg-alert-soft hover:text-alert" : "hover:text-alert"
                            }`}
                          >
                            {confirming === u.id ? "Click again to delete" : "Delete"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Section>
            </>
          )}

          {/* ── Datasets ── */}
          {tab === "datasets" && (
            <>
              <Section title="Datasets">
                <Table empty={loaded && datasets.length === 0 ? "No datasets yet. Create one below." : null}>
                  <thead>
                    <tr>
                      <th className={th}>Name</th>
                      <th className={th}>Key</th>
                      <th className={th}>Token map</th>
                      <th className={th}>Chat model</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datasets.map((d) => (
                      <tr key={d.id} className={rowCls(d.id)}>
                        <td className={td}>
                          <span className="block text-ink">{d.name}</span>
                          {d.description && <span className="block text-xs text-ink-2">{d.description}</span>}
                        </td>
                        <td className={td}><Status ok={d.has_key} yes="Uploaded" no="Missing" warn /></td>
                        <td className={td}><Status ok={d.rdb_imported} yes="Imported" no="Not imported" /></td>
                        <td className={td}>
                          {d.model_name
                            ? <span className="font-type text-sm text-ink">{d.model_name}</span>
                            : <span className="text-xs text-ink-3">Default</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <p className="mt-3 text-xs text-ink-2">A dataset needs a key before anyone can chat with it.</p>
              </Section>

              <Section title="Create a dataset">
                <form onSubmit={createDataset} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_10.5rem] sm:items-end">
                  <Field label="Name" htmlFor="ds-name">
                    <input id="ds-name" className="field" required value={dsName} onChange={(e) => setDsName(e.target.value)} />
                  </Field>
                  <Field label="Description (optional)" htmlFor="ds-desc">
                    <input id="ds-desc" className="field" value={dsDesc} onChange={(e) => setDsDesc(e.target.value)} />
                  </Field>
                  <button type="submit" className="btn-ink">Create dataset</button>
                </form>
              </Section>

              <Section
                title="Upload the AES key"
                hint="The server wraps the key with its master key before it stores it. The key is never logged and never sent to a browser."
              >
                <form onSubmit={uploadKey} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_10.5rem] sm:items-end">
                  <Field label="Dataset" htmlFor="key-ds">
                    <select id="key-ds" className="field" value={keyDsId} onChange={(e) => setKeyDsId(e.target.value)} required>
                      <option value="">Choose a dataset</option>
                      {datasetOptions((d) => (d.has_key ? " (has a key)" : ""))}
                    </select>
                  </Field>
                  <Field label="Key in hex: 32, 48 or 64 characters" htmlFor="key-hex">
                    <input id="key-hex" className="field font-type" required autoComplete="off" spellCheck={false} value={keyHex} onChange={(e) => setKeyHex(e.target.value)} />
                  </Field>
                  <button type="submit" className="btn-ink">Upload key</button>
                </form>
              </Section>

              <Section
                title="Import the token map"
                hint={<>Upload the <span className="font-type">dump.rdb</span> made when the dataset was tokenized. Chat uses it to turn tokens back into values.</>}
              >
                <form onSubmit={importRdb} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_10.5rem] sm:items-end">
                  <Field label="Dataset" htmlFor="rdb-ds">
                    <select id="rdb-ds" className="field" value={rdbDsId} onChange={(e) => setRdbDsId(e.target.value)} required>
                      <option value="">Choose a dataset</option>
                      {datasetOptions((d) => (d.rdb_imported ? " (imported)" : ""))}
                    </select>
                  </Field>
                  <Field label="File" htmlFor="rdb-file">
                    <FilePick id="rdb-file" accept=".rdb" file={rdbFile} onPick={setRdbFile} />
                  </Field>
                  <button type="submit" disabled={rdbLoading} className="btn-ink">
                    {rdbLoading && <Spinner />}
                    {rdbLoading ? "Importing…" : "Import token map"}
                  </button>
                </form>
              </Section>

              <Section
                title="Upload a chat model"
                hint="The .gguf file is saved and registered with Ollama. A large model can take several minutes."
              >
                <form onSubmit={uploadModel} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_10.5rem] sm:items-end">
                  <Field label="Dataset" htmlFor="model-ds">
                    <select id="model-ds" className="field" value={modelDsId} onChange={(e) => setModelDsId(e.target.value)} required>
                      <option value="">Choose a dataset</option>
                      {datasetOptions((d) => (d.model_name ? ` (${d.model_name})` : ""))}
                    </select>
                  </Field>
                  <Field label="File" htmlFor="model-file">
                    <FilePick id="model-file" accept=".gguf" file={modelFile} onPick={setModelFile} />
                  </Field>
                  <button type="submit" disabled={modelLoading} className="btn-ink">
                    {modelLoading && <Spinner />}
                    {modelLoading ? "Uploading…" : "Upload model"}
                  </button>
                </form>
              </Section>
            </>
          )}

          {/* ── Access ── */}
          {tab === "access" && (
            <>
              <Section
                title="Let a user see a type of value"
                hint="Without a rule, the user sees a bar instead of the value. Choose “All types” to show every value in that dataset."
              >
                <form onSubmit={addGrant} className="grid gap-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_10.5rem] sm:items-end">
                  <Field label="User" htmlFor="g-user">
                    <select id="g-user" className="field" value={grantUserId} onChange={(e) => setGrantUserId(e.target.value)} required>
                      <option value="">Choose a user</option>
                      {users.map((u) => <option key={u.id} value={u.id}>{u.email}</option>)}
                    </select>
                  </Field>
                  <Field label="Dataset" htmlFor="g-ds">
                    <select id="g-ds" className="field" value={grantDsId} onChange={(e) => setGrantDsId(e.target.value)} required>
                      <option value="">Choose a dataset</option>
                      {datasetOptions(() => "")}
                    </select>
                  </Field>
                  <Field label="Type of value" htmlFor="g-type">
                    <select id="g-type" className="field" value={grantEntity} onChange={(e) => setGrantEntity(e.target.value)}>
                      {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t === "*" ? "All types" : t}</option>)}
                    </select>
                  </Field>
                  <button type="submit" className="btn-ink">Add rule</button>
                </form>
              </Section>

              <Section title="Rules">
                <Table empty={loaded && grants.length === 0 ? "No rules yet. Users other than admins see bars only." : null}>
                  <thead>
                    <tr>
                      <th className={th}>User</th>
                      <th className={th}>Dataset</th>
                      <th className={th}>Can see</th>
                      <th className={th}><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {grants.map((g) => {
                      const user = users.find((u) => u.id === g.user_id);
                      const ds = datasets.find((d) => d.id === g.dataset_id);
                      return (
                        <tr key={g.id} className={rowCls(g.id)}>
                          <td className={`${td} text-ink`}>{user?.email ?? g.user_id.slice(0, 8)}</td>
                          <td className={`${td} text-ink-2`}>{ds?.name ?? "Deleted dataset"}</td>
                          <td className={td}>
                            {g.entity_type === "*"
                              ? <span className="text-sm font-medium text-ink">All types</span>
                              : <Redaction label={g.entity_type} interactive={false} />}
                          </td>
                          <td className={`${td} pr-0 text-right`}>
                            <button onClick={() => removeGrant(g.id)} className="btn-quiet text-xs hover:text-alert">
                              Remove
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
              </Section>
            </>
          )}
        </div>
      </main>

      <Toast msg={toast} onDone={(id) => setToast((t) => (t?.id === id ? null : t))} />
    </div>
  );
}

function Table({ empty, children }: Readonly<{ empty: string | null; children: React.ReactNode }>) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full min-w-[520px] text-sm">{children}</table>
      {empty && <p className="border-t border-rule py-6 text-sm text-ink-2">{empty}</p>}
    </div>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden
      className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-sheet/30 border-t-sheet"
    />
  );
}
