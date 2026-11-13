import { Fragment, useEffect, useState } from "react";
import { prefersReducedMotion } from "@/hooks/useMotion";

type Stage = "plain" | "scan" | "bar";

// A fictional record. The card number is the standard Visa test number.
const PARTS: (string | { text: string; label: string })[] = [
  { text: "Marta Kowalska", label: "PERSON" },
  " was born on ",
  { text: "14 March 1988", label: "DOB" },
  ". Her card ",
  { text: "4111 1111 1111 1111", label: "CREDIT_CARD" },
  " is linked to ",
  { text: "marta@example.com", label: "EMAIL" },
  ".",
];
const SPANS = PARTS.filter((p) => typeof p !== "string").length;

const SCAN_AT = 700; // first underline
const SCAN_STEP = 140;
const BAR_AT = SCAN_AT + SCAN_STEP * SPANS + 380; // first bar
const BAR_STEP = 170;
const CAPTION_AT = BAR_AT + BAR_STEP * SPANS + 450;

/**
 * The login page's one orchestrated moment: a record is read, its personal data is found,
 * and each value is blacked out into a typed token. It runs once; "Replay" runs it again.
 */
export function RedactionDemo() {
  const [run, setRun] = useState(0);
  const [stages, setStages] = useState<Stage[]>(() =>
    Array(SPANS).fill(prefersReducedMotion() ? "bar" : "plain"),
  );
  const [captionShown, setCaptionShown] = useState(prefersReducedMotion());

  useEffect(() => {
    if (prefersReducedMotion()) {
      setStages(Array(SPANS).fill("bar"));
      setCaptionShown(true);
      return;
    }
    setStages(Array(SPANS).fill("plain"));
    if (run === 0) setCaptionShown(false);
    const timers: number[] = [];
    const set = (i: number, s: Stage) =>
      setStages((prev) => prev.map((v, j) => (j === i ? s : v)));
    for (let i = 0; i < SPANS; i++) {
      timers.push(window.setTimeout(() => set(i, "scan"), SCAN_AT + i * SCAN_STEP));
      timers.push(window.setTimeout(() => set(i, "bar"), BAR_AT + i * BAR_STEP));
    }
    timers.push(window.setTimeout(() => setCaptionShown(true), CAPTION_AT));
    return () => timers.forEach(clearTimeout);
  }, [run]);

  let k = -1;
  return (
    <figure>
      <blockquote
        className="max-w-[23ch] text-xl font-medium leading-[1.5] tracking-[-0.012em] text-ink sm:text-2xl lg:text-3xl lg:leading-[1.42] xl:text-[46px] xl:leading-[1.38]"
        aria-label="Example record: Marta Kowalska was born on 14 March 1988. Her card 4111 1111 1111 1111 is linked to marta@example.com. After tokenization each of these values is a hidden token."
      >
        <span aria-hidden>
          {PARTS.map((p, i) => {
            if (typeof p === "string") return <Fragment key={i}>{p}</Fragment>;
            k += 1;
            return (
              <span key={i} className="demo-pii" data-stage={stages[k]}>
                {p.text}
                <span className="demo-label">{p.label}</span>
              </span>
            );
          })}
        </span>
      </blockquote>

      <figcaption
        className={`mt-8 flex max-w-[46ch] flex-wrap items-baseline gap-x-4 gap-y-2 text-base text-ink-2 transition-[opacity,transform] duration-500 ease-out ${
          captionShown ? "opacity-100" : "translate-y-1 opacity-0"
        }`}
      >
        <span>
          This is what the model reads. Your role decides which of these values you see again.
        </span>
        <button
          type="button"
          onClick={() => setRun((r) => r + 1)}
          className="btn-quiet -ml-2 text-sm underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
          tabIndex={captionShown ? 0 : -1}
        >
          Replay
        </button>
      </figcaption>
    </figure>
  );
}
