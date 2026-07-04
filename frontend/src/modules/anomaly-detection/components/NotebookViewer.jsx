import { useEffect, useState } from "react";
import { marked } from "marked";

const ANSI_ESCAPE_RE = /\x1B\[[0-9;]*[a-zA-Z]/g;

function joinSource(source) {
  if (Array.isArray(source)) return source.join("");
  return source || "";
}

function stripAnsi(text) {
  return text.replace(ANSI_ESCAPE_RE, "");
}

function renderMarkdown(source, imagesBaseUrl) {
  const rewritten = joinSource(source).replace(
    /(src=["'])(?!https?:\/\/|\/)([^"']+)(["'])/g,
    (_match, pre, path, post) => `${pre}${imagesBaseUrl}/${path}${post}`
  );
  return { __html: marked.parse(rewritten) };
}

function CellOutput({ output, index }) {
  if (output.output_type === "stream") {
    return (
      <pre className="nb-output-stream">{stripAnsi(joinSource(output.text))}</pre>
    );
  }

  if (output.output_type === "error") {
    return (
      <pre className="nb-output-error">
        {stripAnsi(joinSource(output.traceback))}
      </pre>
    );
  }

  if (output.output_type === "execute_result" || output.output_type === "display_data") {
    const data = output.data || {};

    if (data["image/png"]) {
      return (
        <img
          className="nb-output-image"
          src={`data:image/png;base64,${joinSource(data["image/png"])}`}
          alt={`Output ${index}`}
        />
      );
    }

    if (data["text/html"]) {
      return (
        <div
          className="nb-output-html"
          dangerouslySetInnerHTML={{ __html: joinSource(data["text/html"]) }}
        />
      );
    }

    if (data["text/plain"]) {
      return <pre className="nb-output-plain">{joinSource(data["text/plain"])}</pre>;
    }
  }

  return null;
}

function NotebookCell({ cell, imagesBaseUrl }) {
  if (cell.cell_type === "markdown") {
    return (
      <div
        className="nb-markdown-cell"
        dangerouslySetInnerHTML={renderMarkdown(cell.source, imagesBaseUrl)}
      />
    );
  }

  if (cell.cell_type === "code") {
    const execCount = cell.execution_count != null ? `[${cell.execution_count}]` : "[ ]";
    return (
      <div className="nb-code-cell">
        <div className="nb-code-block">
          <span className="nb-exec-count">In {execCount}:</span>
          <pre className="nb-code-source">{joinSource(cell.source)}</pre>
        </div>

        {(cell.outputs || []).length > 0 && (
          <div className="nb-outputs">
            {cell.outputs.map((output, i) => (
              <CellOutput key={i} output={output} index={i} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return null;
}

export default function NotebookViewer({ url, imagesBaseUrl = "" }) {
  const [notebook, setNotebook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load notebook (${res.status}).`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setNotebook(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load notebook.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [url]);

  if (loading) return <p className="poi-empty">Loading notebook...</p>;
  if (error) return <div className="poi-alert poi-alert-error">{error}</div>;
  if (!notebook) return null;

  return (
    <div className="nb-viewer">
      {notebook.cells.map((cell, i) => (
        <NotebookCell key={i} cell={cell} imagesBaseUrl={imagesBaseUrl} />
      ))}
    </div>
  );
}
