// Download the chart's underlying numbers as a CSV — the PM can take the real
// statistics into a spreadsheet, not just a picture.
export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number)[][],
): void {
  const esc = (v: string | number) => {
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const body = [headers, ...rows].map((r) => r.map(esc).join(",")).join("\n");
  const blob = new Blob([body], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// Export an inline <svg> chart to a PNG download. Charts use explicit grayscale
// hex (not CSS vars) so the rasterized image is faithful and self-contained.

export async function downloadSvgAsPng(
  svg: SVGSVGElement,
  filename: string,
  scale = 2,
): Promise<void> {
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));

  const xml = new XMLSerializer().serializeToString(svg);
  const src =
    "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));

  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("svg load failed"));
    img.src = src;
  });

  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.fillStyle = "#ffffff"; // paper background, so the PNG drops cleanly into a slide
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

  await new Promise<void>((resolve) => {
    canvas.toBlob((blob) => {
      if (blob) {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename.endsWith(".png") ? filename : `${filename}.png`;
        a.click();
        URL.revokeObjectURL(a.href);
      }
      resolve();
    }, "image/png");
  });
}
