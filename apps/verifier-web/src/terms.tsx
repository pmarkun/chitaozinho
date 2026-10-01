import terms from "../../../packages/project-content/terms.json";

export function Terms() {
  return (
    <main id="main-content" className="privacy-page" tabIndex={-1}>
      <p className="eyebrow">Projeto Evidências</p>
      <h1>{terms.title}</h1>
      <p>Versão de 1º de outubro de 2026.</p>
      <p>{terms.introduction}</p>
      <p>{terms.acceptance}</p>
      <ol type="i">
        {terms.clauses.map((clause) => (
          <li key={clause}>{clause}</li>
        ))}
      </ol>
    </main>
  );
}
