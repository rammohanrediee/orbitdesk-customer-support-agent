import { useState } from "react";
import { getEvidence } from "../api.js";

export default function EvidenceSource({ source }) {
  const [document, setDocument] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (document) return;
    setLoading(true);
    setError("");
    try {
      setDocument(await getEvidence(source.source_id));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <li className="evidence-source">
      <div>
        <code>{source.source_id}</code>
        {source.source_title && <p>{source.source_title} · {source.source_type?.replaceAll("_", " ")}</p>}
        {source.claim && <p>Claim: {source.claim}</p>}
        <p>“{source.passage}”</p>
        <button type="button" onClick={toggle}
          aria-expanded={open}
          aria-label={`${open ? "Hide" : "View"} full source ${source.source_id}`}>
          {open ? "Hide full source" : "View full source"}
        </button>
        {open && (
          <div className="evidence-source__detail">
            {loading && <p>Loading source…</p>}
            {error && <p role="alert">{error}</p>}
            {document && (
              <>
                <h4>{document.title}</h4>
                <pre>{document.text}</pre>
              </>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
