import type { ChatDataset } from "@/lib/api";

interface Props {
  options: ChatDataset[] | null; // null: still loading
  value: string;
  onChange: (id: string) => void;
  /** An existing chat stays bound to the dataset it was started with. */
  locked: boolean;
}

export function DatasetPicker({ options, value, onChange, locked }: Readonly<Props>) {
  const current = options?.find((d) => d.id === value);

  if (locked) {
    return (
      <p className="flex min-w-0 items-baseline gap-2 text-sm">
        <span className="text-ink-2">Dataset</span>
        <span className="truncate font-semibold text-ink">{current?.name ?? "Unknown dataset"}</span>
      </p>
    );
  }

  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <label htmlFor="dataset" className="shrink-0 text-sm text-ink-2">
        Dataset
      </label>
      <select
        id="dataset"
        value={value}
        disabled={!options || options.length === 0}
        onChange={(e) => onChange(e.target.value)}
        className="field w-auto min-w-[180px] max-w-[320px] py-1.5 font-semibold"
      >
        {!options && <option value="">Loading…</option>}
        {options && options.length === 0 && <option value="">No dataset with a key</option>}
        {options && options.length > 0 && !value && <option value="">Choose a dataset</option>}
        {options?.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
    </div>
  );
}
