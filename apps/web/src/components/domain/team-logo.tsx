import { cn } from "@/lib/cn";

const palettes = [
  "from-[#2a2458] to-[#7c6cf6]",
  "from-[#16324a] to-[#4ea3d9]",
  "from-[#17392d] to-[#3ddc97]",
  "from-[#3a2614] to-[#f0a14a]",
  "from-[#3a1d24] to-[#e36b5b]",
];

function paletteFor(name: string) {
  const sum = Array.from(name).reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return palettes[sum % palettes.length];
}

export function TeamLogo({
  name,
  abbreviation,
  size = "md",
}: {
  name: string;
  abbreviation: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizes = {
    sm: "size-8 text-[10px]",
    md: "size-10 text-xs",
    lg: "size-14 text-sm",
  };

  return (
    <div
      aria-hidden="true"
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-linear-to-br font-semibold text-white",
        paletteFor(name),
        sizes[size],
      )}
    >
      {abbreviation.slice(0, 3)}
    </div>
  );
}
