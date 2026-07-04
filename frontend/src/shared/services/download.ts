// Dispara la descarga en el navegador a partir de una respuesta blob de axios.
// Compartido por los features que exportan Excel (gestion, dashboard-gestor, cierre-cursada).

const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

interface RespuestaBlob {
  data: BlobPart;
  headers: Record<string, unknown>;
}

export function dispararDescarga(resp: RespuestaBlob, fallback: string): void {
  const cd = resp.headers['content-disposition'] as string | undefined;
  const match = cd?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? fallback;

  const blob = new Blob([resp.data], { type: XLSX_MIME });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
