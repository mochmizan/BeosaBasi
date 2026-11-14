import { pesanGalat } from "../api/errors";

export default function ErrorMessage({ error }: { error: unknown }): React.JSX.Element {
  return (
    <p className="bb-error" role="alert">
      {pesanGalat(error)}
    </p>
  );
}
