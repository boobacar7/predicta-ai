export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <p className="text-xs uppercase tracking-[0.2em] text-ai-strong">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-medium tracking-tight text-foreground md:text-4xl">
          {title}
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted md:text-base">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
