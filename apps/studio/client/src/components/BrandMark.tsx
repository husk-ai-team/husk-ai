// Studio-side brand mark — visually identical to the marketing site's BrandName
// + logo combo. Kept here so the studio doesn't depend on marketing source.

interface BrandMarkProps {
  className?: string;
}

export function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div className="size-8 rounded-md bg-accent grid place-items-center">
        <span className="font-bold text-[13px] text-white leading-none">H</span>
      </div>
      <div className="text-sm font-bold tracking-[-0.02em]">
        <span className="text-foreground">HUSK</span>{" "}
        <span className="text-accent">AI</span>
      </div>
    </div>
  );
}
