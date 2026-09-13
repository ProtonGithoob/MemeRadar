import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  note,
  id
}: {
  eyebrow: string;
  title: string;
  note?: ReactNode;
  id?: string;
}) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={id}>{title}</h2>
      </div>
      {note ? <small>{note}</small> : null}
    </div>
  );
}
