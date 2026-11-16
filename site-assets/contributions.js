(function () {
  "use strict";
  const normalize = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
  const IMAGE_HEADERS = new Set(["imagen", "imagenes", "image", "images", "foto", "fotografia"]);
  const NOTE_HEADERS = new Set(["nota", "notas", "note", "descripcion", "comentario", "comentarios", "observaciones"]);
  let decoderPromise;
  function loadHeicDecoder(base) {
    if (window.MineralHeicConverter?.heicTo) return Promise.resolve(window.MineralHeicConverter);
    if (!decoderPromise) decoderPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script"); script.async = true;
      script.src = base + "/vendor/heic-decoder-1.6.7.js";
      const timer = setTimeout(() => { script.remove(); decoderPromise = null; reject(new Error("No se pudo cargar el conversor HEIC. Revisa tu conexión e inténtalo otra vez.")); }, 45000);
      script.onload = () => { clearTimeout(timer); if (window.MineralHeicConverter?.heicTo) resolve(window.MineralHeicConverter); else { decoderPromise = null; reject(new Error("No se pudo iniciar el conversor HEIC.")); } };
      script.onerror = () => { clearTimeout(timer); script.remove(); decoderPromise = null; reject(new Error("No se pudo cargar el conversor HEIC. Revisa tu conexión e inténtalo otra vez.")); };
      document.head.appendChild(script);
    });
    return decoderPromise;
  }
  function isHeic(file) { return /\.hei[cf]$/i.test(file.name) || /^image\/hei[cf](?:-sequence)?$/i.test(file.type); }
  async function nativeImage(blob) {
    const url = URL.createObjectURL(blob), image = new Image(); image.src = url;
    try { await image.decode(); return { source: image, width: image.naturalWidth, height: image.naturalHeight, release: () => { image.removeAttribute("src"); URL.revokeObjectURL(url); } }; }
    catch (error) { URL.revokeObjectURL(url); throw error; }
  }
  function imageTable(article) {
    for (const table of article.querySelectorAll("table")) {
      const headers = [...table.querySelectorAll("thead tr:first-child th")].map(th => normalize(th.textContent));
      const image = headers.findIndex(text => IMAGE_HEADERS.has(text));
      const note = headers.findIndex(text => NOTE_HEADERS.has(text));
      if (image >= 0 && note >= 0) return { table, image, note, columns: headers.length };
    }
    return null;
  }
  function createTable(root) {
    const table = document.createElement("table"); table.className = "mc-image-table";
    table.innerHTML = "<thead><tr><th>imagen</th><th>nota</th></tr></thead><tbody></tbody>";
    root.before(table); return { table, image: 0, note: 1, columns: 2 };
  }
  async function gallery(root, base, mineral) {
    const response = await fetch(base + "/api/photos?mineral=" + encodeURIComponent(mineral), { credentials: "omit", cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !Array.isArray(data.photos)) throw new Error(data.error || "No se pudieron cargar las fotografías de la comunidad.");
    const article = root.closest("article") || root.parentElement;
    let target = imageTable(article);
    if (!target && data.photos.length) target = createTable(root);
    if (!target) return;
    document.dispatchEvent(new CustomEvent("mineral-tables:before-update", { detail: { table: target.table } }));
    const tbody = target.table.tBodies[0] || target.table.createTBody();
    for (const old of tbody.querySelectorAll("tr[data-community-photo]")) old.remove();
    for (const photo of data.photos) {
      if (photo.mineral !== mineral || !/^[0-9a-f-]{36}$/i.test(photo.id)) continue;
      const row = document.createElement("tr"); row.dataset.communityPhoto = photo.id;
      for (let i = 0; i < target.columns; i++) row.insertCell();
      const link = document.createElement("a"); link.href = base + "/api/photos/" + photo.id + "/image"; link.target = "_blank"; link.rel = "noopener";
      const image = document.createElement("img"); image.src = link.href; image.alt = photo.description || "Fotografía de " + root.dataset.mineralName; image.loading = "lazy"; image.decoding = "async"; image.className = "mc-community-image";
      if (Number(photo.width) > 0 && Number(photo.height) > 0) { image.width = photo.width; image.height = photo.height; }
      link.append(image); row.cells[target.image].append(link);
      const description = document.createElement("p"); description.className = "mc-photo-note"; description.textContent = photo.description;
      row.cells[target.note].append(description);
      if (photo.author) { const author = document.createElement("p"); author.className = "mc-credit"; author.textContent = "Foto: " + photo.author; row.cells[target.note].append(author); }
      const label = document.createElement("span"); label.className = "mc-community-label"; label.textContent = "Aporte de la comunidad"; row.cells[target.note].append(label);
      tbody.append(row);
    }
    document.dispatchEvent(new CustomEvent("mineral-tables:update"));
  }
  async function prepareImage(file, base = location.origin, notify = () => {}) {
    const type = file.type.toLowerCase();
    if (/svg|xml|html/.test(type) || !(/\.(jpe?g|png|webp|avif|hei[cf]|gif|bmp)$/i.test(file.name) || /^image\/(jpeg|png|webp|avif|hei[cf](?:-sequence)?|gif|bmp)$/.test(type))) throw new Error("Elige una imagen JPG, PNG, WebP, AVIF o una foto HEIC de tu teléfono.");
    if (file.size > 35 * 1024 * 1024) throw new Error("La imagen original no puede superar 35 MB.");
    let decoded;
    try {
      try { decoded = await nativeImage(file); }
      catch {
        if (!isHeic(file)) throw new Error("El navegador no pudo abrir esta imagen. Comprueba que el archivo no esté dañado.");
        notify("Convirtiendo HEIC a JPEG en tu dispositivo…");
        const decoder = await loadHeicDecoder(base);
        try {
          if (typeof createImageBitmap === "function") {
            const bitmap = await decoder.heicTo({ blob: file, type: "bitmap" });
            decoded = { source: bitmap, width: bitmap.width, height: bitmap.height, release: () => bitmap.close() };
          } else {
            const jpeg = await decoder.heicTo({ blob: file, type: "image/jpeg", quality: .98 });
            decoded = await nativeImage(jpeg);
          }
        } catch { throw new Error("No se pudo convertir esta fotografía HEIC. Comprueba que el archivo no esté dañado e inténtalo otra vez."); }
      }
      const scale = Math.min(1, 2400 / Math.max(decoded.width, decoded.height));
      if (!decoded.width || !decoded.height) throw new Error("No se pudo leer la fotografía.");
      const canvas = document.createElement("canvas"); canvas.width = Math.max(1, Math.round(decoded.width * scale)); canvas.height = Math.max(1, Math.round(decoded.height * scale));
      const context = canvas.getContext("2d"); if (!context) throw new Error("No se pudo preparar la fotografía.");
      context.fillStyle = "white"; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(decoded.source, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", .9));
      canvas.width = 0; canvas.height = 0;
      if (!blob || blob.size > 8 * 1024 * 1024) throw new Error("No se pudo reducir la fotografía a menos de 8 MB.");
      return new File([blob], "fotografia.jpg", { type: "image/jpeg" });
    } finally { decoded?.release(); }
  }
  function mount(root) {
    if (root.dataset.mcReady) return;
    root.dataset.mcReady = "true";
    const base = (root.dataset.api || location.origin).replace(/\/$/, ""), mineral = root.dataset.mineralId;
    if (!mineral) return;
    root.innerHTML = '<details class="mc-upload"><summary>Añadir una fotografía</summary><form class="mc-form">' +
      '<p class="mc-explanation">La foto y su nota se añadirán a esta ficha después de la revisión.</p>' +
      '<div class="mc-pickers"><button type="button" data-picker="camera">Tomar foto</button><button type="button" data-picker="library">Galería</button><button type="button" data-picker="file">Archivo de imagen</button></div>' +
      '<p class="mc-explanation">Las fotos HEIC/HEIF de iPhone se convierten automáticamente a JPEG antes de enviarlas.</p>' +
      '<input class="mc-file" type="file" data-input="camera" accept="image/*" capture="environment" aria-label="Tomar una fotografía">' +
      '<input class="mc-file" type="file" data-input="library" accept="image/*" aria-label="Elegir fotografía de la galería">' +
      '<input class="mc-file" type="file" data-input="file" accept=".jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.gif,.bmp" aria-label="Elegir un archivo de imagen">' +
      '<div class="mc-preview" hidden><img alt="Vista previa de tu fotografía"><p class="mc-filename"></p><button type="button" class="mc-remove">Quitar foto</button></div>' +
      '<label class="mc-field"><span>Nota / descripción de la fotografía</span><textarea name="description" rows="4" maxlength="1800" placeholder="Localidad, tamaño del ejemplar, rasgos que se aprecian…"></textarea><small>Aparecerá en la columna «nota», junto a la imagen.</small></label>' +
      '<label class="mc-field"><span>Autor de la fotografía <small>(opcional)</small></span><input name="author" type="text" maxlength="120" autocomplete="name"></label>' +
      '<label class="mc-permission"><input name="permission" type="checkbox" required><span>Tengo permiso para publicar esta fotografía y su descripción.</span></label>' +
      '<div class="mc-trap" aria-hidden="true"><label>Deja este campo vacío<input name="website" type="text" tabindex="-1" autocomplete="off"></label></div>' +
      '<button class="mc-submit" type="submit" disabled>Enviar para revisión</button><p class="mc-status" role="status" aria-live="polite"></p></form></details>';
    const form = root.querySelector("form"), submit = root.querySelector(".mc-submit"), status = root.querySelector(".mc-status"), preview = root.querySelector(".mc-preview");
    let prepared = null, previewUrl = null, requestId = crypto.randomUUID(), busy = false, preparing = false, selection = 0;
    if (root.dataset.uploadOnly === "true") root.querySelector("details").open = true;
    function message(text, error) { status.textContent = text; status.classList.toggle("mc-error", !!error); }
    function remove() { selection++; prepared = null; if (previewUrl) URL.revokeObjectURL(previewUrl); previewUrl = null; preview.hidden = true; preview.querySelector("img").removeAttribute("src"); submit.disabled = true; root.querySelectorAll('input[type="file"]').forEach(input => { input.value = ""; }); }
    root.querySelectorAll("[data-picker]").forEach(button => button.addEventListener("click", () => root.querySelector('[data-input="' + button.dataset.picker + '"]').click()));
    root.querySelector(".mc-remove").addEventListener("click", () => { if (!busy) { remove(); message(""); } });
    form.querySelectorAll('textarea, input[name="author"]').forEach(input => input.addEventListener("input", () => { if (!busy) requestId = crypto.randomUUID(); }));
    root.querySelectorAll('input[type="file"]').forEach(input => input.addEventListener("change", async () => {
      const file = input.files[0]; if (!file || busy || preparing) return;
      remove(); const current = selection; message("Preparando imagen…");
      preparing = true; root.querySelectorAll('[data-picker], input[type="file"]').forEach(control => { control.disabled = true; });
      try {
        const image = await prepareImage(file, base, text => { if (current === selection) message(text); }); if (current !== selection) return;
        prepared = image; requestId = crypto.randomUUID(); previewUrl = URL.createObjectURL(image); preview.querySelector("img").src = previewUrl;
        preview.querySelector(".mc-filename").textContent = file.name + " · " + Math.max(1, Math.round(image.size / 1024)) + " KB";
        preview.hidden = false; submit.disabled = false; message(isHeic(file) ? "HEIC convertido a JPEG. Puedes añadir una nota antes de enviarlo." : "Imagen preparada. Puedes añadir una nota antes de enviarla.");
      } catch (error) { if (current === selection) message(error.message, true); }
      finally { preparing = false; root.querySelectorAll('[data-picker], input[type="file"]').forEach(control => { control.disabled = false; }); }
    }));
    form.addEventListener("submit", async event => {
      event.preventDefault(); if (busy || !prepared || !form.reportValidity()) return;
      busy = true; form.querySelectorAll("button, input, textarea").forEach(control => { control.disabled = true; }); message("Enviando fotografía…");
      const data = new FormData(); data.set("mineral", mineral); data.set("description", form.elements.description.value); data.set("author", form.elements.author.value); data.set("permission", "yes"); data.set("website", form.elements.website.value); data.set("requestId", requestId); data.set("image", prepared);
      try {
        const response = await fetch(base + "/api/submissions", { method: "POST", body: data, credentials: "omit" });
        const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo enviar la fotografía.");
        form.reset(); remove(); message("Fotografía enviada. Quedará privada hasta su aprobación y después aparecerá en la tabla de esta ficha.");
      } catch (error) { message(error.message || "No hay conexión. Puedes volver a intentarlo sin duplicar el envío.", true); }
      finally { busy = false; form.querySelectorAll("button, input, textarea").forEach(control => { control.disabled = false; }); submit.disabled = !prepared; }
    });
    if (root.dataset.uploadOnly !== "true") {
      const article = root.closest("article") || root.parentElement, target = imageTable(article);
      if (target) { const wrapper = target.table.closest(".md-typeset__scrollwrap") || target.table; wrapper.after(root); }
      gallery(root, base, mineral).catch(() => {
        const warning = document.createElement("p"); warning.className = "mc-gallery-warning";
        const retry = document.createElement("button"); retry.type = "button"; retry.textContent = "Reintentar cargar fotos de la comunidad";
        retry.addEventListener("click", () => { retry.disabled = true; gallery(root, base, mineral).then(() => warning.remove()).catch(() => { retry.disabled = false; }); });
        warning.append(retry); root.append(warning);
      });
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && root.isConnected) gallery(root, base, mineral).catch(() => {}); });
    }
  }
  function init(scope = document) { scope.querySelectorAll(".mineral-contributions").forEach(mount); }
  window.MineralContributions = { init, imageTable, prepareImage };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => init()); else init();
  if (typeof document$ !== "undefined") document$.subscribe(() => init());
})();
