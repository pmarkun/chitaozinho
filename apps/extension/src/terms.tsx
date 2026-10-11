import { createRoot } from "react-dom/client";
import terms from "../../../packages/project-content/terms.json";
import "./terms.css";

createRoot(document.getElementById("root")!).render(
  <main>
    <p>Evidências</p>
    <h1>{terms.title}</h1>
    <p>Versão de 1º de outubro de 2026.</p>
    <p>{terms.introduction}</p>
    <p>{terms.acceptance}</p>
    <ol type="i">
      {terms.clauses.map((clause) => (
        <li key={clause}>{clause}</li>
      ))}
    </ol>
  </main>,
);
