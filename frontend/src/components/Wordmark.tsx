/** The name set as a token: the bar is the product. */
export function Wordmark({ size = "md" }: Readonly<{ size?: "md" | "lg" }>) {
  const lg = size === "lg";
  return (
    <span
      className={`inline-flex items-baseline font-bold tracking-[-0.01em] text-ink ${
        lg ? "text-xl" : "text-base"
      }`}
      aria-label="tux.ai"
    >
      <span
        aria-hidden
        className={`rounded-[2px] bg-toner font-type font-bold text-sheet ${
          lg ? "px-2 py-px" : "px-1.5"
        }`}
      >
        tux
      </span>
      <span aria-hidden className="ml-[1px]">
        .ai
      </span>
    </span>
  );
}
