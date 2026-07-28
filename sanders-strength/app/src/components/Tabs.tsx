export function Tabs<T extends string>({
  options,
  active,
  onChange,
}: {
  options: Array<{ value: T; label: string }>;
  active: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="tabs">
      {options.map((opt) => (
        <div
          key={opt.value}
          className={"tab" + (opt.value === active ? " active" : "")}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </div>
      ))}
    </div>
  );
}
